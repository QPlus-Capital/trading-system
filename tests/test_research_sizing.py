"""Tests for the sizing policies (flat vs drawdown-throttle)."""

import math
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
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
    opened = pd.Timestamp("2025-04-09 13:00", tz="UTC").value
    observed = pd.Timestamp("2025-04-10 09:00", tz="UTC").value
    closed = pd.Timestamp("2025-04-10 13:00", tz="UTC").value
    from research.portfolio.curves import to_day

    trades = pd.DataFrame(
        {
            "market": ["X"],
            "od": [to_day(opened)],
            "cd": [to_day(closed)],
            "ts_opened": [opened],
            "ts_closed": [closed],
            "pnl_base": [-2_000.0],  # a mild 2% loser overall
            "entry": [100.0],
            "exit": [98.0],
            "is_long": [True],
        }
    )
    d0, d1 = int(trades["od"].min()), int(trades["cd"].max())
    closes = {"X": np.linspace(100.0, 98.0, d1 - d0 + 1)}
    h4 = {
        "X": pd.DataFrame(
            {
                "timestamp_ns": [observed, closed],
                "low": [94, 98],
                "high": [100, 100],
                "close": [99.5, 98],
            }
        )
    }

    _r, eq, _s, diagnostics = simulate(
        trades,
        closes,
        d0,
        d1,
        100_000.0,
        0.06,
        flat(1.0),
        h4_prices=h4,
        daily_limit_frac=0.03,
    )
    # On day 1 the close-based mark is mild, the intraday mark is far worse.
    assert diagnostics.minimum_equity.min() < eq.min()
    assert diagnostics.daily_breach.any()
    assert not daily_breach(eq, 0.03)  # end-of-day alone saw nothing


def test_a_trade_that_dips_and_closes_the_same_day_still_counts_as_a_breach() -> None:
    """Codex P1: closers were realized and removed from open_set BEFORE the intraday mark was
    computed, so a trade that dipped through the daily limit and then closed was invisible to the
    gate -- a false pass for exactly the closing-day and same-day trades."""
    opened = pd.Timestamp("2025-04-10 05:00", tz="UTC").value
    closed = pd.Timestamp("2025-04-10 09:00", tz="UTC").value
    from research.portfolio.curves import to_day

    trades = pd.DataFrame(
        {
            "market": ["X"],
            "od": [to_day(opened)],
            "cd": [to_day(closed)],
            "ts_opened": [opened],
            "ts_closed": [closed],
            "pnl_base": [-500.0],  # ends the day only mildly down
            "entry": [100.0],
            "exit": [99.5],
            "is_long": [True],
        }
    )
    d0 = to_day(opened)
    closes = {"X": np.array([99.5])}
    h4 = {
        "X": pd.DataFrame({"timestamp_ns": [opened], "low": [94], "high": [100], "close": [99.5]})
    }

    _r, eq, _s, diagnostics = simulate(
        trades,
        closes,
        d0,
        d0,
        100_000.0,
        0.06,
        flat(1.0),
        h4_prices=h4,
        daily_limit_frac=0.03,
    )
    assert diagnostics.minimum_equity[0] < eq[0]
    assert diagnostics.daily_breach[0]


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
    assert (
        to_day(after.value) - to_day(before.value)
        == (loss_day(after.to_pydatetime()) - loss_day(before.to_pydatetime())).days
    )


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


def test_h4_reconstruction_fails_closed_without_explicit_direction() -> None:
    """A missing categorical direction must never fall back to a trade's outcome."""
    opened = pd.Timestamp("2025-04-10 05:00", tz="UTC").value
    closed = pd.Timestamp("2025-04-10 09:00", tz="UTC").value
    from research.portfolio.curves import to_day

    day = to_day(opened)
    trades = pd.DataFrame(
        {
            "market": ["X"],
            "od": [day],
            "cd": [day],
            "ts_opened": [opened],
            "ts_closed": [closed],
            "pnl_base": [-1_000.0],
            "entry": [100.0],
            "exit": [99.0],
        }
    )
    closes = {"X": np.array([99.0])}
    h4 = {"X": pd.DataFrame({"timestamp_ns": [opened], "low": [90], "high": [101], "close": [99]})}
    with pytest.raises(ValueError, match="requires an explicit is_long column"):
        simulate(trades, closes, day, day, 100_000.0, 0.06, flat(1.0), h4_prices=h4)


def test_a_morning_close_updates_the_balance_before_an_evening_open() -> None:
    """Codex round-5 P1: sorting opens and closes separately still processed ALL opens before
    ANY close. A trade closing at 08:00 must book its loss before a 20:00 open sizes off the
    balance -- otherwise compound/throttle sizing uses equity a morning loss already destroyed."""
    hour_ns = 3_600_000_000_000
    day_ns = 24 * hour_ns
    trades = pd.DataFrame(
        {
            "market": ["A", "A"],
            "od": [0, 1],
            "cd": [1, 2],
            "ts_opened": [0, 1 * day_ns + 20 * hour_ns],  # B opens day 1 at 20:00
            "ts_closed": [1 * day_ns + 8 * hour_ns, 2 * day_ns],  # A closes day 1 at 08:00
            "pnl_base": [-10_000.0, 1_000.0],
            "entry": [100.0, 100.0],
            "exit": [90.0, 101.0],
            "is_long": [True, True],
        }
    )
    # Day 1's close price sits back at A's entry, so the unrealized mark hides the loss --
    # only the REALIZED booking at 08:00 can inform B's sizing.
    prices = {"A": np.array([100.0, 100.0, 101.0])}
    _r, _e, sizes, _m = simulate(trades, prices, 0, 2, 100_000.0, 0.06, flat(1.0), compound=True)
    assert sizes[1] == pytest.approx(0.9)  # sized AFTER the -10k booked: 90k / 100k


def test_a_reset_straddling_bar_charges_its_extremes_to_both_loss_days(
    tmp_path: Path,
) -> None:
    """Codex round-5 P1: the H4 bar stamped 00:00 server (summer) opens 21:00 UTC -- fifteen
    minutes BEFORE the 16:15 CT reset -- and closes after it. Bucketing its low/high only by the
    close time hides a pre-reset dip from the day it happened in. A straddling bar's extremes
    belong to BOTH adjacent loss days; over-charging one bar is the conservative side."""
    from research.portfolio.curves import interval_loss_days, load_h4_prices, to_day

    csv = tmp_path / "X_H4.csv"
    csv.write_text(
        "<DATE>\t<TIME>\t<LOW>\t<HIGH>\t<CLOSE>\n2026.07.02\t00:00:00\t93.0\t101.0\t99.0\n",
        encoding="utf-8",
    )
    bars = load_h4_prices(str(csv))
    d_before = to_day(pd.Timestamp("2026-07-01 21:00", tz="UTC").value)  # pre-reset side
    d_after = to_day(pd.Timestamp("2026-07-02 01:00", tz="UTC").value)  # post-reset side
    assert d_after == d_before + 1  # the bar really does straddle the reset
    assert list(bars["low"]) == [Decimal("93.0")]
    assert list(bars["high"]) == [Decimal("101.0")]
    start = int(bars["timestamp_ns"].iloc[0])
    assert interval_loss_days(start, start + 4 * 3_600_000_000_000) == (d_before, d_after)
