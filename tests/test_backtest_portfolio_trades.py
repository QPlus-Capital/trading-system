"""Tests for the timed OOS trade-stream extraction (Stage 1 -> 3)."""

import pandas as pd

from qplus.backtest.portfolio_trades import timed_trades_from_report


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
            "is_snapshot": [True, False, False],  # a snapshot round-trip is still a real trade
        }
    )
    trades = timed_trades_from_report(pos, "X")
    assert len(trades) == 2  # the open position is skipped; the snapshot is kept
    assert trades[0]["market"] == "X"
    assert trades[0]["pnl_1pct"] == 100.5
    assert trades[0]["entry"] == 10.0
    assert trades[0]["exit"] == 10.5
    assert trades[0]["ts_opened"] == pd.Timestamp("2020-01-01", tz="UTC").value
    assert trades[1]["pnl_1pct"] == -50.0
