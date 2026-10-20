#!/usr/bin/env bash
# Thin Terraform wrapper: ./scripts/tf.sh plan|apply|destroy|output [dev|prod]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT}/infrastructure/terraform"
ACTION="${1:-plan}"
ENV="${2:-dev}"
REGION="${AWS_REGION:-us-east-1}"

command -v aws >/dev/null || { echo "aws CLI required" >&2; exit 1; }
command -v terraform >/dev/null || { echo "terraform required" >&2; exit 1; }

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
STATE_BUCKET="llm-finetune-tfstate-${ACCOUNT_ID}"
STATE_KEY="environments/${ENV}/terraform.tfstate"

ensure_state_bucket() {
  if aws s3api head-bucket --bucket "${STATE_BUCKET}" 2>/dev/null; then
    return
  fi
  echo "Creating state bucket s3://${STATE_BUCKET}"
  if [[ "${REGION}" == "us-east-1" ]]; then
    aws s3api create-bucket --bucket "${STATE_BUCKET}" --region "${REGION}"
  else
    aws s3api create-bucket --bucket "${STATE_BUCKET}" --region "${REGION}" \
      --create-bucket-configuration "LocationConstraint=${REGION}"
  fi
  aws s3api put-bucket-versioning --bucket "${STATE_BUCKET}" \
    --versioning-configuration Status=Enabled
  aws s3api put-public-access-block --bucket "${STATE_BUCKET}" \
    --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
  aws s3api put-bucket-encryption --bucket "${STATE_BUCKET}" \
    --server-side-encryption-configuration \
    '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
}

cd "${TF_DIR}"
ensure_state_bucket

terraform init -reconfigure \
  -backend-config="bucket=${STATE_BUCKET}" \
  -backend-config="key=${STATE_KEY}" \
  -backend-config="region=${REGION}"

case "${ACTION}" in
  plan)
    terraform plan -var-file="${ENV}.tfvars" -out="tfplan-${ENV}"
    ;;
  apply)
    terraform apply -var-file="${ENV}.tfvars" -auto-approve
    ;;
  destroy)
    terraform destroy -var-file="${ENV}.tfvars" -auto-approve
    ;;
  output)
    terraform output
    ;;
  *)
    echo "usage: $0 plan|apply|destroy|output [dev|prod]" >&2
    exit 1
    ;;
esac
