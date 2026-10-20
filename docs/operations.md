# Operations

## Bootstrap (once)

```bash
export GITHUB_REPOSITORY=OWNER/sagemaker-finetuning-platform
./scripts/setup-gha-oidc-role.sh   # or let Terraform manage OIDC
./scripts/tf.sh apply dev
# Set GitHub variable AWS_ROLE_ARN to terraform output github_actions_role_arn
```

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
