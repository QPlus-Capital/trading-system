"""Tests for the sizing policies (flat vs drawdown-throttle)."""

import math

import numpy as np
import pandas as pd
from research.portfolio.curves import base_curves
from research.portfolio.drawdown import daily_breach
from research.portfolio.sizing import flat, simulate, throttle

_TRADES = pd.DataFrame(
    {
        "market": ["A", "B", "C"],
        "od": [1, 1, 2],
        "cd": [3, 3, 2],  # C opens AND closes on day 2 (same-day -> must not corrupt the sim)
        "pnl_base": [200.0, -100.0, 75.0],
        "entry": [100.0, 50.0, 20.0],
        "exit": [102.0, 49.0, 20.5],
    }
)
_PRICES = {
    "A": np.array([100.0, 99.0, 99.0, 102.0]),
    "B": np.array([50.0, 50.5, 50.5, 49.0]),
    "C": np.array([20.0, 20.0, 20.5, 20.5]),
}


def test_constant_throttle_reproduces_flat_scaling() -> None:
    # A constant risk_fn must give exactly start + m * base curves (validation of the loop).
    start, m = 200_000.0, 0.5
    realized_base, unreal_base = base_curves(_TRADES, _PRICES, 0, 3)
    equity_base = realized_base + unreal_base
    realized, equity, _sizes, _min = simulate(_TRADES, _PRICES, 0, 3, start, 0.06, flat(m))
    assert np.allclose(realized, start + m * realized_base)
    assert np.allclose(equity, start + m * equity_base)


def test_compound_grows_geometrically_vs_flat() -> None:
    # Two sequential (non-overlapping) winning trades: the second opens AFTER the first realized
    # a gain, so compound sizes it up by equity/start -> compound ends above flat.
    trades = pd.DataFrame(
        {
            "market": ["A", "A"],
            "od": [0, 2],
            "cd": [1, 3],
            "pnl_base": [1000.0, 1000.0],
            "entry": [100.0, 100.0],
            "exit": [110.0, 110.0],
        }
    )
    prices = {"A": np.array([100.0, 110.0, 100.0, 110.0])}
    start, m = 100_000.0, 1.0
    flat_real, _e, _s, _mn = simulate(trades, prices, 0, 3, start, 0.06, flat(m), compound=False)
    comp_real, _e2, sizes, _mn2 = simulate(
        trades, prices, 0, 3, start, 0.06, flat(m), compound=True
    )
    assert comp_real[-1] > flat_real[-1]  # the grown equity compounded the second trade
    assert sizes[1] > m  # the later trade was sized up (equity/start = 1.01)


def test_throttle_policy_shape() -> None:
    fn = throttle(2.0, floor_frac=0.15)
    assert math.isclose(fn(0.0), 2.0)  # fresh buffer -> full base risk
    assert math.isclose(fn(0.5), 1.0)  # half budget used -> half risk
    assert math.isclose(fn(1.0), 0.3)  # at the wall -> floor (2.0 * 0.15)


def test_the_intraday_low_reveals_a_breach_the_close_hides() -> None:
    """#15: a day that dips through the daily limit and recovers by the close breaches live.

    One long, held over a day whose LOW is far below its close. The end-of-day series sees a mild
    day; the worst-mark series sees the real dip. The gate must read the latter.
    """
    trades = pd.DataFrame(
        {
            "market": ["X"],
            "od": [0], "cd": [3],
            "pnl_base": [-2_000.0],  # a mild 2% loser overall
            "entry": [100.0], "exit": [98.0],
            "is_long": [True],
        }
    )
    # End of day the path is gentle: no single close-to-close drop is near the 3% limit.
    closes = {"X": np.array([100.0, 99.5, 99.0, 98.0])}
    # But day 1 dipped to 94 intraday (6% of equity) before recovering to 99.5 by the close.
    lows = {"X": np.array([100.0, 94.0, 99.0, 98.0])}
    highs = {"X": np.array([100.0, 100.0, 100.0, 100.0])}

    _r, eq, _s, min_eq = simulate(
        trades, closes, 0, 3, 100_000.0, 0.06, flat(1.0), adverse=(lows, highs)
    )
    # On day 1 the close-based mark is mild, the intraday mark is far worse.
    assert min_eq[1] < eq[1]
    assert daily_breach(min_eq, 0.03, prior=eq)  # the real dip breaches the 3% daily limit
    assert not daily_breach(eq, 0.03)  # end-of-day alone saw nothing


