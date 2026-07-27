"""Tests for the shared portfolio statistics (R-multiples + edge metrics)."""

import numpy as np
import pandas as pd
import pytest
from core.broker import BrokerProfile, SwapSpec
from nautilus_trader.backtest import node as node_module
from research.portfolio import stats
from research.portfolio.stats import edge_stats, r_multiples


def _market_trade_fixture(
    monkeypatch: pytest.MonkeyPatch,
    broker: BrokerProfile,
) -> pd.DataFrame:
    class _Instrument:
        raw_symbol = "TEST"

    class _Recipe:
        INSTRUMENT = _Instrument()

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def build_run_config(self, _params: dict[str, object]) -> object:
            return object()

    class _Trader:
        @staticmethod
        def generate_positions_report() -> pd.DataFrame:
            return pd.DataFrame()

    class _Engine:
        trader = _Trader()

    class _Node:
        def __init__(self, *, configs: list[object]) -> None:
            assert len(configs) == 1

        @staticmethod
        def run() -> None:
            pass

        @staticmethod
        def get_engines() -> list[_Engine]:
            return [_Engine()]

        @staticmethod
        def dispose() -> None:
            pass

    opened = int(pd.Timestamp("2024-01-01", tz="UTC").value)
    closed = int(pd.Timestamp("2024-01-02", tz="UTC").value)
    rows = [
        {
            "market": "TEST",
            "ts_opened": opened,
            "ts_closed": closed,
            "pnl_base": 1_000.0,
            "entry": 100.0,
            "exit": 110.0,
            "sl_pct": 1.0,
            "is_long": True,
        }
    ]
    monkeypatch.setattr(stats, "SweepRecipe", _Recipe)
    monkeypatch.setattr(node_module, "BacktestNode", _Node)
    monkeypatch.setattr(stats, "timed_trades_from_report", lambda *_args: rows)
    return stats._market_trades(
        lambda: _Instrument(),
        "unused.csv",
        10.0,
        1.0,
        2.0,
        {},
        broker,
    )


def test_market_trades_preserves_gross_and_separate_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    broker = BrokerProfile(
        name="swap-bearing",
        swap_specs={
            "TEST": SwapSpec(
                mode="POINTS",
                swap_long=-0.25,
                swap_short=0.10,
                rollover_py=2,
                tick_value=1.0,
                tick_size=1.0,
            )
        },
    )

    result = _market_trade_fixture(monkeypatch, broker)

    assert result.loc[0, "r"] == pytest.approx(1.0)
    assert result.loc[0, "swap_r"] == pytest.approx(-0.25)
    assert result.loc[0, "swap_r"] != 0.0
    assert result.loc[0, "net_r"] == pytest.approx(result.loc[0, "r"] + result.loc[0, "swap_r"])


def test_market_trades_records_zero_swap_when_broker_has_no_market_spec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _market_trade_fixture(monkeypatch, BrokerProfile(name="swap-less"))

    assert result.loc[0, "r"] == pytest.approx(1.0)
    assert result.loc[0, "swap_r"] == pytest.approx(0.0)
    assert result.loc[0, "net_r"] == result.loc[0, "r"]


def test_r_multiples_recover_size_invariant_return() -> None:
    # First trade risks 1% of 200k = 2000; a +2000 PnL is exactly +1R.
    rs = r_multiples([2000.0], start=200_000.0)
    assert abs(rs[0] - 1.0) < 1e-9


def test_r_multiples_walk_the_equity_forward() -> None:
    # After a +2000 win, equity is 202k -> next trade risks 2020; a -2020 loss is -1R.
    rs = r_multiples([2000.0, -2020.0], start=200_000.0)
    assert abs(rs[0] - 1.0) < 1e-9
    assert abs(rs[1] + 1.0) < 1e-9


def test_edge_stats_count_metrics() -> None:
    # 4 trades: +100, -50, +200, -50 -> 2 wins / 2 losses.
    s = edge_stats(np.array([100.0, -50.0, 200.0, -50.0]))
    assert s["trades"] == 4.0
    assert abs(s["hit_rate"] - 0.5) < 1e-9
    assert abs(s["payoff"] - 3.0) < 1e-9  # avg win 150 / avg loss 50
    assert abs(s["profit_factor"] - 3.0) < 1e-9  # 300 won / 100 lost
    assert abs(s["expectancy"] - 50.0) < 1e-9  # (100-50+200-50)/4
