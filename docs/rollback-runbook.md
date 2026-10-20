# Rollback runbook (Week 5 target)

## Triggers

- CloudWatch alarm: elevated 5xx / model latency during canary
- Smoke test failure on staging
- Manual decision after bad eval discovered post-approval

## Immediate actions

1. **Stop traffic shift** — set production variant weight back to 100% on previous model
2. **Invoke** `python deployment/rollback.py --endpoint-name llm-finetune-prod`
3. **Verify** smoke invoke against previous version succeeds
4. **Leave** failed model package as `Rejected` in Model Registry
5. **Open** incident note: pipeline execution ARN, model package ARN, alarm name

## Do not

- Delete the failed model package (keep lineage)
- Re-run GPU training blindly without checking dataset / config diffs
- Keep both full-capacity blue and green fleets after rollback

## Evidence to capture for interviews / demos

- Alarm screenshot / metric query
- Endpoint config history showing weight change
- Model Registry status transition Approved → (canary) → rolled back / Rejected