def test_a_trade_that_dips_and_closes_the_same_day_still_counts_as_a_breach() -> None:
    """Codex P1: closers were realized and removed from open_set BEFORE the intraday mark was
    computed, so a trade that dipped through the daily limit and then closed was invisible to the
    gate -- a false pass for exactly the closing-day and same-day trades."""
    trades = pd.DataFrame(
        {
            "market": ["X"],
            "od": [1], "cd": [1],  # opens AND closes on day 1
            "pnl_base": [-500.0],  # ends the day only mildly down
            "entry": [100.0], "exit": [99.5],
            "is_long": [True],
        }
    )
    closes = {"X": np.array([100.0, 99.5, 99.5, 99.5])}
    lows = {"X": np.array([100.0, 94.0, 99.5, 99.5])}  # dipped to 94 before closing at 99.5
    highs = {"X": np.array([100.0, 100.0, 100.0, 100.0])}

    _r, eq, _s, min_eq = simulate(
        trades, closes, 0, 3, 100_000.0, 0.06, flat(1.0), adverse=(lows, highs)
    )
    assert min_eq[1] < eq[1]  # the dip is visible even though the trade closed that day
    assert daily_breach(min_eq, 0.03, prior=_r)  # and it breaches the 3% daily limit


def test_the_day_axis_is_the_prop_loss_day_not_utc_midnight() -> None:
    """Codex P1: the daily-limit maths bucketed by UTC calendar day while the account's day resets
    at 16:15 America/Chicago, so an adverse evening move was measured against the wrong day's
    baseline. Trades and the price series must share this one axis."""
    from live.runner import loss_day
    from research.portfolio.curves import to_calendar_day, to_day

    # 21:14 UTC on 1 July 2026 is 16:14 CDT -- still the old loss day; 21:16 UTC is 16:16, the new.
    before = pd.Timestamp("2026-07-01 21:14", tz="UTC")
    after = pd.Timestamp("2026-07-01 21:16", tz="UTC")
    assert to_day(after.value) == to_day(before.value) + 1  # rolls at the CT reset ...
    assert to_calendar_day(after.value) == to_calendar_day(before.value)  # ... not at UTC midnight
    # And it agrees with the live runner, so research and live cannot drift on the boundary.
    assert to_day(after.value) - to_day(before.value) == (
        loss_day(after.to_pydatetime()) - loss_day(before.to_pydatetime())
    ).days


def test_the_first_simulated_day_is_checked_for_a_breach() -> None:
    """Codex P1: comparing consecutive entries never tested day 0 against anything, so a
    simulation whose FIRST loss day dipped through the limit reported no breach at all."""
    # Day 0 dips to 96k intraday (4% below the 100k opening balance) and closes at 98k.
    worst = np.array([96_000.0, 98_000.0, 98_000.0])
    prior = np.array([98_000.0, 98_000.0, 98_000.0])  # the day's CLOSING balances
    assert daily_breach(worst, 0.03, prior=prior, start_balance=100_000.0)
    # Measured against day 0's own close (98k) the dip is only 2% -- which is why the opening
    # balance has to be supplied; otherwise the first day is judged against its own outcome.
    assert not daily_breach(worst, 0.03, prior=prior)


def test_the_trailing_floor_also_reads_the_intraday_mark() -> None:
    """Codex P1: an intraday dip below the trailing floor that recovers by the close is still a
    prop-rule breach; testing it on close-based equity reported it as OK."""
    from research.portfolio.drawdown import evaluate

    realized = np.array([100_000.0, 100_000.0])
    close_equity = np.array([100_000.0, 99_000.0])  # gentle at the close
    intraday_low = np.array([100_000.0, 93_000.0])  # but dipped below the 95k floor (5% of 100k)
    assert not evaluate(close_equity, realized, 100_000.0, 0.05).breached
    assert evaluate(intraday_low, realized, 100_000.0, 0.05).breached


def test_a_legacy_stream_infers_direction_from_the_outcome_too() -> None:
    """Codex P2: `exit > entry` alone calls every LOSING long a short, which then marks it at the
    day's high instead of its low -- hiding exactly the intraday breach the mark exists to find."""
    # A losing long: bought at 100, stopped at 99. No is_long column (legacy stream).
    trades = pd.DataFrame(
        {"market": ["X"], "od": [1], "cd": [1], "pnl_base": [-1_000.0],
         "entry": [100.0], "exit": [99.0]}
    )
    closes = {"X": np.array([100.0, 99.0, 99.0])}
    lows = {"X": np.array([100.0, 90.0, 99.0])}  # dipped hard -- the LOW is the adverse side
    highs = {"X": np.array([100.0, 101.0, 101.0])}
    _r, eq, _s, min_eq = simulate(
        trades, closes, 0, 2, 100_000.0, 0.06, flat(1.0), adverse=(lows, highs)
    )
    assert min_eq[1] < eq[1]  # marked at the low, as a long should be
