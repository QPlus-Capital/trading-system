"""Backtest configuration.

A :class:`BacktestConfig` fully describes a single backtest run: which instrument
and bars, the strategy parameters, the simulated account, and -- for this
skeleton -- the parameters of the deterministic synthetic price series that
stands in for real market data. Concrete configs live under ``config/backtest/``.

All monetary and price values are :class:`~decimal.Decimal`; floats are never
used for money or prices.
"""

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, kw_only=True)
class BacktestConfig:
    """Parameters for one backtest run.

    Parameters
    ----------
    instrument_id : str
        The instrument identifier, e.g. ``"AUDUSD.OANDA"``. Must be known to the
        runner's instrument registry.
    bar_spec : str
        The bar specification appended to ``instrument_id`` to form the bar type,
        e.g. ``"1-DAY-LAST-EXTERNAL"``.
    fast_ema_period : int
        The fast EMA period.
    slow_ema_period : int
        The slow EMA period. Must be greater than ``fast_ema_period``.
    trade_size : Decimal
        The position size, in instrument units, entered per signal.
    account_currency : str
        The account base currency, e.g. ``"USD"``.
    starting_balance : Decimal
        The starting account balance in ``account_currency``.
    leverage : Decimal
        The default account leverage for the margin account.
    bar_count : int
        The number of synthetic bars to generate.
    start_time : str
        The UTC timestamp of the first bar (parsed by pandas), e.g. ``"2020-01-01"``.
    start_price : Decimal
        The mid price of the synthetic series' baseline.
    wave_amplitude : Decimal
        The peak deviation of the synthetic sine wave from ``start_price``.
    wave_period_bars : int
        The number of bars in one full sine cycle. Drives how often EMAs cross.
    bar_half_range : Decimal
        Half the high-low range of each synthetic bar. Kept above the instrument's
        price increment so bars are never single-price.
    """

    # Instrument & bars
    instrument_id: str = "AUDUSD.OANDA"
    bar_spec: str = "1-DAY-LAST-EXTERNAL"

    # Strategy
    fast_ema_period: int = 10
    slow_ema_period: int = 20
    trade_size: Decimal = field(default_factory=lambda: Decimal("100_000"))

    # Simulated account / venue
    account_currency: str = "USD"
    starting_balance: Decimal = field(default_factory=lambda: Decimal("1_000_000"))
    leverage: Decimal = field(default_factory=lambda: Decimal("30"))

    # Synthetic market data (stand-in until real IBKR data is wired in)
    bar_count: int = 300
    start_time: str = "2020-01-01"
    start_price: Decimal = field(default_factory=lambda: Decimal("0.70000"))
    wave_amplitude: Decimal = field(default_factory=lambda: Decimal("0.03"))
    wave_period_bars: int = 40
    bar_half_range: Decimal = field(default_factory=lambda: Decimal("0.0005"))

    def __post_init__(self) -> None:
        if self.fast_ema_period <= 0 or self.slow_ema_period <= 0:
            raise ValueError("EMA periods must be positive")
        if self.fast_ema_period >= self.slow_ema_period:
            raise ValueError("fast_ema_period must be less than slow_ema_period")
        if self.bar_count <= 0:
            raise ValueError("bar_count must be positive")
        if self.wave_period_bars <= 0:
            raise ValueError("wave_period_bars must be positive")
        if self.trade_size <= 0:
            raise ValueError("trade_size must be positive")
        if self.starting_balance <= 0:
            raise ValueError("starting_balance must be positive")

    @property
    def bar_type_str(self) -> str:
        """The full bar type string, e.g. ``"AUDUSD.OANDA-1-DAY-LAST-EXTERNAL"``."""
        return f"{self.instrument_id}-{self.bar_spec}"
