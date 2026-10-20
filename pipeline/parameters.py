"""Shared pipeline parameter definitions."""

from __future__ import annotations

from sagemaker.workflow.parameters import ParameterFloat, ParameterInteger, ParameterString


def build_parameters(
    *,
    default_bucket: str,
    default_role: str,
    default_base_model: str = "Qwen/Qwen2.5-0.5B-Instruct",
    min_quality_score: float = 0.88,
) -> dict:
    return {
        "processing_instance_type": ParameterString(
            name="ProcessingInstanceType", default_value="ml.m5.xlarge"
        ),
        "training_instance_type": ParameterString(
            name="TrainingInstanceType", default_value="ml.g5.xlarge"
        ),
        "model_approval_status": ParameterString(
            name="ModelApprovalStatus", default_value="PendingManualApproval"
        ),
        "input_data_uri": ParameterString(
            name="InputDataUri",
            default_value=f"s3://{default_bucket}/data/raw",
        ),
        "base_model": ParameterString(name="BaseModel", default_value=default_base_model),
        "epochs": ParameterInteger(name="Epochs", default_value=1),
        "learning_rate": ParameterString(name="LearningRate", default_value="2e-4"),
        "lora_r": ParameterInteger(name="LoraR", default_value=8),
        "min_quality_score": ParameterFloat(
            name="MinQualityScore", default_value=min_quality_score
        ),
        "role_arn": ParameterString(name="RoleArn", default_value=default_role),
    }
