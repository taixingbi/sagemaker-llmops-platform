# SageMaker Fine-Tuning Platform

Automated LLM Fine-Tuning, Evaluation & Deployment Platform on AWS SageMaker.

Developers submit data + training config; the platform runs validation → LoRA fine-tuning → evaluation → quality gate → Model Registry. Staging / canary / rollback land in later weeks.

Complements Bedrock-side managed-model eval/serving: this repo owns **custom model training lifecycle**.

## Architecture

```
GitHub Actions (test · upsert pipeline · start execution)
        │
        ▼
SageMaker Pipeline
  1. Data Validation (Processing)
  2. Fine-Tuning LoRA (Training)
  3. Evaluation (Processing)
  4. Quality Gate (Condition)
  5. Model Registration (Model Registry)
        │
        ▼  (manual approval — Week 4+)
Staging → Canary Production → CloudWatch / rollback
```

## MVP checklist (Week 1–2)

- [x] Terraform: S3 + IAM + ECR + OIDC + budget alarm
- [x] GitHub Actions OIDC workflows
- [x] Data validation Processing Job
- [x] LoRA Training Job (Qwen2.5-0.5B-Instruct)
- [x] Model artifacts → S3
- [x] Evaluation Processing Job
- [x] Quality ConditionStep
- [x] Model Registry registration

## Prerequisites

| Tool | Notes |
|------|--------|
| AWS account | Prefer a personal/sandbox account; **no JP internal data/creds** |
| Terraform ≥ 1.5 | Local apply or CI |
| Python 3.11+ | CI + local unit tests |
| AWS CLI v2 | OIDC bootstrap + pipeline start |
| GitHub repo | OIDC trust scoped to this repo |

## Quick start

```bash
# 1. Bootstrap GitHub OIDC deploy role (once, with admin creds)
export GITHUB_REPOSITORY=OWNER/sagemaker-finetuning-platform
./scripts/setup-gha-oidc-role.sh
# → set GitHub Actions variable AWS_ROLE_ARN to the printed ARN

# 2. Apply infra (dev)
./scripts/tf.sh apply dev

# 3. Upload sample dataset
./scripts/upload_sample_data.sh

# 4. Upsert & start pipeline (local or via Actions)
pip install -r requirements-ci.txt
python scripts/upsert_pipeline.py --env dev
aws sagemaker start-pipeline-execution --pipeline-name llm-finetune-dev
```

## Repository layout

```
.github/workflows/     CI, training trigger, release stubs
infrastructure/terraform/
pipeline/              SageMaker Pipeline definition + quality gate
src/                   preprocessing · training · evaluation · inference
deployment/            staging / promote / rollback (Week 4+)
configs/               env YAML
scripts/               upsert, terraform wrappers, OIDC, cleanup
tests/                 unit tests (CPU, no GPU in CI)
docs/                  architecture, ops, rollback runbook
```

## Cost control

Default base model: **Qwen/Qwen2.5-0.5B-Instruct** + LoRA on `ml.g5.xlarge` (short runs).

- Training Job `max_run` capped; CI never starts GPU jobs on every push
- Endpoints are **opt-in** and deleted after smoke tests (Week 4+)
- AWS Budget alert at **$150** (alert only — does not auto-stop GPUs)
- See [cost.md](cost.md) and [docs/operations.md](docs/operations.md)

## CI/CD

| Workflow | Trigger | Behavior |
|----------|---------|----------|
| `ci.yaml` | PR / push | pytest + Terraform fmt/validate |
| `training.yaml` | `workflow_dispatch` / main (optional) | upsert pipeline + start execution |
| `release.yaml` | manual | promote approved model (Week 4+) |

GitHub Actions trains **nothing** on the runner; it only validates code and starts SageMaker.

## Acceptance experiments

| Scenario | Expected |
|----------|----------|
| Bad dataset schema | Training does not start |
| Training failure | Pipeline stops; logs retained |
| Quality below threshold | Registration skipped |
| Unapproved model | No production deploy (Week 4+) |

## License

Personal learning project. Not for production customer data.
# sagemaker-llmops-platform
# sagemaker-llmops-platform
