"""LoRA fine-tuning entrypoint for SageMaker Training Job.

Expects SageMaker channels:
  SM_CHANNEL_TRAIN  — directory with train.jsonl (+ optional eval.jsonl)
  SM_MODEL_DIR      — where to write model artifacts
  SM_OUTPUT_DATA_DIR — metrics / lineage sidecars

Hyperparameters arrive as CLI flags (SageMaker convention).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--model_id", type=str, default="Qwen/Qwen2.5-0.5B-Instruct")
    p.add_argument("--epochs", type=int, default=1)
    p.add_argument("--learning_rate", type=float, default=2e-4)
    p.add_argument("--per_device_train_batch_size", type=int, default=4)
    p.add_argument("--lora_r", type=int, default=8)
    p.add_argument("--lora_alpha", type=int, default=16)
    p.add_argument("--lora_dropout", type=float, default=0.05)
    p.add_argument("--max_seq_length", type=int, default=512)
    p.add_argument("--max_train_samples", type=int, default=-1, help="-1 = all")
    return p.parse_args()


def _sm_path(env_key: str, default: str) -> Path:
    return Path(os.environ.get(env_key, default))


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def format_example(row: dict) -> str:
    instruction = row["instruction"]
    inp = row.get("input") or ""
    output = row["output"]
    if inp:
        prompt = f"### Instruction:\n{instruction}\n\n### Input:\n{inp}\n\n### Response:\n"
    else:
        prompt = f"### Instruction:\n{instruction}\n\n### Response:\n"
    return prompt + output


def train(args: argparse.Namespace) -> None:
    # Heavy imports inside train() so unit tests can import module without GPU deps.
    import torch
    from datasets import Dataset
    from peft import LoraConfig, get_peft_model, TaskType
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    train_dir = _sm_path("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train")
    model_dir = _sm_path("SM_MODEL_DIR", "/opt/ml/model")
    output_dir = _sm_path("SM_OUTPUT_DATA_DIR", "/opt/ml/output/data")
    checkpoint_dir = _sm_path("SM_OUTPUT_DIR", "/opt/ml/checkpoints")

    train_file = train_dir / "train.jsonl"
    if not train_file.is_file():
        # Processing job may nest under data/
        nested = train_dir / "data" / "train.jsonl"
        train_file = nested if nested.is_file() else train_file
    if not train_file.is_file():
        raise FileNotFoundError(f"train.jsonl not found under {train_dir}")

    rows = load_jsonl(train_file)
    if args.max_train_samples > 0:
        rows = rows[: args.max_train_samples]
    texts = [format_example(r) for r in rows]
    ds = Dataset.from_dict({"text": texts})

    tokenizer = AutoTokenizer.from_pretrained(args.model_id, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    def tokenize(batch):
        return tokenizer(
            batch["text"],
            truncation=True,
            max_length=args.max_seq_length,
            padding="max_length",
        )

    tokenized = ds.map(tokenize, batched=True, remove_columns=["text"])

    model = AutoModelForCausalLM.from_pretrained(
        args.model_id,
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        trust_remote_code=True,
    )
    lora = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=args.lora_dropout,
        target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    training_args = TrainingArguments(
        output_dir=str(checkpoint_dir),
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=args.per_device_train_batch_size,
        logging_steps=5,
        save_strategy="epoch",
        report_to=[],
        bf16=torch.cuda.is_available(),
        gradient_checkpointing=True,
        remove_unused_columns=False,
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized,
        data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False),
    )
    result = trainer.train()

    model_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    trainer.save_model(str(model_dir))
    tokenizer.save_pretrained(str(model_dir))

    # Persist adapter + base model id for evaluation / serving lineage
    lineage = {
        "base_model": args.model_id,
        "lora": {
            "r": args.lora_r,
            "alpha": args.lora_alpha,
            "dropout": args.lora_dropout,
        },
        "train_samples": len(rows),
        "metrics": {k: float(v) for k, v in (result.metrics or {}).items() if isinstance(v, (int, float))},
        "git_sha": os.environ.get("GIT_SHA", "unknown"),
    }
    (model_dir / "lineage.json").write_text(json.dumps(lineage, indent=2) + "\n")
    (output_dir / "train_metrics.json").write_text(json.dumps(lineage, indent=2) + "\n")

    # Copy train.jsonl hash companion if present
    manifest = train_dir / "validation_manifest.json"
    if not manifest.is_file():
        manifest = train_dir.parent / "validation_manifest.json"
    if manifest.is_file():
        shutil.copy(manifest, model_dir / "validation_manifest.json")

    print(f"saved model artifacts → {model_dir}")


def main() -> None:
    args = parse_args()
    train(args)


if __name__ == "__main__":
    main()
