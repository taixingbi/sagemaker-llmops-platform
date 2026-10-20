#!/usr/bin/env bash
# Assume the platform operator role via STS (same IAM role GitHub Actions uses via OIDC).
#
# Root cannot call sts:AssumeRole. Use the Terraform-created operator IAM user:
#   ./scripts/assume-role.sh --write-profile   # once: write ~/.aws profiles from tf outputs
#   eval "$(./scripts/assume-role.sh)"        # export temp role creds into this shell
#   ./scripts/assume-role.sh --whoami         # assume + print caller identity
#
# Optional env: AWS_ROLE_ARN, ROLE_SESSION, DURATION, AWS_SOURCE_PROFILE
# Do NOT set AWS_SOURCE_PROFILE to "llmops" — that is the target role profile.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TF_DIR="${ROOT}/infrastructure/terraform"
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
SESSION_NAME="${ROLE_SESSION:-local-ops}"
DURATION="${DURATION:-3600}"
MODE="eval" # eval | print | whoami | write-profile
# Always assume FROM the IAM-user profile, never from AWS_PROFILE=llmops (would nest).
SOURCE_PROFILE="${AWS_SOURCE_PROFILE:-llmops-base}"

die() { echo "error: $*" >&2; exit 1; }
command -v aws >/dev/null || die "aws CLI required"
command -v jq >/dev/null || die "jq required"

for arg in "$@"; do
  case "$arg" in
    --print) MODE=print ;;
    --whoami) MODE=whoami ;;
    --write-profile) MODE=write-profile ;;
    -h|--help)
      sed -n '2,12p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *) die "unknown arg: $arg (use --print|--whoami|--write-profile)" ;;
  esac
done

tf_out() {
  terraform -chdir="${TF_DIR}" output -raw "$1" 2>/dev/null || true
}

resolve_role() {
  if [[ -n "${AWS_ROLE_ARN:-}" ]]; then
    echo "${AWS_ROLE_ARN}"
    return
  fi
  local out
  out="$(tf_out github_actions_role_arn)"
  if [[ -n "${out}" ]]; then
    echo "${out}"
    return
  fi
  local account
  account="$(aws sts get-caller-identity --query Account --output text)"
  echo "arn:aws:iam::${account}:role/llm-finetune-dev-github-actions"
}

write_profile() {
  command -v terraform >/dev/null || die "terraform required for --write-profile"
  local ak sk role
  ak="$(tf_out operator_access_key_id)"
  sk="$(terraform -chdir="${TF_DIR}" output -raw operator_secret_access_key)"
  role="$(tf_out github_actions_role_arn)"
  [[ -n "${ak}" && -n "${sk}" && -n "${role}" ]] || die "missing terraform outputs — run ./scripts/tf.sh apply dev first"

  mkdir -p "${HOME}/.aws"
  local creds="${HOME}/.aws/credentials"
  local config="${HOME}/.aws/config"

  # Strip existing llmops blocks then append (idempotent-ish)
  if [[ -f "${creds}" ]]; then
    awk '
      /^\[llmops-base\]/ {skip=1; next}
      /^\[/ {skip=0}
      !skip {print}
    ' "${creds}" > "${creds}.tmp" && mv "${creds}.tmp" "${creds}"
  fi
  if [[ -f "${config}" ]]; then
    awk '
      /^\[profile llmops\]/ {skip=1; next}
      /^\[/ {skip=0}
      !skip {print}
    ' "${config}" > "${config}.tmp" && mv "${config}.tmp" "${config}"
  fi

  cat >> "${creds}" <<EOF

[llmops-base]
aws_access_key_id = ${ak}
aws_secret_access_key = ${sk}
EOF

  cat >> "${config}" <<EOF

[profile llmops]
role_arn = ${role}
source_profile = llmops-base
region = ${REGION}
EOF

  echo "Wrote profiles: llmops-base (keys) + llmops (sts assume ${role})" >&2
  echo "Use:  export AWS_PROFILE=llmops" >&2
  echo "  or: eval \"\$(./scripts/assume-role.sh)\"" >&2
}

if [[ "${MODE}" == "write-profile" ]]; then
  write_profile
  exit 0
fi

ROLE_ARN="$(resolve_role)"
[[ "${ROLE_ARN}" == arn:aws:iam::* ]] || die "could not resolve role ARN"

# If already on the target role (e.g. AWS_PROFILE=llmops), skip re-assume.
if CURRENT="$(aws sts get-caller-identity --query Arn --output text 2>/dev/null || true)"; then
  if [[ "${CURRENT}" == *":assumed-role/llm-finetune-"*"-github-actions/"* ]] || [[ "${CURRENT}" == *":assumed-role/"*"github-actions/"* ]]; then
    echo "already assumed: ${CURRENT}" >&2
    if [[ "${MODE}" == "whoami" ]]; then
      aws sts get-caller-identity --output json
      exit 0
    fi
    # For eval/print: keep current env; tell user not to nest.
    cat <<EOF
# already on ${CURRENT}
# keep AWS_PROFILE=llmops  OR  existing AWS_* session creds
true
EOF
    exit 0
  fi
fi

# Prefer operator source profile when present so root is not used.
ASSUME_ARGS=(
  --role-arn "${ROLE_ARN}"
  --role-session-name "${SESSION_NAME}"
  --duration-seconds "${DURATION}"
  --region "${REGION}"
  --output json
)
if aws configure list-profiles 2>/dev/null | grep -qx "${SOURCE_PROFILE}"; then
  ASSUME_ARGS+=(--profile "${SOURCE_PROFILE}")
elif [[ -n "${AWS_PROFILE:-}" && "${AWS_PROFILE}" != "llmops" ]]; then
  ASSUME_ARGS+=(--profile "${AWS_PROFILE}")
fi

CREDS="$(aws sts assume-role "${ASSUME_ARGS[@]}")" || die "AssumeRole failed — run ./scripts/assume-role.sh --write-profile first (and unset AWS_PROFILE=llmops before re-assuming)"

AK="$(jq -r '.Credentials.AccessKeyId' <<<"${CREDS}")"
SK="$(jq -r '.Credentials.SecretAccessKey' <<<"${CREDS}")"
ST="$(jq -r '.Credentials.SessionToken' <<<"${CREDS}")"
EXP="$(jq -r '.Credentials.Expiration' <<<"${CREDS}")"

EXPORTS="$(cat <<EOF
export AWS_ACCESS_KEY_ID='${AK}'
export AWS_SECRET_ACCESS_KEY='${SK}'
export AWS_SESSION_TOKEN='${ST}'
export AWS_REGION='${REGION}'
export AWS_DEFAULT_REGION='${REGION}'
export AWS_ROLE_ARN='${ROLE_ARN}'
unset AWS_PROFILE
# expires ${EXP}
EOF
)"

case "${MODE}" in
  print|eval)
    echo "${EXPORTS}"
    ;;
  whoami)
    eval "${EXPORTS}"
    echo "assumed ${ROLE_ARN} (expires ${EXP})" >&2
    aws sts get-caller-identity --output json
    ;;
esac
