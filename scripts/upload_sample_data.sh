#!/usr/bin/env bash
# Upload sample train/eval JSONL to the artifacts bucket data/raw prefix.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV="${1:-dev}"
REGION="${AWS_REGION:-us-east-1}"

if [[ -n "${ARTIFACTS_BUCKET:-}" ]]; then
  BUCKET="${ARTIFACTS_BUCKET}"
else
  ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
  BUCKET="llm-finetune-artifacts-${ENV}-${ACCOUNT}"
fi

echo "Uploading sample data → s3://${BUCKET}/data/raw/"
aws s3 cp "${ROOT}/data/sample/train.jsonl" "s3://${BUCKET}/data/raw/train.jsonl" --region "${REGION}"
aws s3 cp "${ROOT}/data/sample/eval.jsonl" "s3://${BUCKET}/data/raw/eval.jsonl" --region "${REGION}"
aws s3 cp "${ROOT}/data/schemas/instruction.json" "s3://${BUCKET}/data/schemas/instruction.json" --region "${REGION}"
echo "done"
