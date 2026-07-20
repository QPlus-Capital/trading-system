"""#32: the numerical comparison that has to pass before a numbers-changing PR is reviewable.

The threshold is not the interesting part -- the interesting part is that a change which moves
more than was announced cannot be presented as if it had not.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from research.regression import Thresholds, build_report, compare


def _run(
    tmp: Path,
    name: str,
    *,
    n_trades: int = 1000,
    ann_return_pct: float = 40.0,
    full_history: str = "market,r\nEURUSD,1.0\n",
) -> Path:
    run = tmp / name
    run.mkdir(parents=True)
    (run / "portfolio.json").write_text(
        json.dumps(
            {
                "n_trades": n_trades,
                "ann_return_pct": ann_return_pct,
                "max_drawdown_pct": 3.5,
                "total_return_pct": 55.0,
            }
        ),
        encoding="utf-8",
    )
    (run / "full_history_trades.csv").write_text(full_history, encoding="utf-8")
    return run


_LIMITS = Thresholds(trade_count_pct=1.0, annual_return_pp=2.0)


def test_seam_sized_changes_are_expected(tmp_path: Path) -> None:
    """Trade-count drift concentrated at window seams is the whole point of the change."""
    ref = _run(tmp_path, "reference", n_trades=1000, ann_return_pct=40.0)
    cand = _run(tmp_path, "candidate", n_trades=1007, ann_return_pct=41.2)
    result = compare(ref, cand, _LIMITS)
    assert result.unexpected == []
    assert result.metrics["n_trades_drift_pct"] == pytest.approx(0.7)


def test_a_trade_count_beyond_the_limit_is_flagged(tmp_path: Path) -> None:
    ref = _run(tmp_path, "reference", n_trades=1000)
    cand = _run(tmp_path, "candidate", n_trades=1050)  # 5%, far past seam-sized
    result = compare(ref, cand, _LIMITS)
    assert any("trade count moved" in u for u in result.unexpected)


def test_an_annual_return_beyond_the_limit_is_flagged(tmp_path: Path) -> None:
    ref = _run(tmp_path, "reference", ann_return_pct=40.0)
    cand = _run(tmp_path, "candidate", ann_return_pct=46.0)
    result = compare(ref, cand, _LIMITS)
    assert any("annual return moved" in u for u in result.unexpected)


def test_the_full_history_stream_must_be_untouched(tmp_path: Path) -> None:
    """The hard invariant: nothing in a walk-forward change can reach the full-history tail.

    It is produced by full-history backtests at one constant parameter set. If it moved, the
    change did something other than what it claimed, and no threshold should excuse that.
    """
    ref = _run(tmp_path, "reference")
    cand = _run(tmp_path, "candidate", full_history="market,r\nEURUSD,1.4\n")
    result = compare(ref, cand, _LIMITS)
    assert any("full_history_trades.csv changed" in u for u in result.unexpected)


def test_a_missing_invariant_artifact_cannot_be_waved_through(tmp_path: Path) -> None:
    ref = _run(tmp_path, "reference")
    cand = _run(tmp_path, "candidate")
    (cand / "full_history_trades.csv").unlink()
    result = compare(ref, cand, _LIMITS)
    assert any("cannot be compared" in u for u in result.unexpected)


def test_a_run_that_never_reached_the_portfolio_stage_is_refused(tmp_path: Path) -> None:
    ref = _run(tmp_path, "reference")
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(SystemExit, match="no portfolio.json"):
        compare(ref, empty, _LIMITS)


def test_the_report_collects_every_unexpected_change(tmp_path: Path) -> None:
    ref = _run(tmp_path, "reference", n_trades=1000)
    bad = _run(tmp_path, "bad", n_trades=1200)
    good = _run(tmp_path, "good", n_trades=1005)
    report = build_report("32", [(ref, bad), (ref, good)], _LIMITS)

    assert len(report["comparisons"]) == 2
    assert len(report["unexpected_changes"]) == 1
    assert "reference -> bad" in report["unexpected_changes"][0]
    assert report["thresholds"]["trade_count_pct"] == 1.0
    assert "full_history_trades.csv" in report["invariant_artifacts"]
