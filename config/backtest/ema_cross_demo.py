"""Demo backtest config: EMA crossover on synthetic AUD/USD daily bars.

Runs the ``EMACross`` strategy on a deterministic synthetic price series -- no
real market data or IBKR credentials required. Run it from the repo root with::

    uv run python -m qplus.backtest.runner config/backtest/ema_cross_demo.py

Tweak the parameters below to experiment; the strategy code never changes.
"""

from decimal import Decimal

from qplus.backtest.config import BacktestConfig

config = BacktestConfig(
    instrument_id="AUDUSD.OANDA",
    bar_spec="1-DAY-LAST-EXTERNAL",
    fast_ema_period=10,
    slow_ema_period=20,
    trade_size=Decimal("100_000"),
    account_currency="USD",
    starting_balance=Decimal("1_000_000"),
    leverage=Decimal("30"),
    bar_count=300,
    start_time="2020-01-01",
    start_price=Decimal("0.70000"),
    wave_amplitude=Decimal("0.03"),
    wave_period_bars=40,
    bar_half_range=Decimal("0.0005"),
)
