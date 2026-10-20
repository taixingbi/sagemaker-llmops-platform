from pipeline.quality_gate import evaluate_training_gate


def test_passes_when_above_threshold() -> None:
    result = evaluate_training_gate(
        {"quality_score": 0.89, "eval_loss": 1.2},
        min_quality_score=0.88,
        max_eval_loss=2.5,
    )
    assert result["eligible_for_registration"] is True
    assert result["reasons"] == []


def test_rejects_low_quality() -> None:
    result = evaluate_training_gate(
        {"quality_score": 0.70, "eval_loss": 1.0},
        min_quality_score=0.88,
    )
    assert result["eligible_for_registration"] is False
    assert any("quality_score" in r for r in result["reasons"])


def test_rejects_high_loss() -> None:
    result = evaluate_training_gate(
        {"quality_score": 0.95, "eval_loss": 3.5},
        max_eval_loss=2.5,
    )
    assert result["eligible_for_registration"] is False
    assert any("eval_loss" in r for r in result["reasons"])
