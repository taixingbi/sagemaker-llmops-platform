#!/usr/bin/env python3
"""Create or update the SageMaker Pipeline from pipeline/definition.py."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# Classic Pipeline APIs live in SDK v2 (pinned in requirements-ci.txt).
os.environ.setdefault("SAGEMAKER_SUPPRESS_V2_WARNING", "1")

import boto3
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.definition import create_pipeline  # noqa: E402


def load_config(env: str) -> dict:
    path = ROOT / "configs" / f"{env}.yaml"
    with path.open() as f:
        return yaml.safe_load(f)


def tf_output(env: str, name: str) -> str | None:
    tf_dir = ROOT / "infrastructure" / "terraform"
    try:
        raw = subprocess.check_output(
            ["terraform", "output", "-raw", name],
            cwd=tf_dir,
            env={**os.environ, "TF_WORKSPACE": env},
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return raw or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def resolve_infra(env: str, cfg: dict) -> tuple[str, str, str]:
    """Return (role_arn, bucket, region) from env vars or Terraform outputs."""
    region = (
        os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
        or cfg.get("region")
        or "us-east-1"
    )
    role = os.environ.get("SAGEMAKER_ROLE_ARN") or tf_output(env, "sagemaker_execution_role_arn")
    bucket = os.environ.get("ARTIFACTS_BUCKET") or tf_output(env, "artifacts_bucket")

    if not role or not bucket:
        # Fall back to SSM / tagged discovery via caller account naming convention
        account = boto3.client("sts").get_caller_identity()["Account"]
        bucket = bucket or f"llm-finetune-artifacts-{env}-{account}"
        if not role:
            raise SystemExit(
                "Set SAGEMAKER_ROLE_ARN (and optionally ARTIFACTS_BUCKET) "
                "or apply Terraform and ensure terraform output works."
            )
    return role, bucket, region


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.environ.get("GITHUB_SHA", "local")[:12]


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--env", default="dev", choices=["dev", "prod"])
    p.add_argument("--dry-run", action="store_true", help="Build definition only; print step names")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(args.env)
    role, bucket, region = resolve_infra(args.env, cfg)
    gate = cfg.get("quality_gate", {})

    pipeline = create_pipeline(
        role=role,
        bucket=bucket,
        pipeline_name=cfg["pipeline_name"],
        model_package_group_name=cfg["model_package_group"],
        region=region,
        base_model=cfg.get("base_model", "Qwen/Qwen2.5-0.5B-Instruct"),
        min_quality_score=float(gate.get("min_quality_score", 0.88)),
        git_sha=git_sha(),
    )

    definition = json.loads(pipeline.definition())
    step_names = [s.get("Name") for s in definition.get("Steps", [])]
    print(f"pipeline={cfg['pipeline_name']} steps={step_names}")
    print(f"role={role}")
    print(f"bucket={bucket}")

    if args.dry_run:
        print(json.dumps({"steps": step_names}, indent=2))
        return 0

    upsert = pipeline.upsert(role_arn=role)
    print(f"upserted: {upsert}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
