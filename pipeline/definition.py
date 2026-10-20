"""SageMaker Pipeline: validate → train (LoRA) → evaluate → quality gate → register."""

from __future__ import annotations

import os
from pathlib import Path

import boto3
from sagemaker import image_uris
from sagemaker.huggingface import HuggingFace
from sagemaker.inputs import TrainingInput
from sagemaker.model_metrics import MetricsSource, ModelMetrics
from sagemaker.processing import ProcessingInput, ProcessingOutput
from sagemaker.pytorch.processing import PyTorchProcessor
from sagemaker.sklearn.processing import SKLearnProcessor
from sagemaker.workflow.condition_step import ConditionStep
from sagemaker.workflow.conditions import ConditionGreaterThanOrEqualTo
from sagemaker.workflow.fail_step import FailStep
from sagemaker.workflow.functions import Join, JsonGet
from sagemaker.workflow.pipeline import Pipeline
from sagemaker.workflow.pipeline_context import PipelineSession
from sagemaker.workflow.properties import PropertyFile
from sagemaker.workflow.step_collections import RegisterModel
from sagemaker.workflow.steps import ProcessingStep, TrainingStep

from pipeline.parameters import build_parameters

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

# Matched train+inference DLC pair for sagemaker SDK 2.257 (us-east-1).
HF_TRANSFORMERS_VERSION = "4.48.0"
HF_PYTORCH_VERSION = "2.3.0"
HF_PY_VERSION = "py311"


def get_pipeline_session(region: str | None = None, default_bucket: str | None = None) -> PipelineSession:
    """PipelineSession defers job/create + code upload until pipeline.upsert()."""
    region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    boto_sess = boto3.Session(region_name=region)
    kwargs = {"boto_session": boto_sess}
    if default_bucket:
        kwargs["default_bucket"] = default_bucket
    return PipelineSession(**kwargs)


