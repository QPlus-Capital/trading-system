"""Backtest runner.

Wires a :class:`~qplus.backtest.config.BacktestConfig` into a NautilusTrader
``BacktestEngine`` and runs it: create the venue and instrument, feed the
(currently synthetic) bars, attach the strategy, run, and return the result.

Run the bundled demo from the repo root::

    uv run python -m qplus.backtest.runner

or point it at another config module under ``config/backtest/``::

    uv run python -m qplus.backtest.runner config/backtest/ema_cross_demo.py
"""

import importlib.util
import sys
from pathlib import Path

from nautilus_trader.backtest.engine import BacktestEngine
from nautilus_trader.backtest.results import BacktestResult
from nautilus_trader.model.data import BarType
from nautilus_trader.model.enums import AccountType, OmsType
from nautilus_trader.model.instruments import Instrument
from nautilus_trader.model.objects import Currency, Money
from nautilus_trader.test_kit.providers import TestInstrumentProvider

from qplus.backtest.config import BacktestConfig
from qplus.backtest.data import make_synthetic_bars
from qplus.strategies.ema_cross import EMACross, EMACrossConfig

# Repo root: src/qplus/backtest/runner.py -> parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_CONFIG = _REPO_ROOT / "config" / "backtest" / "ema_cross_demo.py"

# Instruments the runner knows how to build. Extend as more are backtested.
_INSTRUMENTS = {
    "AUDUSD.OANDA": TestInstrumentProvider.audusd_cfd,
}


def resolve_instrument(instrument_id: str) -> Instrument:
    """Return the instrument for ``instrument_id`` from the known registry."""
    try:
        factory = _INSTRUMENTS[instrument_id]
    except KeyError:
        known = ", ".join(sorted(_INSTRUMENTS))
        raise ValueError(f"Unknown instrument {instrument_id!r}; known: {known}") from None
    return factory()


def run_backtest(config: BacktestConfig) -> BacktestResult:
    """Run a single backtest and return its result.

    Parameters
    ----------
    config : BacktestConfig
        The fully specified backtest configuration.

    Returns
    -------
    BacktestResult
        The result summary of the run (orders, positions, PnL statistics, ...).
    """
    instrument = resolve_instrument(config.instrument_id)
    bar_type = BarType.from_str(config.bar_type_str)
    currency = Currency.from_str(config.account_currency)

    engine = BacktestEngine()
    try:
        engine.add_venue(
            venue=instrument.id.venue,
            oms_type=OmsType.NETTING,
            account_type=AccountType.MARGIN,
            base_currency=currency,
            starting_balances=[Money(config.starting_balance, currency)],
            default_leverage=config.leverage,
        )
        engine.add_instrument(instrument)
        engine.add_data(make_synthetic_bars(instrument, bar_type, config))
        engine.add_strategy(
            EMACross(
                EMACrossConfig(
                    instrument_id=instrument.id,
                    bar_type=bar_type,
                    trade_size=config.trade_size,
                    fast_ema_period=config.fast_ema_period,
                    slow_ema_period=config.slow_ema_period,
                ),
            ),
        )
        engine.run()
        result: BacktestResult = engine.get_result()
        return result
    finally:
        engine.dispose()


def load_config(path: Path) -> BacktestConfig:
    """Load the ``config`` object from a Python config module at ``path``."""
    spec = importlib.util.spec_from_file_location("qplus_backtest_config", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load backtest config from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = getattr(module, "config", None)
    if not isinstance(config, BacktestConfig):
        raise TypeError(f"{path} must define a `config` of type BacktestConfig")
    return config


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: load a config module and run the backtest."""
    args = sys.argv[1:] if argv is None else argv
    path = Path(args[0]) if args else _DEFAULT_CONFIG

    config = load_config(path)
    result = run_backtest(config)

    print("\n===== Backtest result =====")
    print(f"config:        {path}")
    print(f"instrument:    {config.instrument_id}  ({config.bar_type_str})")
    print(f"total orders:  {result.total_orders}")
    print(f"total positions: {result.total_positions}")
    for ccy, stats in result.stats_pnls.items():
        print(f"PnL [{ccy}]:    {stats.get('PnL (total)')}  ({stats.get('PnL% (total)')}%)")


if __name__ == "__main__":
    main()
