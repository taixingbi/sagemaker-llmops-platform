#!/usr/bin/env bash
# Bootstrap GitHub OIDC provider + deploy role (mirrors bedrock-lambda pattern).
# Prefer Terraform (oidc.tf) after first apply; this script is the one-shot alternative.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROLE_NAME="${ROLE_NAME:-llm-finetune-github-actions}"
OIDC_URL="https://token.actions.githubusercontent.com"
OIDC_HOST="token.actions.githubusercontent.com"

die() { echo "error: $*" >&2; exit 1; }
command -v aws >/dev/null || die "aws CLI required"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
REPO="${GITHUB_REPOSITORY:-}"
if [[ -z "${REPO}" ]]; then
  origin="$(git -C "${ROOT}" remote get-url origin 2>/dev/null || true)"
  REPO="$(sed -E 's#.*github.com[:/]([^/]+/[^/.]+)(\.git)?$#\1#' <<<"${origin}")"
fi
[[ "${REPO}" == */* ]] || die "set GITHUB_REPOSITORY=owner/name"

PROVIDER_ARN="arn:aws:iam::${ACCOUNT_ID}:oidc-provider/${OIDC_HOST}"

if ! aws iam get-open-id-connect-provider --open-id-connect-provider-arn "${PROVIDER_ARN}" >/dev/null 2>&1; then
  echo "Creating OIDC provider ${OIDC_HOST}…"
  aws iam create-open-id-connect-provider \
    --url "${OIDC_URL}" \
    --client-id-list sts.amazonaws.com \
    --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1 >/dev/null
fi

TRUST="$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "Federated": "${PROVIDER_ARN}" },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": { "${OIDC_HOST}:aud": "sts.amazonaws.com" },
      "StringLike": { "${OIDC_HOST}:sub": ["repo:${REPO}:*"] }
    }
  }]
}
EOF
)"

if aws iam get-role --role-name "${ROLE_NAME}" >/dev/null 2>&1; then
  aws iam update-assume-role-policy --role-name "${ROLE_NAME}" --policy-document "${TRUST}"
else
  aws iam create-role \
    --role-name "${ROLE_NAME}" \
    --assume-role-policy-document "${TRUST}" \
    --description "GitHub Actions OIDC for ${REPO}" >/dev/null
fi

# Broad enough for first-time Terraform apply + pipeline ops; tighten via Terraform later.
aws iam attach-role-policy \
  --role-name "${ROLE_NAME}" \
  --policy-arn arn:aws:iam::aws:policy/AdministratorAccess >/dev/null 2>&1 || true

ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${ROLE_NAME}"
echo ""
echo "AWS_ROLE_ARN=${ROLE_ARN}"
echo "Add this as a GitHub Actions variable (or secret) named AWS_ROLE_ARN."
echo "NOTE: AdministratorAccess attached for bootstrap only — replace with Terraform-managed least privilege."
