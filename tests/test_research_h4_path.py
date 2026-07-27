"""Behavioural guards for synchronized H4 portfolio-risk reconstruction."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from research.portfolio.curves import interval_loss_days, load_h4_prices, to_day
from research.portfolio.risk import AccountProfile, FlatRisk, evaluate_policy
from research.portfolio.sizing import DailyDiagnostics, flat, simulate
from research.portfolio.trades import timed_trades_from_report

_HOUR_NS = 3_600_000_000_000


def _ts(value: str) -> int:
    return int(pd.Timestamp(value, tz="UTC").value)


def _h4(*rows: tuple[int, str, str, str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp_ns": [row[0] for row in rows],
            "low": [Decimal(row[1]) for row in rows],
            "high": [Decimal(row[2]) for row in rows],
            "close": [Decimal(row[3]) for row in rows],
        }
    )


def _run(
    trades: pd.DataFrame,
    h4_prices: dict[str, pd.DataFrame],
    *,
    d0: int | None = None,
    d1: int | None = None,
    risk_multiple: float = 1.0,
    daily_limit_frac: float = 0.03,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, DailyDiagnostics]:
    opened = trades["ts_opened"].to_numpy(dtype=np.int64)
    closed = trades["ts_closed"].to_numpy(dtype=np.int64)
    t = trades.copy()
    t["od"] = [to_day(int(value)) for value in opened]
    t["cd"] = [to_day(int(value)) for value in closed]
    first = min(t["od"]) if d0 is None else d0
    last = max(t["cd"]) if d1 is None else d1
    closes = {
        market: np.full(
            last - first + 1,
            float(rows["close"].iloc[-1]) if "close" in rows else 100.0,
        )
        for market, rows in h4_prices.items()
    }
    return simulate(
        t,
        closes,
        first,
        last,
        100_000.0,
        0.06,
        flat(risk_multiple),
        h4_prices=h4_prices,
        daily_limit_frac=daily_limit_frac,
    )


def _trade(
    market: str,
    opened: int,
    closed: int,
    *,
    pnl_base: float = 1_000.0,
    entry: float = 100.0,
    exit_: float = 99.0,
    swap_base: float = 0.0,
) -> dict[str, object]:
    return {
        "market": market,
        "ts_opened": opened,
        "ts_closed": closed,
        "pnl_base": pnl_base,
        "entry": entry,
        "exit": exit_,
        "is_long": False,
        "swap_base": swap_base,
    }


def test_extracted_entry_side_drives_long_low_and_short_high() -> None:
    opened = pd.Timestamp("2025-04-10 05:00", tz="UTC")
    closed = pd.Timestamp("2025-04-10 09:00", tz="UTC")
    report = pd.DataFrame(
        {
            "ts_opened": [opened, opened],
            "ts_closed": [closed, closed],
            "realized_pnl": ["1000.0 USD", "1000.0 USD"],
            "avg_px_open": [100.0, 100.0],
            "avg_px_close": [110.0, 90.0],
            "entry": ["BUY", "SELL"],
            "side": ["FLAT", "FLAT"],
        }
    )
    trades = pd.DataFrame(timed_trades_from_report(report, "X", sl_pct=1.0))
    bars = {
        "X": _h4(
            (_ts("2025-04-10 05:00"), "90", "110", "100"),
        )
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert trades["is_long"].tolist() == [True, False]
    assert diagnostics.minimum_equity[0] == pytest.approx(98_000.0)


def test_loss_day_interval_is_half_open_and_rejects_empty_ranges() -> None:
    before_reset = _ts("2026-07-01 21:00")
    reset = _ts("2026-07-01 21:15")
    after_reset = before_reset + 4 * _HOUR_NS

    assert interval_loss_days(before_reset, before_reset) == ()
    assert interval_loss_days(after_reset, before_reset) == ()
    assert interval_loss_days(before_reset, after_reset) == (
        to_day(before_reset),
        to_day(after_reset),
    )
    assert interval_loss_days(before_reset, reset) == (to_day(before_reset),)
    assert interval_loss_days(reset, reset + 1) == (to_day(reset),)


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        (
            "2026.07.02\t00:00:00\t99\t101\t100\n2026.07.02\t00:00:00\t99\t101\t100\n",
            "duplicate H4 timestamps",
        ),
        (
            "2026.07.02\t04:00:00\t99\t101\t100\n2026.07.02\t00:00:00\t99\t101\t100\n",
            "not strictly increasing",
        ),
        ("2026.07.02\t00:00:00\tnan\t101\t100\n", "non-finite H4 price"),
        ("2026.07.02\t00:00:00\t99\tnan\t100\n", "non-finite H4 price"),
        ("2026.07.02\t00:00:00\t99\t101\tnan\n", "non-finite H4 price"),
    ],
)
def test_h4_loader_fails_closed_on_invalid_rows(tmp_path: Path, rows: str, message: str) -> None:
    csv = tmp_path / "X_H4.csv"
    csv.write_text(
        "<DATE>\t<TIME>\t<LOW>\t<HIGH>\t<CLOSE>\n" + rows,
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        load_h4_prices(str(csv))


def test_h4_loader_accepts_one_complete_observation(tmp_path: Path) -> None:
    csv = tmp_path / "X_H4.csv"
    csv.write_text(
        "<DATE>\t<TIME>\t<LOW>\t<HIGH>\t<CLOSE>\n2026.07.02\t00:00:00\t99\t101\t100\n",
        encoding="utf-8",
    )

    loaded = load_h4_prices(str(csv))

    assert loaded[["low", "high", "close"]].iloc[0].tolist() == [
        Decimal("99"),
        Decimal("101"),
        Decimal("100"),
    ]


@pytest.mark.parametrize(
    ("frame", "message"),
    [
        (
            pd.DataFrame({"timestamp_ns": [1], "low": [99], "high": [101]}),
            "missing columns",
        ),
        (
            _h4((2, "99", "101", "100"), (1, "99", "101", "100")),
            "strictly increasing",
        ),
        (
            _h4((1, "99", "101", "100"), (1, "99", "101", "100")),
            "strictly increasing",
        ),
        (_h4((1, "nan", "101", "100")), "non-finite H4 prices"),
        (_h4((1, "99", "nan", "100")), "non-finite H4 prices"),
        (_h4((1, "99", "101", "nan")), "non-finite H4 prices"),
        (_h4((1, "102", "101", "100")), "invalid H4 OHLC bounds"),
        (_h4((1, "99", "101", "102")), "invalid H4 OHLC bounds"),
    ],
)
def test_h4_replay_fails_closed_on_invalid_market_frames(frame: pd.DataFrame, message: str) -> None:
    opened = 0
    closed = 4 * _HOUR_NS
    trades = pd.DataFrame([_trade("X", opened, closed)])

    with pytest.raises(ValueError, match=message):
        _run(trades, {"X": frame})


@pytest.mark.parametrize(
    "frame",
    [
        _h4((0, "100", "100", "100")),
        _h4((0, "99", "100", "100")),
    ],
)
def test_equal_h4_bounds_are_valid(frame: pd.DataFrame) -> None:
    trades = pd.DataFrame([_trade("X", 0, 4 * _HOUR_NS)])

    _realized, _equity, _sizes, diagnostics = _run(trades, {"X": frame})

    assert diagnostics.minimum_equity[0] == pytest.approx(100_000.0)


def test_trade_uses_only_h4_observations_inside_its_lifetime() -> None:
    opened = _ts("2025-04-10 13:00")
    closed = _ts("2025-04-10 17:00")
    trades = pd.DataFrame([_trade("X", opened, closed)])
    bars = {
        "X": _h4(
            (_ts("2025-04-10 01:00"), "99", "120", "100"),
            (opened, "98.8", "100.2", "99"),
            (closed, "90", "140", "95"),
        )
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_800.0)
    assert diagnostics.h4_upper_bound


def test_same_observation_short_never_consumes_a_later_high() -> None:
    bar_start = _ts("2025-04-10 13:00")
    opened = bar_start + _HOUR_NS // 2
    closed = bar_start + 7 * _HOUR_NS // 2
    trades = pd.DataFrame([_trade("X", opened, closed)])
    bars = {
        "X": _h4(
            (bar_start, "98.8", "100.2", "99"),
            (bar_start + 4 * _HOUR_NS, "90", "140", "95"),
        )
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_800.0)
    assert diagnostics.daily_loss[0] == pytest.approx(0.002)


def test_legacy_direction_inference_treats_any_positive_pnl_as_a_win() -> None:
    opened = _ts("2025-04-10 05:00")
    closed = _ts("2025-04-10 09:00")
    trade = _trade("X", opened, closed, pnl_base=0.5)
    del trade["is_long"]

    _realized, _equity, _sizes, diagnostics = _run(
        pd.DataFrame([trade]),
        {"X": _h4((opened, "99", "101", "99"))},
    )

    assert diagnostics.minimum_equity[0] == pytest.approx(99_999.5)


def test_explicit_direction_overrides_legacy_pnl_inference() -> None:
    opened = _ts("2025-04-10 05:00")
    closed = _ts("2025-04-10 09:00")
    trade = _trade(
        "X",
        opened,
        closed,
        pnl_base=-1_000.0,
        entry=100.0,
        exit_=101.0,
    )
    trade["is_long"] = True

    _realized, _equity, _sizes, diagnostics = _run(
        pd.DataFrame([trade]),
        {"X": _h4((opened, "99", "102", "101"))},
    )

    assert diagnostics.minimum_equity[0] == pytest.approx(99_000.0)


def test_legacy_equal_entry_exit_keeps_the_strict_direction_boundary() -> None:
    opened = _ts("2025-04-10 05:00")
    closed = _ts("2025-04-10 09:00")
    trade = _trade(
        "X",
        opened,
        closed,
        pnl_base=1_000.0,
        entry=100.0,
        exit_=100.0,
    )
    del trade["is_long"]

    _realized, _equity, _sizes, diagnostics = _run(
        pd.DataFrame([trade]),
        {"X": _h4((opened, "99", "100", "100"))},
    )

    assert diagnostics.minimum_equity[0] == pytest.approx(100_000.0)


@pytest.mark.parametrize(
    ("entry", "exit_", "high", "expected"),
    [
        (100.0, 100.0, "101", 99_000.0),
        (0.0, 1e-12, "0.000000000002", 98_000.0),
    ],
)
def test_zero_and_exact_epsilon_price_spans_are_explicit(
    entry: float, exit_: float, high: str, expected: float
) -> None:
    opened = _ts("2025-04-10 05:00")
    closed = _ts("2025-04-10 09:00")
    trades = pd.DataFrame(
        [
            _trade(
                "X",
                opened,
                closed,
                pnl_base=-1_000.0,
                entry=entry,
                exit_=exit_,
            )
        ]
    )

    _realized, _equity, _sizes, diagnostics = _run(
        trades,
        {"X": _h4((opened, "0", high, str(exit_)))},
    )

    assert diagnostics.minimum_equity[0] == pytest.approx(expected)


def test_different_h4_intervals_do_not_sum_adverse_extremes() -> None:
    t05 = _ts("2025-04-10 05:00")
    t09 = _ts("2025-04-10 09:00")
    t13 = _ts("2025-04-10 13:00")
    trades = pd.DataFrame(
        [
            _trade("A", t05, t09),
            _trade("B", t09, t13),
        ]
    )
    bars = {
        "A": _h4((t05, "99", "100.2", "99")),
        "B": _h4((t09, "99", "100.2", "99")),
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_800.0)


def test_same_h4_interval_sums_contemporaneous_adverse_marks() -> None:
    t05 = _ts("2025-04-10 05:00")
    t09 = _ts("2025-04-10 09:00")
    trades = pd.DataFrame(
        [
            _trade("A", t05, t09),
            _trade("B", t05, t09),
        ]
    )
    bars = {
        "A": _h4((t05, "99", "100.2", "99")),
        "B": _h4((t05, "99", "100.2", "99")),
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_600.0)
    assert diagnostics.h4_upper_bound == (
        "H4 upper bound: contemporaneous positions may hit their direction-adverse "
        "extremes within the same H4 interval"
    )


def test_disjoint_lifetimes_inside_one_h4_bar_are_not_summed() -> None:
    bar_start = _ts("2025-04-10 05:00")
    boundary = bar_start + 2 * _HOUR_NS
    bar_end = bar_start + 4 * _HOUR_NS
    trades = pd.DataFrame(
        [
            _trade("A", bar_start, boundary),
            _trade("B", boundary, bar_end),
        ]
    )
    bars = {
        "A": _h4((bar_start, "99", "100.2", "99")),
        "B": _h4((bar_start, "99", "100.2", "99")),
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_800.0)


def test_reset_straddling_bar_is_charged_only_for_an_overlapping_position() -> None:
    bar = _ts("2026-07-01 21:00")
    before = to_day(bar)
    after = to_day(bar + 4 * _HOUR_NS)
    assert after == before + 1
    overlapping = pd.DataFrame([_trade("X", bar, bar + 4 * _HOUR_NS)])
    non_overlapping = pd.DataFrame([_trade("X", bar, bar)])
    bars = {"X": _h4((bar, "99", "100.2", "99"))}

    *_unused, overlap_diagnostics = _run(overlapping, bars, d0=before, d1=after)
    *_unused2, no_overlap_diagnostics = _run(non_overlapping, bars, d0=before, d1=after)

    assert list(overlap_diagnostics.minimum_equity) == pytest.approx([99_800.0, 99_800.0])
    assert list(no_overlap_diagnostics.minimum_equity) == pytest.approx([100_000.0, 101_000.0])
    assert not no_overlap_diagnostics.daily_loss.any()


def test_swap_is_realized_once_at_close_and_never_in_an_h4_mark() -> None:
    opened = _ts("2025-04-09 13:00")
    observed = _ts("2025-04-10 09:00")
    closed = _ts("2025-04-10 13:00")
    trades = pd.DataFrame([_trade("X", opened, closed, pnl_base=1_000.0, swap_base=-50.0)])
    bars = {"X": _h4((observed, "99", "100.2", "99"))}

    realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[-1] == pytest.approx(99_800.0)
    assert realized[-1] == pytest.approx(100_950.0)
    assert diagnostics.close_balance[-1] == pytest.approx(100_950.0)


def test_closed_swap_changes_every_later_synchronized_mark_once() -> None:
    t05 = _ts("2025-04-10 05:00")
    t09 = _ts("2025-04-10 09:00")
    t13 = _ts("2025-04-10 13:00")
    trades = pd.DataFrame(
        [
            _trade("A", t05, t09, pnl_base=0.0, swap_base=-50.0),
            _trade("B", t05, t13),
        ]
    )
    bars = {
        "A": _h4((t05, "100", "100", "100")),
        "B": _h4(
            (t05, "100", "100", "100"),
            (t09, "99", "100.2", "99"),
        ),
    }

    _realized, _equity, _sizes, diagnostics = _run(
        trades,
        bars,
        risk_multiple=0.5,
    )

    # A's -25 sized swap is realized at 09:00 before B's -100 sized adverse mark.
    assert diagnostics.minimum_equity[0] == pytest.approx(99_875.0)


def test_daily_and_trailing_flags_share_the_minimum_equity_path() -> None:
    opened = _ts("2025-04-10 05:00")
    closed = _ts("2025-04-10 09:00")
    trades = pd.DataFrame([_trade("X", opened, closed)])
    bars = {"X": _h4((opened, "99", "104", "99"))}

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.opening_balance[0] == pytest.approx(100_000.0)
    assert diagnostics.close_balance[0] == pytest.approx(101_000.0)
    assert diagnostics.close_equity[0] == pytest.approx(101_000.0)
    assert diagnostics.minimum_equity[0] == pytest.approx(96_000.0)
    assert diagnostics.daily_loss[0] == pytest.approx(0.04)
    assert diagnostics.days[0] == to_day(opened)
    assert diagnostics.trailing_floor[0] == pytest.approx(95_000.0)
    assert diagnostics.daily_breach[0]
    assert not diagnostics.trailing_breach[0]
    assert diagnostics.breached


def test_zero_daily_limit_disables_daily_breach_flags() -> None:
    opened = _ts("2025-04-10 05:00")
    closed = _ts("2025-04-10 09:00")
    trades = pd.DataFrame([_trade("X", opened, closed)])

    *_unused, diagnostics = _run(
        trades,
        {"X": _h4((opened, "99", "104", "99"))},
        daily_limit_frac=0.0,
    )

    assert diagnostics.daily_loss[0] == pytest.approx(0.04)
    assert not diagnostics.daily_breach.any()


def test_closed_market_carries_last_close_without_borrowing_an_extreme() -> None:
    t05 = _ts("2025-04-10 05:00")
    t09 = _ts("2025-04-10 09:00")
    t13 = _ts("2025-04-10 13:00")
    trades = pd.DataFrame(
        [
            _trade("A", t05, t13),
            _trade("B", t05, t13),
        ]
    )
    bars = {
        "A": _h4((t05, "99", "100.2", "99"), (t09, "99", "100.2", "99")),
        "B": _h4((t05, "99", "100", "99.5")),
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_800.0)


def test_closed_market_carry_changes_the_synchronized_minimum() -> None:
    t05 = _ts("2025-04-10 05:00")
    t09 = _ts("2025-04-10 09:00")
    t13 = _ts("2025-04-10 13:00")
    trades = pd.DataFrame([_trade("A", t05, t13), _trade("B", t05, t13)])
    bars = {
        "A": _h4((t09, "99", "100.2", "99")),
        "B": _h4((t05, "97", "100", "98")),
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    # B's 98 close is +2R when A first becomes adverse. Carrying entry instead would create
    # a spurious 200-money loss and make the minimum 99,800.
    assert diagnostics.minimum_equity[0] == pytest.approx(100_000.0)


def test_prior_realized_closes_accumulate_before_a_later_h4_mark() -> None:
    t05 = _ts("2025-04-10 05:00")
    t09 = _ts("2025-04-10 09:00")
    t13 = _ts("2025-04-10 13:00")
    t17 = _ts("2025-04-10 17:00")
    trades = pd.DataFrame(
        [
            _trade("A", t05, t09),
            _trade("B", t05, t13),
            _trade("C", t05, t17),
        ]
    )
    bars = {
        "A": _h4((t05, "99", "100", "99")),
        "B": _h4((t05, "99", "100", "99"), (t09, "99", "100", "99")),
        "C": _h4(
            (t05, "99", "100", "99"),
            (t09, "99", "100", "99"),
            (t13, "99", "102.5", "99"),
        ),
    }

    _realized, _equity, _sizes, diagnostics = _run(trades, bars)

    assert diagnostics.minimum_equity[0] == pytest.approx(99_500.0)


def test_exact_daily_and_trailing_boundaries_keep_declared_strictness() -> None:
    opened = _ts("2025-04-10 05:00")
    closed = _ts("2025-04-10 09:00")
    trades = pd.DataFrame([_trade("X", opened, closed)])

    *_unused, daily_exact = _run(
        trades,
        {"X": _h4((opened, "99", "103", "99"))},
    )
    *_unused2, trailing_exact = _run(
        trades,
        {"X": _h4((opened, "99", "105", "99"))},
    )

    assert daily_exact.daily_loss[0] == pytest.approx(0.03)
    assert not daily_exact.daily_breach[0]
    assert trailing_exact.minimum_equity[0] == pytest.approx(trailing_exact.trailing_floor[0])
    assert trailing_exact.trailing_breach[0]


@pytest.mark.parametrize("missing", ["ts_opened", "ts_closed"])
def test_h4_replay_names_a_missing_trade_timestamp(missing: str) -> None:
    opened = _ts("2025-04-10 05:00")
    closed = _ts("2025-04-10 09:00")
    trades = pd.DataFrame([_trade("X", opened, closed)]).drop(columns=missing)
    trades["od"] = to_day(opened)
    trades["cd"] = to_day(closed)
    bars = {"X": _h4((opened, "99", "100.2", "99"))}

    with pytest.raises(ValueError) as exc_info:
        simulate(
            trades,
            {"X": np.array([99.0])},
            to_day(opened),
            to_day(closed),
            100_000.0,
            0.06,
            flat(1.0),
            h4_prices=bars,
        )
    assert str(exc_info.value) == (
        "synchronized H4 reconstruction requires ts_opened and ts_closed"
    )


def test_wholly_missing_h4_lifetime_evidence_fails_closed() -> None:
    t05 = _ts("2025-04-10 05:00")
    t09 = _ts("2025-04-10 09:00")
    trades = pd.DataFrame(
        [
            _trade("A", t05, t09),
            _trade("B", t05, t09),
        ]
    )
    bars = {
        "A": _h4((t05, "99", "100.2", "99")),
        "B": _h4((_ts("2025-04-10 13:00"), "99", "100.2", "99")),
    }

    with pytest.raises(ValueError, match="no H4 observation overlaps B trade 1"):
        _run(trades, bars)


def test_synthetic_retired_structure_replaces_impossible_whole_day_breach() -> None:
    stamps = [
        _ts("2025-04-10 05:00"),
        _ts("2025-04-10 09:00"),
        _ts("2025-04-10 13:00"),
    ]
    returns = [6.14, 4.11, 3.08, 2.00, -1.00, -1.00]
    rows: list[dict[str, object]] = []
    bars: dict[str, pd.DataFrame] = {}
    legacy_worst = Decimal("0")
    risk_multiple = Decimal("0.15")
    per_trade_legacy_loss = Decimal("3200") / Decimal(6)
    for index, result_r in enumerate(returns):
        market = f"M{index}"
        observed = stamps[index // 2]
        opened = observed - 4 * _HOUR_NS
        pnl_base = Decimal(str(result_r)) * Decimal("1000")
        exit_price = Decimal("99") if result_r > 0 else Decimal("101")
        span = exit_price - Decimal("100")
        actual_loss = Decimal("185")
        actual_high = Decimal("100") + actual_loss * abs(span) / (abs(pnl_base) * risk_multiple)
        later_high = Decimal("100") + per_trade_legacy_loss * abs(span) / (
            abs(pnl_base) * risk_multiple
        )
        rows.append(
            _trade(
                market,
                opened,
                observed,
                pnl_base=float(pnl_base),
                exit_=float(exit_price),
            )
        )
        bars[market] = _h4(
            (opened, "99", str(actual_high), str(exit_price)),
            (_ts("2025-04-10 17:00"), "99", str(later_high), str(exit_price)),
        )
        fraction = (later_high - Decimal("100")) / span
        legacy_worst += pnl_base * risk_multiple * fraction
    trades = pd.DataFrame(rows)

    _realized, equity, _sizes, diagnostics = _run(trades, bars, risk_multiple=0.15)
    whole_day_loss = float(-legacy_worst / Decimal("100000"))

    assert whole_day_loss == pytest.approx(0.032)
    assert equity[-1] > 100_000.0
    assert 0.0030 <= diagnostics.daily_loss.max() <= 0.0045
    assert not diagnostics.daily_breach.any()


def test_h4_path_changes_leave_every_non_path_policy_statistic_exact() -> None:
    opened = _ts("2025-04-10 05:00")
    closed = _ts("2025-04-10 09:00")
    day = to_day(opened)
    trades = pd.DataFrame(
        {
            "market": ["X"],
            "ts_opened": [opened],
            "ts_closed": [closed],
            "entry": [100.0],
            "exit": [99.0],
            "is_long": [False],
            "r": [2.0],
            "swap_r": [-0.1],
        }
    )
    daily_close = {"X": pd.Series([99.0], index=[day])}
    mild = {"X": _h4((opened, "98.9", "100.2", "99"))}
    severe = {"X": _h4((opened, "98.9", "104", "99"))}
    account = AccountProfile(start_balance=100_000.0, base_risk_frac=0.01)

    mild_result = evaluate_policy(
        trades, daily_close, account, FlatRisk(0.15), 0.02, h4_prices=mild
    )
    severe_result = evaluate_policy(
        trades, daily_close, account, FlatRisk(0.15), 0.02, h4_prices=severe
    )

    for field in (
        "label",
        "ceiling_pct",
        "floor_pct",
        "n_trades",
        "years",
        "total_return_pct",
        "ann_return_pct",
        "ann_return_eur",
    ):
        assert getattr(mild_result, field) == getattr(severe_result, field)
    np.testing.assert_array_equal(mild_result.trade_pnl, severe_result.trade_pnl)
    np.testing.assert_array_equal(mild_result.trade_swap, severe_result.trade_swap)
    np.testing.assert_array_equal(
        mild_result.daily_diagnostics.close_balance,
        severe_result.daily_diagnostics.close_balance,
    )
    np.testing.assert_array_equal(
        mild_result.daily_diagnostics.close_equity,
        severe_result.daily_diagnostics.close_equity,
    )
    assert mild_result.max_drawdown_pct != severe_result.max_drawdown_pct


def test_drawdown_does_not_use_a_later_profitable_close_as_its_peak() -> None:
    opened = _ts("2026-07-02 00:00")
    closed = opened + 4 * _HOUR_NS
    trades = pd.DataFrame(
        [
            {
                **_trade(
                    "X",
                    opened,
                    closed,
                    pnl_base=10_000.0,
                    entry=100.0,
                    exit_=110.0,
                ),
                "is_long": True,
            }
        ]
    )
    prices = {"X": _h4((opened, "99", "110", "110"))}

    *_unused, diagnostics = _run(trades, prices)

    assert diagnostics.minimum_equity.min() == pytest.approx(99_000.0)
    assert diagnostics.close_equity[-1] == pytest.approx(110_000.0)
    assert diagnostics.max_drawdown_pct == -1.0


def test_drawdown_uses_an_observable_h4_close_before_a_later_minimum() -> None:
    opened = _ts("2026-07-02 00:00")
    closed = opened + 8 * _HOUR_NS
    trades = pd.DataFrame(
        [
            {
                **_trade(
                    "X",
                    opened,
                    closed,
                    pnl_base=10_000.0,
                    entry=100.0,
                    exit_=110.0,
                ),
                "is_long": True,
            }
        ]
    )
    prices = {
        "X": _h4(
            (opened, "100", "110", "110"),
            (opened + 4 * _HOUR_NS, "109", "111", "110"),
        )
    }

    *_unused, diagnostics = _run(trades, prices)

    assert diagnostics.minimum_equity.min() == pytest.approx(100_000.0)
    assert diagnostics.close_equity[-1] == pytest.approx(110_000.0)
    assert diagnostics.max_drawdown_pct == -0.91


def test_observable_h4_close_can_exceed_the_daily_close_only_hwm() -> None:
    opened = _ts("2026-07-02 00:00")
    later_bar = opened + 28 * _HOUR_NS
    trades = pd.DataFrame(
        [
            {
                **_trade(
                    "X",
                    opened,
                    opened + 8 * _HOUR_NS,
                    pnl_base=9_500.0,
                    entry=100.0,
                    exit_=109.5,
                ),
                "is_long": True,
            },
            {
                **_trade(
                    "X",
                    later_bar,
                    later_bar + 4 * _HOUR_NS,
                    pnl_base=1_000.0,
                    entry=100.0,
                    exit_=110.0,
                ),
                "is_long": True,
            },
        ]
    )
    prices = {
        "X": _h4(
            # The 120 high is unknowable within the interval and must not become the HWM.
            # The 110 close is observable before every later mark and therefore must.
            (opened, "100", "120", "110"),
            (opened + 4 * _HOUR_NS, "109.5", "110", "109.5"),
            (later_bar, "95", "100", "100"),
        )
    }

    *_unused, diagnostics = _run(trades, prices)
    daily_close_only = replace(diagnostics, chronological_drawdown=None)

    assert diagnostics.max_drawdown_pct == -0.91
    assert daily_close_only.max_drawdown_pct == -0.46


def test_pre_entry_market_close_cannot_create_a_position_drawdown_peak() -> None:
    first_bar = _ts("2026-07-02 00:00")
    opened = first_bar + 4 * _HOUR_NS
    closed = opened + 4 * _HOUR_NS
    trades = pd.DataFrame(
        [
            {
                **_trade(
                    "X",
                    opened,
                    closed,
                    pnl_base=10_000.0,
                    entry=100.0,
                    exit_=110.0,
                ),
                "is_long": True,
            }
        ]
    )
    prices = {
        "X": _h4(
            (first_bar, "120", "120", "120"),
            (opened, "100", "110", "110"),
        )
    }

    *_unused, diagnostics = _run(trades, prices)

    assert diagnostics.minimum_equity.min() == pytest.approx(100_000.0)
    assert diagnostics.max_drawdown_pct == 0.0
