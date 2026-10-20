"""SageMaker inference handler stubs for Hugging Face DLC / custom container.

Week 4+ wires this to real endpoints. Kept minimal so Model Registry packages
have a documented serving contract.
"""

from __future__ import annotations

import json
from typing import Any


def model_fn(model_dir: str) -> dict[str, Any]:
    """Load tokenizer + model. Heavy imports deferred until serve time."""
    from pathlib import Path

    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    path = Path(model_dir)
    lineage = {}
    lineage_path = path / "lineage.json"
    if lineage_path.is_file():
        lineage = json.loads(lineage_path.read_text())
    base_model = lineage.get("base_model", "Qwen/Qwen2.5-0.5B-Instruct")

    tokenizer = AutoTokenizer.from_pretrained(path, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    if (path / "adapter_config.json").is_file():
        base = AutoModelForCausalLM.from_pretrained(base_model, trust_remote_code=True)
        model = PeftModel.from_pretrained(base, str(path))
    else:
        model = AutoModelForCausalLM.from_pretrained(path, trust_remote_code=True)

    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return {"model": model, "tokenizer": tokenizer, "device": device}


def input_fn(request_body: str, content_type: str = "application/json") -> dict[str, Any]:
    if content_type != "application/json":
        raise ValueError(f"unsupported content type: {content_type}")
    payload = json.loads(request_body)
    if "inputs" not in payload and "prompt" not in payload:
        raise ValueError("payload must include 'inputs' or 'prompt'")
    return payload


def predict_fn(input_data: dict[str, Any], model_bundle: dict[str, Any]) -> dict[str, Any]:
    model = model_bundle["model"]
    tokenizer = model_bundle["tokenizer"]
    device = model_bundle["device"]

    prompt = input_data.get("inputs") or input_data.get("prompt")
    max_new_tokens = int(input_data.get("parameters", {}).get("max_new_tokens", 128))

    encoded = tokenizer(prompt, return_tensors="pt").to(device)
    generated = model.generate(
        **encoded,
        max_new_tokens=max_new_tokens,
        do_sample=False,
        pad_token_id=tokenizer.eos_token_id,
    )
    text = tokenizer.decode(generated[0], skip_special_tokens=True)
    return {"generated_text": text}


def output_fn(prediction: dict[str, Any], accept: str = "application/json") -> str:
    if accept != "application/json":
        raise ValueError(f"unsupported accept type: {accept}")
    return json.dumps(prediction)
