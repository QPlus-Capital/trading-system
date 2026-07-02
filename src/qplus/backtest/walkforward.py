"""Walk-forward window scheme.

Walk-forward validation splits history into rolling (train, test) windows: parameters
are optimized on each *train* window and then evaluated on the immediately following
*test* window, which the optimizer never saw. Stitching the test windows together
gives an out-of-sample track record -- the honest estimate of future performance.

This module only computes the window boundaries; running and scoring them lives in
the walk-forward runner (built on top of this).
"""

from collections.abc import Sequence
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class WalkForwardWindow:
    """One rolling window: optimize on [train_start, train_end), test on [test_start, test_end)."""

    train_start: pd.Timestamp
    train_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

    @property
    def label(self) -> str:
        """Short human label for the out-of-sample period, e.g. ``2013-02..2013-08``."""
        return f"{self.test_start:%Y-%m}..{self.test_end:%Y-%m}"


def walk_forward_windows(
    start: str | pd.Timestamp,
    end: str | pd.Timestamp,
    *,
    train_months: int,
    test_months: int,
    step_months: int,
) -> list[WalkForwardWindow]:
    """Return rolling walk-forward windows spanning ``start``..``end``.

    Each window trains on ``train_months`` and tests on the following ``test_months``;
    the window origin advances by ``step_months`` (non-anchored: the train length is
    constant). Windows whose test period would run past ``end`` are dropped.

    Parameters
    ----------
    start, end : str or pd.Timestamp
        The overall data span.
    train_months, test_months, step_months : int
        Window sizing, in whole months. All must be positive.

    Returns
    -------
    list[WalkForwardWindow]
    """
    if train_months <= 0 or test_months <= 0 or step_months <= 0:
        raise ValueError("train_months, test_months and step_months must be positive")

    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)

    windows: list[WalkForwardWindow] = []
    train_start = start_ts
    while True:
        train_end = train_start + pd.DateOffset(months=train_months)
        test_start = train_end
        test_end = test_start + pd.DateOffset(months=test_months)
        if test_end > end_ts:
            break
        windows.append(WalkForwardWindow(train_start, train_end, test_start, test_end))
        train_start = train_start + pd.DateOffset(months=step_months)
    return windows


def describe_windows(windows: Sequence[WalkForwardWindow]) -> str:
    """Return a short multi-line summary of the windows (for logging)."""
    if not windows:
        return "no walk-forward windows (data span too short for the given sizing)"
    lines = [f"{len(windows)} walk-forward windows:"]
    lines += [
        f"  train {w.train_start:%Y-%m}..{w.train_end:%Y-%m}  ->  test {w.label}" for w in windows
    ]
    return "\n".join(lines)
