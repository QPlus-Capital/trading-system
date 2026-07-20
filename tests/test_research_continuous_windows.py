"""#32 window attribution: which window owns a trade, and what a ruined account reports.

Both rules decide what the study's per-window numbers MEAN, so they are pinned here rather than
left to the shape of the production windows -- which happen to be contiguous and would hide the
gap case entirely.
"""

from __future__ import annotations

import pandas as pd
import pytest
from research.engine.continuous import window_returns
from research.engine.walkforward import WalkForwardWindow


def _window(test_start: str, test_end: str) -> WalkForwardWindow:
    ts, te = pd.Timestamp(test_start), pd.Timestamp(test_end)
    return WalkForwardWindow(ts - pd.DateOffset(months=12), ts, ts, te)


def _ns(when: str) -> int:
    return int(pd.Timestamp(when).value)


def test_a_trade_resolving_in_a_gap_still_belongs_to_a_window() -> None:
    """A step longer than the test length leaves an interval no window covers.

    A position carried into it and closed there moved the account, so it must appear in the
    counts. Bounding a window by its own end instead of by the next window's start dropped the
    trade from every result while its PnL still shifted the next window's opening equity.
    """
    windows = [_window("2020-01-01", "2020-07-01"), _window("2020-10-01", "2021-04-01")]
    closed = [(_ns("2020-08-15"), 500.0)]  # inside the gap
    first, second = window_returns(closed, windows, start_balance=100_000.0)

    assert first[1] == [pytest.approx(0.005)], "the gap trade belongs to the window before it"
    assert second[0] == 0.0
    # ...and the next window opens on equity that includes it, consistently.
    assert window_returns(closed + [(_ns("2020-11-01"), 1_000.0)], windows, 100_000.0)[1][0] == (
        pytest.approx(1_000.0 / 100_500.0)
    )


def test_contiguous_windows_are_unaffected_by_the_gap_rule() -> None:
    windows = [_window("2020-01-01", "2020-07-01"), _window("2020-07-01", "2021-01-01")]
    closed = [(_ns("2020-03-01"), 100.0), (_ns("2020-09-01"), 200.0)]
    first, second = window_returns(closed, windows, start_balance=100_000.0)
    assert first[1] == [pytest.approx(0.001)]
    assert second[1] == [pytest.approx(200.0 / 100_100.0)]


def test_an_exhausted_account_is_not_reported_as_a_flat_window() -> None:
    """Post-ruin windows averaged in as 0% would flatter the strategy that caused the ruin."""
    windows = [_window("2020-01-01", "2020-07-01"), _window("2020-07-01", "2021-01-01")]
    closed = [(_ns("2020-03-01"), -100_000.0)]  # the account is gone
    with pytest.raises(RuntimeError, match="account exhausted"):
        window_returns(closed, windows, start_balance=100_000.0)
