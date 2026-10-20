"""Quality gate helpers — shared by ConditionStep wiring and unit tests."""

from __future__ import annotations

from typing import Any


DEFAULT_MIN_QUALITY = 0.88
DEFAULT_MAX_EVAL_LOSS = 2.5


def evaluate_training_gate(
    metrics: dict[str, Any],
    *,
    min_quality_score: float = DEFAULT_MIN_QUALITY,
    max_eval_loss: float = DEFAULT_MAX_EVAL_LOSS,
) -> dict[str, Any]:
    """Training Gate: model quality before Model Registry.

    Deployment Gate (latency / error rate / canary) is enforced later by the
    release controller + CloudWatch, not this function.
    """
    quality = float(metrics.get("quality_score", 0.0))
    eval_loss = float(metrics.get("eval_loss", 999.0))

    reasons: list[str] = []
    if quality < min_quality_score:
        reasons.append(
            f"quality_score {quality} < min_quality_score {min_quality_score}"
        )
    if eval_loss > max_eval_loss:
        reasons.append(f"eval_loss {eval_loss} > max_eval_loss {max_eval_loss}")

    return {
        "eligible_for_registration": len(reasons) == 0,
        "quality_score": quality,
        "eval_loss": eval_loss,
        "reasons": reasons,
    }
