# Operations

## Bootstrap (once)

```bash
export GITHUB_REPOSITORY=taixingbi/sagemaker-llmops-platform
./scripts/setup-gha-oidc-role.sh   # or let Terraform manage OIDC
./scripts/tf.sh apply dev
# Set GitHub variable AWS_ROLE_ARN to terraform output github_actions_role_arn
```

## Local STS AssumeRole

GitHub Actions uses **OIDC** (`AssumeRoleWithWebIdentity`). Locally we use classic
**`sts:AssumeRole` into the same role**. Account **root cannot AssumeRole** (AWS rule),
so Terraform creates a least-privilege IAM user (`…-operator`) whose only permission
is `sts:AssumeRole` on that role.

```bash
# once after terraform apply (writes ~/.aws llmops-base + llmops profiles)
./scripts/assume-role.sh --write-profile

# option A — auto-refresh via profile
export AWS_PROFILE=llmops
aws sts get-caller-identity

# option B — one-shot temp creds in this shell
eval "$(./scripts/assume-role.sh)"
aws sts get-caller-identity
# → AssumedRole …/llm-finetune-dev-github-actions/local-ops

python scripts/upsert_pipeline.py --env dev
```

Extra principals: `local_assume_principals = ["arn:aws:iam::ACCOUNT:user/you"]` in tfvars.
Disable local path: `allow_local_sts_assume = false` (GHA OIDC still works).

If the account already has the GitHub OIDC provider:

```hcl
# infrastructure/terraform/dev.tfvars
manage_github_oidc_provider = false
```

## Run a training pipeline

```bash
./scripts/upload_sample_data.sh dev
export SAGEMAKER_ROLE_ARN=...
export ARTIFACTS_BUCKET=...
python scripts/upsert_pipeline.py --env dev
aws sagemaker start-pipeline-execution --pipeline-name llm-finetune-dev
```

Or use Actions → **training** → Run workflow (manual).

## Cost hygiene

- Prefer `workflow_dispatch` for training (enabled by default)
- After demos: `python scripts/cleanup.py --delete-endpoints --yes`
- Set `budget_notification_email` in tfvars for Budget alerts
- Never leave `ml.g5.*` endpoints running overnight

## Debugging

| Symptom | Where to look |
|---------|----------------|
| Validation failed | CloudWatch `/aws/sagemaker/ProcessingJobs` |
| Training OOM / timeout | Training job logs; lower batch size / `max_run` |
| Quality gate fail | `s3://…/evaluation/evaluation.json` |
| Upsert IAM errors | PassRole on execution role; GHA role policy |

## No internal data

Personal sandbox only — do not upload JP-internal datasets, code, or credentials.
