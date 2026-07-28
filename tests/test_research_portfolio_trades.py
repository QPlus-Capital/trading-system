"""Tests for the timed OOS trade-stream extraction (edge -> portfolio)."""

import pandas as pd
import pytest
from research.portfolio.trades import timed_trades_from_report


def _closed_position(entry_side: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_opened": [pd.Timestamp("2024-01-01", tz="UTC")],
            "ts_closed": [pd.Timestamp("2024-01-02", tz="UTC")],
            "realized_pnl": ["10.0 USD"],
            "avg_px_open": [100.0],
            "avg_px_close": [101.0],
            "entry": [entry_side],
            "side": ["FLAT"],
        }
    )


def test_closed_position_uses_entry_side_for_direction() -> None:
    long = timed_trades_from_report(_closed_position("BUY"), "X", sl_pct=1.0)
    short = timed_trades_from_report(_closed_position("SELL"), "X", sl_pct=1.0)

    assert long[0]["is_long"] is True
    assert short[0]["is_long"] is False


def test_unrecognized_entry_side_fails_closed() -> None:
    with pytest.raises(ValueError, match="unrecognized position entry side.*HOLD"):
        timed_trades_from_report(_closed_position("HOLD"), "X", sl_pct=1.0)


def test_extraction_keeps_snapshots_and_skips_open() -> None:
    pos = pd.DataFrame(
        {
            "ts_opened": [
                pd.Timestamp("2020-01-01", tz="UTC"),
                pd.Timestamp("2020-01-05", tz="UTC"),
                pd.Timestamp("2020-01-10", tz="UTC"),
            ],
            "ts_closed": [
                pd.Timestamp("2020-01-03", tz="UTC"),
                pd.Timestamp("2020-01-07", tz="UTC"),
                pd.NaT,  # still open at window end -> skipped
            ],
            "realized_pnl": ["100.5 USD", "-50.0 USD", "0 USD"],
            "avg_px_open": [10.0, 11.0, 12.0],
            "avg_px_close": [10.5, 10.5, 12.0],
            # The report carries the direction; note its "entry" means the entry SIDE, while the
            # extracted "entry" is the entry PRICE.
            "entry": ["BUY", "SELL", "BUY"],
            "side": ["FLAT", "FLAT", "LONG"],
            "is_snapshot": [True, False, False],  # a snapshot round-trip is still a real trade
        }
    )
    trades = timed_trades_from_report(pos, "X", sl_pct=1.5)
    assert len(trades) == 2  # the open position is skipped; the snapshot is kept
    assert trades[0]["market"] == "X"
    assert trades[0]["pnl_base"] == 100.5
    assert trades[0]["entry"] == 10.0
    assert trades[0]["exit"] == 10.5
    assert trades[0]["sl_pct"] == 1.5
    # Direction is taken from the report, not inferred: trade 1 is a SHORT that lost, which the
    # outcome-based inference would have read as a long.
    assert trades[0]["is_long"] is True
    assert trades[1]["is_long"] is False
    assert trades[0]["ts_opened"] == pd.Timestamp("2020-01-01", tz="UTC").value
    assert trades[1]["pnl_base"] == -50.0


def test_a_trade_carried_across_a_boundary_is_kept_by_the_window_that_resolves_it() -> None:
    """#14: a position opened before the window and stopped out inside it is REAL -- live realises
    that loss. It used to vanish (opened in the previous window, still open at its end -> dropped;
    never seen by the next). The pre-roll plus closed_from attributes it to the window it
    resolved in, exactly once."""
    pos = pd.DataFrame(
        {
            "ts_opened": [
                pd.Timestamp("2024-01-20", tz="UTC"),  # before the window (in the pre-roll)
                pd.Timestamp("2024-02-10", tz="UTC"),
            ],
            "ts_closed": [
                pd.Timestamp("2024-02-03", tz="UTC"),  # gapped through its stop INSIDE the window
                pd.Timestamp("2024-02-14", tz="UTC"),
            ],
            "realized_pnl": ["-900.0 USD", "150.0 USD"],
            "avg_px_open": [100.0, 101.0],
            "avg_px_close": [91.0, 102.5],
            "entry": ["BUY", "BUY"],
            "side": ["FLAT", "FLAT"],
            "is_snapshot": [False, False],
        }
    )
    kept = timed_trades_from_report(
        pos, "X", sl_pct=1.0, closed_from=pd.Timestamp("2024-02-01", tz="UTC")
    )
    assert [t["pnl_base"] for t in kept] == [-900.0, 150.0]  # the carried loss is NOT dropped


