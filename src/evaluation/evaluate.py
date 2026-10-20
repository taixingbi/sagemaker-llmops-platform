"""Evaluation Processing Job entrypoint.

Inputs:
  /opt/ml/processing/model   — trained adapter / model dir
  /opt/ml/processing/data    — eval.jsonl
Outputs:
  /opt/ml/processing/evaluation/evaluation.json  — metrics for ConditionStep
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--model-dir", type=Path, default=Path("/opt/ml/processing/model"))
    p.add_argument("--data-dir", type=Path, default=Path("/opt/ml/processing/data"))
    p.add_argument("--output-dir", type=Path, default=Path("/opt/ml/processing/evaluation"))
    p.add_argument("--max-samples", type=int, default=64)
    return p.parse_args(argv)


def find_eval_file(data_dir: Path) -> Path:
    for candidate in (
        data_dir / "eval.jsonl",
        data_dir / "data" / "eval.jsonl",
    ):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"eval.jsonl not found under {data_dir}")


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def format_prompt(row: dict) -> str:
    instruction = row["instruction"]
    inp = row.get("input") or ""
    if inp:
        return f"### Instruction:\n{instruction}\n\n### Input:\n{inp}\n\n### Response:\n"
    return f"### Instruction:\n{instruction}\n\n### Response:\n"


def compute_quality_score(avg_loss: float, exact_match_rate: float) -> float:
    """Map loss + EM into a 0–1 quality score for the ConditionStep.

    Tuned for demo thresholds (pass ≥ 0.88). Real projects should replace
    with task-specific metrics (BLEU/ROUGE/LLM-judge).
    """
    loss_component = 1.0 / (1.0 + avg_loss)  # loss 0 → 1.0; loss 2.5 → ~0.29
    score = 0.55 * loss_component + 0.45 * exact_match_rate
    return round(min(max(score, 0.0), 1.0), 4)


def _ensure_eval_deps() -> None:
    """Install HF stack on PyTorch DLC if missing (keeps Processing on CPU)."""
    try:
        import peft  # noqa: F401
        import transformers  # noqa: F401
    except ImportError:
        import subprocess

        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "transformers>=4.45.0",
                "peft>=0.13.0",
                "accelerate>=0.34.0",
                "safetensors>=0.4.5",
                "-q",
            ],
            stdout=sys.stdout,
            stderr=sys.stderr,
        )


def evaluate(model_dir: Path, data_dir: Path, output_dir: Path, max_samples: int) -> dict:
    _ensure_eval_deps()
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    eval_path = find_eval_file(data_dir)
    rows = load_jsonl(eval_path)[:max_samples]

    lineage_path = model_dir / "lineage.json"
    base_model = "Qwen/Qwen2.5-0.5B-Instruct"
    if lineage_path.is_file():
        base_model = json.loads(lineage_path.read_text()).get("base_model", base_model)

    tokenizer = AutoTokenizer.from_pretrained(model_dir, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # Prefer PEFT adapter layout; fall back to full model dir
    adapter_cfg = model_dir / "adapter_config.json"
    if adapter_cfg.is_file():
        base = AutoModelForCausalLM.from_pretrained(
            base_model,
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            trust_remote_code=True,
        )
        model = PeftModel.from_pretrained(base, str(model_dir))
    else:
        model = AutoModelForCausalLM.from_pretrained(
            model_dir,
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            trust_remote_code=True,
        )
    model.eval()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    losses: list[float] = []
    exact = 0
    for row in rows:
        prompt = format_prompt(row)
        target = row["output"]
        full = prompt + target
        enc = tokenizer(full, return_tensors="pt", truncation=True, max_length=512)
        enc = {k: v.to(device) for k, v in enc.items()}
        # Mask prompt tokens for causal LM loss on response only
        prompt_len = len(tokenizer(prompt, add_special_tokens=False)["input_ids"])
        labels = enc["input_ids"].clone()
        labels[:, :prompt_len] = -100
        with torch.no_grad():
            out = model(**enc, labels=labels)
            losses.append(float(out.loss.item()))

        gen = model.generate(
            **tokenizer(prompt, return_tensors="pt").to(device),
            max_new_tokens=64,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
        decoded = tokenizer.decode(gen[0][enc["input_ids"].shape[-1] :], skip_special_tokens=True)
        # Rough EM: strip and compare lowercase
        if decoded.strip().lower() == target.strip().lower():
            exact += 1

    avg_loss = sum(losses) / max(len(losses), 1)
    em_rate = exact / max(len(rows), 1)
    quality = compute_quality_score(avg_loss, em_rate)
    perplexity = math.exp(min(avg_loss, 20))

    report = {
        "metrics": {
            "quality_score": quality,
            "eval_loss": round(avg_loss, 6),
            "perplexity": round(perplexity, 4),
            "exact_match_rate": round(em_rate, 4),
            "num_samples": len(rows),
        },
        "base_model": base_model,
        "passed_hint": quality >= 0.88,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "evaluation.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n")

    # SageMaker ModelMetrics / PropertyFile convention for Pipeline
    (output_dir / "evaluation.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report["metrics"]))
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        evaluate(args.model_dir, args.data_dir, args.output_dir, args.max_samples)
    except Exception as exc:  # noqa: BLE001
        print(f"EVALUATION_FAILED: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
