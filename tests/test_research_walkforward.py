"""Tests for the walk-forward window scheme."""

import math

import pandas as pd
import pytest
from research.engine.walkforward import (
    WalkForwardResult,
    calmar_score,
    normalized_wfe,
    split_windows,
    walk_forward_efficiency,
    walk_forward_windows,
)


def test_split_windows_reserves_holdout() -> None:
    windows = walk_forward_windows(
        "2018-01-01", "2024-01-01", train_months=12, test_months=6, step_months=6
    )
    data_end = pd.Timestamp("2024-01-01")
    cutoff = data_end - pd.DateOffset(months=12)  # 2023-01-01
    selection, holdout = split_windows(windows, data_end, holdout_months=12)
    assert selection and holdout
    assert all(w.test_end <= cutoff for w in selection)  # selection never touches the holdout
    assert all(w.test_start >= cutoff for w in holdout)
    # holdout_months = 0 -> everything is selection, nothing reserved
    sel0, hold0 = split_windows(windows, data_end, 0)
    assert hold0 == [] and len(sel0) == len(windows)


def test_embargo_gaps_train_from_test() -> None:
    w = walk_forward_windows(
        "2020-01-01", "2023-01-01", train_months=12, test_months=6, step_months=6, embargo_days=7
    )[0]
    assert w.test_start == w.train_end + pd.Timedelta(days=7)  # purged boundary (F5)
    assert w.test_end == w.test_start + pd.DateOffset(months=6)


def test_windows_are_contiguous_and_non_anchored() -> None:
    windows = walk_forward_windows(
        "2020-01-01", "2023-01-01", train_months=12, test_months=6, step_months=6
    )
    # 2020-01 origin, stepping 6m, dropping any window whose test runs past 2023-01.
    assert len(windows) == 4

    first = windows[0]
    assert first.train_start == pd.Timestamp("2020-01-01")
    assert first.train_end == pd.Timestamp("2021-01-01")
    assert first.test_start == pd.Timestamp("2021-01-01")  # test starts where train ends
    assert first.test_end == pd.Timestamp("2021-07-01")

    # Non-anchored: each origin advances by the step; train length stays constant.
    assert windows[1].train_start == pd.Timestamp("2020-07-01")
    assert all(
        (w.train_end.year - w.train_start.year) * 12 + (w.train_end.month - w.train_start.month)
        == 12
        for w in windows
    )
    # No test window exceeds the end.
    assert all(w.test_end <= pd.Timestamp("2023-01-01") for w in windows)


def test_span_too_short_returns_no_windows() -> None:
    windows = walk_forward_windows(
        "2020-01-01", "2020-06-01", train_months=12, test_months=6, step_months=6
    )
    assert windows == []


def test_invalid_sizing_raises() -> None:
    for bad in ({"train_months": 0}, {"test_months": 0}, {"step_months": 0}):
        kwargs = {"train_months": 12, "test_months": 6, "step_months": 6, **bad}
        try:
            walk_forward_windows("2020-01-01", "2023-01-01", **kwargs)
        except ValueError:
            continue
        raise AssertionError(f"expected ValueError for {bad}")


def test_calmar_score_return_over_drawdown() -> None:
    # equity: 1000 -> 1100 -> 1050 -> 1150; return 0.15, max dd (1100-1050)/1100.
    score = calmar_score([100.0, -50.0, 100.0], 1000.0, min_trades=1)
    assert math.isclose(score, 0.15 / (50.0 / 1100.0), rel_tol=1e-9)


def test_calmar_score_too_few_trades_is_minus_inf() -> None:
    assert calmar_score([100.0], 1000.0, min_trades=10) == float("-inf")


def test_walk_forward_efficiency_and_its_length_normalisation() -> None:
    """Efficiency compares OOS against in-sample; normalising removes the window-length bias."""
    results = [
        WalkForwardResult(
            window=f"w{i}",
            best_params={"stop_loss_pct": 1.0},
            is_return=0.20,
            oos_return=0.20,
            oos_trades=2,
            oos_max_dd=0.0,
            oos_returns=[0.1, 0.1],
        )
        for i in range(2)
    ]
    # OOS equals IS here -> raw efficiency 1.0 ...
    assert math.isclose(walk_forward_efficiency(results), 1.0)
    # ... and per month, scaled by train/test = 12/6.
    assert math.isclose(normalized_wfe(results, train_months=12, test_months=6), 2.0)
    with pytest.raises(ValueError, match="test_months must be positive"):
        normalized_wfe(results, train_months=12, test_months=0)
