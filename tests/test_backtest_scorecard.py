"""Tests for the validation scorecard."""

from qplus.backtest.scorecard import build_scorecard, verdict


def _metrics(**overrides: float) -> dict[str, float]:
    base = {
        "walk_forward_efficiency": 0.5,
        "oos_profitable_windows": 0.8,
        "deflated_sharpe_ratio": 0.95,
        "prob_backtest_overfitting": 0.05,
        "oos_mc_prob_profit": 0.95,
        "oos_mc_max_dd_p95": 0.2,
        "stress_worst_return": -0.05,
    }
    base.update(overrides)
    return base


def test_all_pass_gives_robust_verdict() -> None:
    checks = build_scorecard(_metrics())
    assert all(c.passed for c in checks)
    assert verdict(checks).startswith("PASS")


def test_ge_and_le_comparators() -> None:
    # DSR below threshold fails (>=); PBO above threshold fails (<=).
    checks = {c.label: c for c in build_scorecard(_metrics(deflated_sharpe_ratio=0.5))}
    assert not checks["Deflated Sharpe ratio"].passed
    checks = {c.label: c for c in build_scorecard(_metrics(prob_backtest_overfitting=0.9))}
    assert not checks["Prob. of backtest overfitting"].passed


def test_missing_metric_fails() -> None:
    metrics = _metrics()
    del metrics["deflated_sharpe_ratio"]
    checks = {c.label: c for c in build_scorecard(metrics)}
    assert checks["Deflated Sharpe ratio"].value is None
    assert not checks["Deflated Sharpe ratio"].passed


def test_our_current_metrics_are_promising() -> None:
    # The XAUUSD numbers measured this session: 5/7 pass (WFE and DSR fail).
    checks = build_scorecard(_metrics(walk_forward_efficiency=0.11, deflated_sharpe_ratio=0.60))
    assert sum(1 for c in checks if c.passed) == 5
    assert verdict(checks).startswith("PROMISING")
