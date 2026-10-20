from src.evaluation.evaluate import compute_quality_score


def test_quality_score_bounds() -> None:
    assert 0.0 <= compute_quality_score(0.0, 1.0) <= 1.0
    assert 0.0 <= compute_quality_score(10.0, 0.0) <= 1.0


def test_better_metrics_higher_score() -> None:
    good = compute_quality_score(0.5, 0.8)
    bad = compute_quality_score(3.0, 0.1)
    assert good > bad