def create_pipeline(
    *,
    role: str,
    bucket: str,
    pipeline_name: str,
    model_package_group_name: str,
    region: str = "us-east-1",
    base_model: str = "Qwen/Qwen2.5-0.5B-Instruct",
    min_quality_score: float = 0.88,
    git_sha: str = "local",
) -> Pipeline:
    session = get_pipeline_session(region, default_bucket=bucket)
    params = build_parameters(
        default_bucket=bucket,
        default_role=role,
        default_base_model=base_model,
        min_quality_score=min_quality_score,
    )

    # --- 1. Data validation (SKLearn processor: jsonschema available via requirements) ---
    sklearn_processor = SKLearnProcessor(
        framework_version="1.2-1",
        instance_type=params["processing_instance_type"],
        instance_count=1,
        base_job_name=f"{pipeline_name}-validate",
        role=role,
        sagemaker_session=session,
    )

    step_validate = ProcessingStep(
        name="DataValidation",
        processor=sklearn_processor,
        inputs=[
            ProcessingInput(
                source=params["input_data_uri"],
                destination="/opt/ml/processing/input",
            ),
            ProcessingInput(
                source=str(ROOT / "data" / "schemas"),
                destination="/opt/ml/processing/schema",
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="validated",
                source="/opt/ml/processing/output",
                destination=f"s3://{bucket}/data/processed",
            )
        ],
        code=str(SRC / "preprocessing" / "validate.py"),
        job_arguments=[
            "--input",
            "/opt/ml/processing/input",
            "--output",
            "/opt/ml/processing/output",
            "--schema",
            "/opt/ml/processing/schema/instruction.json",
        ],
    )

    # --- 2. LoRA fine-tuning ---
    hyperparameters = {
        "model_id": params["base_model"],
        "epochs": params["epochs"],
        "learning_rate": params["learning_rate"],
        "lora_r": params["lora_r"],
        "per_device_train_batch_size": "4",
        "lora_alpha": "16",
        "lora_dropout": "0.05",
        "max_seq_length": "512",
    }

    estimator = HuggingFace(
        entry_point="train_lora.py",
        source_dir=str(SRC / "training"),
        instance_type=params["training_instance_type"],
        instance_count=1,
        role=role,
        transformers_version=HF_TRANSFORMERS_VERSION,
        pytorch_version=HF_PYTORCH_VERSION,
        py_version=HF_PY_VERSION,
        hyperparameters=hyperparameters,
        max_run=7200,
        output_path=f"s3://{bucket}/models",
        code_location=f"s3://{bucket}/code",
        environment={"GIT_SHA": git_sha, "PIP_PACKAGES": "peft datasets accelerate"},
        dependencies=[str(ROOT / "requirements-train.txt")],
        sagemaker_session=session,
        base_job_name=f"{pipeline_name}-train",
        disable_output_compression=False,
    )

    step_train = TrainingStep(
        name="LoRAFineTuning",
        estimator=estimator,
        inputs={
            "train": TrainingInput(
                s3_data=step_validate.properties.ProcessingOutputConfig.Outputs[
                    "validated"
                ].S3Output.S3Uri,
                content_type="application/jsonlines",
            )
        },
    )

    # --- 3. Evaluation ---
    # PyTorch CPU DLC (cheaper than GPU HF processor). evaluate.py pip-installs peft/transformers.
    eval_processor = PyTorchProcessor(
        framework_version="2.4",
        py_version="py311",
        role=role,
        instance_type=params["processing_instance_type"],
        instance_count=1,
        base_job_name=f"{pipeline_name}-eval",
        sagemaker_session=session,
    )

    evaluation_report = PropertyFile(
        name="EvaluationReport",
        output_name="evaluation",
        path="evaluation.json",
    )

    step_eval = ProcessingStep(
        name="ModelEvaluation",
        processor=eval_processor,
        inputs=[
            ProcessingInput(
                source=step_train.properties.ModelArtifacts.S3ModelArtifacts,
                destination="/opt/ml/processing/model",
            ),
            ProcessingInput(
                source=step_validate.properties.ProcessingOutputConfig.Outputs[
                    "validated"
                ].S3Output.S3Uri,
                destination="/opt/ml/processing/data",
            ),
        ],
        outputs=[
            ProcessingOutput(
                output_name="evaluation",
                source="/opt/ml/processing/evaluation",
                destination=f"s3://{bucket}/evaluation",
            )
        ],
        code=str(SRC / "evaluation" / "evaluate.py"),
        property_files=[evaluation_report],
        job_arguments=[
            "--model-dir",
            "/opt/ml/processing/model",
            "--data-dir",
            "/opt/ml/processing/data",
            "--output-dir",
            "/opt/ml/processing/evaluation",
        ],
    )

    # --- 4. Quality gate ---
    cond_quality = ConditionGreaterThanOrEqualTo(
        left=JsonGet(
            step_name=step_eval.name,
            property_file=evaluation_report,
            json_path="metrics.quality_score",
        ),
        right=params["min_quality_score"],
    )

    model_metrics = ModelMetrics(
        model_statistics=MetricsSource(
            s3_uri=Join(
                on="/",
                values=[
                    step_eval.properties.ProcessingOutputConfig.Outputs[
                        "evaluation"
                    ].S3Output.S3Uri,
                    "evaluation.json",
                ],
            ),
            content_type="application/json",
        )
    )

    inference_image = image_uris.retrieve(
        framework="huggingface",
        region=region,
        version=HF_TRANSFORMERS_VERSION,
        image_scope="inference",
        base_framework_version=f"pytorch{HF_PYTORCH_VERSION}",
        py_version=HF_PY_VERSION,
        instance_type="ml.g5.xlarge",
    )

    # RegisterModel uses the training step's estimator / model data
    step_register = RegisterModel(
        name="RegisterLoRAModel",
        estimator=estimator,
        model_data=step_train.properties.ModelArtifacts.S3ModelArtifacts,
        image_uri=inference_image,
        content_types=["application/json"],
        response_types=["application/json"],
        inference_instances=["ml.m5.xlarge", "ml.g5.xlarge"],
        transform_instances=["ml.m5.xlarge"],
        model_package_group_name=model_package_group_name,
        approval_status=params["model_approval_status"],
        model_metrics=model_metrics,
        description=f"LoRA fine-tune of {base_model} (git={git_sha})",
    )

    step_fail = FailStep(
        name="QualityGateFailed",
        error_message="Model quality_score below MinQualityScore threshold; registration skipped",
    )

    step_cond = ConditionStep(
        name="QualityGate",
        conditions=[cond_quality],
        if_steps=[step_register],
        else_steps=[step_fail],
    )

    pipeline = Pipeline(
        name=pipeline_name,
        parameters=list(params.values()),
        steps=[step_validate, step_train, step_eval, step_cond],
        sagemaker_session=session,
    )
    return pipeline