def test_a_trade_resolved_inside_the_preroll_belongs_to_the_previous_window() -> None:
    # Same seam from the other side: counting it here too would double-count it.
    pos = pd.DataFrame(
        {
            "ts_opened": [pd.Timestamp("2024-01-05", tz="UTC")],
            "ts_closed": [pd.Timestamp("2024-01-20", tz="UTC")],  # inside the pre-roll
            "realized_pnl": ["500.0 USD"],
            "avg_px_open": [100.0],
            "avg_px_close": [105.0],
            "entry": ["BUY"],
            "side": ["FLAT"],
            "is_snapshot": [False],
        }
    )
    assert (
        timed_trades_from_report(
            pos, "X", sl_pct=1.0, closed_from=pd.Timestamp("2024-02-01", tz="UTC")
        )
        == []
    )


def test_skipped_rows_never_truncate_later_authoritative_directions() -> None:
    """Open and pre-roll rows are filters, not end-of-report sentinels."""
    boundary = pd.Timestamp("2024-02-01", tz="UTC")
    pos = pd.DataFrame(
        {
            "ts_opened": [
                pd.Timestamp("2024-01-01", tz="UTC"),
                pd.Timestamp("2024-01-02", tz="UTC"),
                pd.Timestamp("2024-02-02", tz="UTC"),
            ],
            "ts_closed": [
                pd.NaT,
                pd.Timestamp("2024-01-20", tz="UTC"),
                pd.Timestamp("2024-02-03", tz="UTC"),
            ],
            "realized_pnl": ["0 USD", "-10 USD", "25 USD"],
            "avg_px_open": [100.0, 100.0, 100.0],
            "avg_px_close": [100.0, 101.0, 102.0],
            "entry": ["SELL", "SELL", "BUY"],
            "side": ["SHORT", "FLAT", "FLAT"],
        }
    )

    extracted = timed_trades_from_report(pos, "X", sl_pct=1.0, closed_from=boundary)

    assert [(row["ts_closed"], row["is_long"]) for row in extracted] == [
        (pd.Timestamp("2024-02-03", tz="UTC").value, True)
    ]


def test_naive_report_timestamp_is_compared_on_the_authoritative_utc_axis() -> None:
    """Nautilus timestamps without tz metadata still represent UTC report instants."""
    closed = pd.Timestamp("2024-02-03 12:00")
    pos = _closed_position("BUY")
    pos["ts_closed"] = [closed]

    extracted = timed_trades_from_report(
        pos,
        "X",
        sl_pct=1.0,
        closed_from=pd.Timestamp("2024-02-01", tz="UTC"),
    )

    assert extracted[0]["ts_closed"] == closed.value
    assert extracted[0]["is_long"] is True


def test_trade_closing_exactly_at_window_start_is_attributed_to_that_window() -> None:
    boundary = pd.Timestamp("2024-02-01", tz="UTC")
    pos = _closed_position("SELL")
    pos["ts_closed"] = [boundary]

    extracted = timed_trades_from_report(pos, "X", sl_pct=1.0, closed_from=boundary)

    assert [(row["ts_closed"], row["is_long"]) for row in extracted] == [
        (boundary.value, False)
    ]


def test_report_money_and_stop_schedule_use_the_authoritative_open_record() -> None:
    opened = pd.Timestamp("2024-01-01", tz="UTC")
    pos = _closed_position("BUY")
    pos["realized_pnl"] = ["1_234.5 USD"]
    seen: list[int] = []

    def stop_at_open(timestamp_ns: int) -> float:
        seen.append(timestamp_ns)
        return 1.25

    extracted = timed_trades_from_report(pos, "X", sl_pct=stop_at_open)

    assert seen == [opened.value]
    assert extracted[0]["pnl_base"] == 1_234.5
    assert extracted[0]["sl_pct"] == 1.25
    assert extracted[0]["is_long"] is True
