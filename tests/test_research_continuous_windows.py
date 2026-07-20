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


def test_overlapping_windows_are_refused_before_any_run() -> None:
    """Two segments claiming the same instant leave the schedule unable to say which governs."""
    from research.engine.continuous import continuous_walk_forward

    overlapping = [_window("2020-01-01", "2020-07-01"), _window("2020-04-01", "2020-10-01")]
    with pytest.raises(ValueError, match="overlap"):
        continuous_walk_forward(object(), overlapping, [], lambda w: ({}, 0.0))


def test_a_config_module_without_start_balance_still_works() -> None:
    """The runner's documented CLI passes a config MODULE, which exports only uppercase names."""
    from research.engine.continuous import start_balance_of

    class _Venue:
        starting_balances = ["200_000 USD"]

    class _Module:
        VENUE = _Venue()

    assert start_balance_of(_Module()) == 200_000.0


def test_a_recipe_carrying_its_own_balance_is_used_directly() -> None:
    from research.engine.continuous import start_balance_of

    class _Recipe:
        start_balance = 50_000.0
        VENUE = None

    assert start_balance_of(_Recipe()) == 50_000.0


def test_window_order_from_the_caller_does_not_change_attribution() -> None:
    """window_returns derives interval ends from sequence order, so it must be normalised once.

    An unsorted caller would bound a window by an EARLIER start -- an empty or reversed interval
    -- and the final zip would then hand those returns to the wrong labels and parameters.
    """
    ordered = [_window("2020-01-01", "2020-07-01"), _window("2020-07-01", "2021-01-01")]
    closed = [(_ns("2020-03-01"), 100.0), (_ns("2020-09-01"), 200.0)]
    assert window_returns(closed, ordered, 100_000.0) == window_returns(
        closed, sorted(ordered, key=lambda w: w.test_start), 100_000.0
    )


def test_a_candidate_schedule_closes_the_same_gaps_as_the_chosen_one() -> None:
    """PBO/DSR compare the candidate matrix against the chosen strategy, so both must trade the
    same periods.

    A single span-wide segment would let a candidate trade through a gap no test window owns,
    making the comparison one between different periods. Only visible with step > test: the
    study's own windows are contiguous, which is why the integration test cannot see this.
    """
    from research.engine.schedule_builder import build_schedule

    gapped = [_window("2020-01-01", "2020-07-01"), _window("2020-10-01", "2021-04-01")]
    params = {"stop_loss_pct": 0.5, "take_profit_pct": 2.0}
    candidate = build_schedule(gapped, [params] * len(gapped))

    from core.strategies.param_schedule import segment_at

    in_gap = segment_at(candidate, _ns("2020-08-15"))
    assert in_gap is not None and not in_gap.entries_allowed, "the gap must refuse entries"
    resumed = segment_at(candidate, _ns("2020-11-01"))
    assert resumed is not None and resumed.entries_allowed


def test_a_trade_closing_exactly_at_the_final_boundary_is_counted() -> None:
    """The last window has no successor to hand the instant to.

    Between windows the next one's start owns the boundary, so the bound must be exclusive there
    or the trade counts twice. At the very end an exclusive bound instead drops the trade from
    every result while its PnL still sits in the account.
    """
    windows = [_window("2020-01-01", "2020-07-01"), _window("2020-07-01", "2021-01-01")]
    closed = [(_ns("2021-01-01"), 400.0)]  # exactly on the final test_end
    first, second = window_returns(closed, windows, start_balance=100_000.0)
    assert first[1] == []
    assert second[1] == [pytest.approx(0.004)], "the final-boundary close belongs to the last one"


def test_a_close_on_an_inner_boundary_belongs_to_the_later_window() -> None:
    """And it must be counted once, not in both."""
    windows = [_window("2020-01-01", "2020-07-01"), _window("2020-07-01", "2021-01-01")]
    closed = [(_ns("2020-07-01"), 400.0)]
    first, second = window_returns(closed, windows, start_balance=100_000.0)
    assert first[1] == []
    assert len(second[1]) == 1
