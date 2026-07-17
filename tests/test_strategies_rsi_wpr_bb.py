"""Tests for the RSI/Williams %R/Bollinger strategy and its indicator helpers."""

import math
from pathlib import Path

from core.data.synthetic import write_synthetic_catalog
from core.strategies.rsi_wpr_bb_signals import bollinger, williams_r
from nautilus_trader.config import (
    BacktestDataConfig,
    BacktestEngineConfig,
    BacktestRunConfig,
    BacktestVenueConfig,
    ImportableStrategyConfig,
    LoggingConfig,
)
from nautilus_trader.model.data import BarType
from nautilus_trader.test_kit.providers import TestInstrumentProvider
from research.engine.config import run_backtest

_INSTRUMENT = TestInstrumentProvider.audusd_cfd()
_BAR_TYPE = BarType.from_str("AUDUSD.OANDA-4-HOUR-LAST-EXTERNAL")


def test_williams_r_at_high_is_zero() -> None:
    # Close equal to the highest high -> %R == 0.
    assert williams_r([10.0, 12.0, 11.0], [8.0, 9.0, 7.0], 12.0) == 0.0


def test_williams_r_at_low_is_minus_100() -> None:
    # Close equal to the lowest low -> %R == -100.
    assert williams_r([10.0, 12.0, 11.0], [8.0, 9.0, 7.0], 7.0) == -100.0


def test_williams_r_zero_range_is_safe() -> None:
    assert williams_r([5.0, 5.0], [5.0, 5.0], 5.0) == 0.0


def test_bollinger_matches_manual_calculation() -> None:
    closes = [1.0, 2.0, 3.0, 4.0, 5.0]
    upper, middle, lower = bollinger(closes, mult=2.0)
    mean = 3.0
    std = math.sqrt(sum((c - mean) ** 2 for c in closes) / len(closes))
    assert middle == mean
    assert math.isclose(upper, mean + 2.0 * std)
    assert math.isclose(lower, mean - 2.0 * std)


def test_signal_engine_warms_up_and_resets() -> None:
    from core.strategies.rsi_wpr_bb_signals import RsiWprBbSignals, SignalParams

    engine = RsiWprBbSignals(SignalParams())
    for i in range(60):  # feed enough bars to warm up
        buy, sell = engine.update(100.0 + i * 0.1, 100.6 + i * 0.1, 99.4 + i * 0.1, 100.3 + i * 0.1)
        assert isinstance(buy, bool) and isinstance(sell, bool)
    assert engine.warmed_up
    engine.reset()
    assert not engine.warmed_up  # back to the pre-warmup state
    assert engine.update(100.0, 100.6, 99.4, 100.3) == (False, False)


def test_backtest_runs_end_to_end(tmp_path: Path) -> None:
    # Smoke test: the strategy processes H4 bars and completes without error.
    write_synthetic_catalog(tmp_path, instrument=_INSTRUMENT, bar_type=_BAR_TYPE, bar_count=500)
    run_config = BacktestRunConfig(
        venues=[
            BacktestVenueConfig(
                name=_INSTRUMENT.id.venue.value,
                oms_type="NETTING",
                account_type="MARGIN",
                base_currency="USD",
                starting_balances=["1_000_000 USD"],
                default_leverage=30.0,
            )
        ],
        data=[
            BacktestDataConfig(
                catalog_path=str(tmp_path),
                data_cls="nautilus_trader.model.data:Bar",
                instrument_id=str(_INSTRUMENT.id),
                bar_types=[str(_BAR_TYPE)],
            )
        ],
        engine=BacktestEngineConfig(
            strategies=[
                ImportableStrategyConfig(
                    strategy_path="core.strategies.rsi_wpr_bb:RsiWprBb",
                    config_path="core.strategies.rsi_wpr_bb:RsiWprBbConfig",
                    config={
                        "instrument_id": str(_INSTRUMENT.id),
                        "bar_type": str(_BAR_TYPE),
                        "trade_size": "100_000",
                        # Exercise the bracket (SL/TP) + risk-sizing code path.
                        "stop_loss_pct": 1.0,
                        "take_profit_pct": 2.0,
                        "risk_per_trade_pct": 1.0,
                    },
                )
            ],
            logging=LoggingConfig(bypass_logging=True),
        ),
        dispose_on_completion=False,
    )

    result = run_backtest(run_config)
    assert isinstance(result.total_orders, int)
    assert result.total_orders >= 0
