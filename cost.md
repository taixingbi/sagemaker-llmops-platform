# Cost notes (personal sandbox)

Budget target: **$100–$200**. Budget alarms notify; they do **not** stop GPU jobs.

## Idle vs active

| Resource | Idle cost | Active cost driver |
|----------|-----------|--------------------|
| S3 (data + artifacts + tfstate) | cents/month | versioned checkpoints |
| ECR | cents | image storage |
| SageMaker Training (`ml.g5.xlarge`) | $0 when stopped | ~$1–2/hour (us-east-1; verify Pricing Calculator) |
| Processing (CPU) | $0 when stopped | brief jobs |
| Endpoints | **high if left up** | create only for smoke/canary, then delete |

## Defaults that keep spend down

- Base model: Qwen2.5-0.5B-Instruct + LoRA (not full fine-tune)
- One full GPU training run for demo; CI uses CPU unit tests only
- `max_run` on training jobs
- No long-lived staging + prod endpoints together
- `scripts/cleanup.py` tears down endpoints and optional pipeline executions

## Before creating GPU resources

1. AWS Pricing Calculator: instance type × region × hours
2. Confirm Budget alarm is applied (`infrastructure/terraform`)
3. Prefer `workflow_dispatch` over push-triggered training
