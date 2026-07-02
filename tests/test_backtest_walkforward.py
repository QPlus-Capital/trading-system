"""Tests for the walk-forward window scheme."""

import pandas as pd

from qplus.backtest.walkforward import walk_forward_windows


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
