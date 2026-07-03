"""Validation scorecard: turn the individual checks into one pass/fail verdict.

Collects the metrics produced by the other tools (walk-forward efficiency, OOS
profitability, deflated Sharpe ratio, PBO, out-of-sample Monte-Carlo, stress) and
grades them against acceptance thresholds, then prints an overall verdict.

Metrics are read from a JSON file (default ``reports/metrics.json``), e.g.::

    {"walk_forward_efficiency": 0.11, "oos_profitable_windows": 0.74,
     "deflated_sharpe_ratio": 0.60, "prob_backtest_overfitting": 0.0,
     "oos_mc_prob_profit": 1.0, "oos_mc_max_dd_p95": 0.258,
     "stress_worst_return": -0.028}

Usage::

    uv run python -m qplus.backtest.validation.acceptance reports/metrics.json
"""

import json
import sys
from dataclasses import dataclass
from pathlib import Path

# (metric key, human label, comparator, threshold). comparator is ">=" or "<=".
_SPEC: list[tuple[str, str, str, float]] = [
    ("walk_forward_efficiency", "Walk-forward efficiency", ">=", 0.30),
    ("oos_profitable_windows", "Profitable OOS windows", ">=", 0.60),
    ("deflated_sharpe_ratio", "Deflated Sharpe ratio", ">=", 0.90),
    ("prob_backtest_overfitting", "Prob. of backtest overfitting", "<=", 0.20),
    ("oos_mc_prob_profit", "OOS Monte-Carlo prob. of profit", ">=", 0.90),
    ("oos_mc_max_dd_p95", "OOS Monte-Carlo 95th-pct max drawdown", "<=", 0.35),
    ("stress_worst_return", "Worst crisis-window return", ">=", -0.20),
]


@dataclass(frozen=True)
class Check:
    """One graded metric."""

    label: str
    value: float | None
    comparator: str
    threshold: float
    passed: bool


def build_scorecard(metrics: dict[str, float]) -> list[Check]:
    """Grade each metric in the spec against its threshold (missing = fail)."""
    checks: list[Check] = []
    for key, label, comparator, threshold in _SPEC:
        value = metrics.get(key)
        if value is None:
            passed = False
        elif comparator == ">=":
            passed = value >= threshold
        else:
            passed = value <= threshold
        checks.append(Check(label, value, comparator, threshold, passed))
    return checks


def verdict(checks: list[Check]) -> str:
    """Overall verdict from the fraction of checks passed."""
    passed = sum(1 for c in checks if c.passed)
    total = len(checks)
    if passed == total:
        return f"PASS -- robust ({passed}/{total} checks)"
    if passed >= 0.6 * total:
        return f"PROMISING -- not yet proven ({passed}/{total} checks)"
    return f"FAIL -- likely overfit or no edge ({passed}/{total} checks)"


def render(checks: list[Check]) -> str:
    """Render the scorecard as a text table."""
    lines = [f"{'':2}{'check':<40}{'value':>10}{'target':>12}"]
    lines.append("-" * 64)
    for c in checks:
        mark = "OK " if c.passed else "XX "
        value = "n/a" if c.value is None else f"{c.value:.3f}"
        lines.append(f"{mark}{c.label:<40}{value:>10}{c.comparator + f'{c.threshold:.2f}':>12}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> None:
    """CLI: read a metrics JSON and print the scorecard + verdict."""
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else Path("reports/metrics.json")
    if not path.exists():
        raise SystemExit(f"metrics file not found: {path}")
    metrics = json.loads(path.read_text(encoding="utf-8"))

    checks = build_scorecard(metrics)
    print("===== Validation scorecard =====")
    print(render(checks))
    print(f"\nVerdict: {verdict(checks)}")


if __name__ == "__main__":
    main()
