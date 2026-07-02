"""Instrument definitions for the venues we trade.

Instruments model the contract details (precision, tick, sizing, fees) the backtest
engine needs. Sizes are expressed in the underlying units (e.g. ounces of gold),
not broker "lots"; ``lot_size`` records the broker's lot for reference.
"""

from decimal import Decimal

from nautilus_trader.model.currencies import USD, XAU
from nautilus_trader.model.enums import AssetClass
from nautilus_trader.model.identifiers import InstrumentId, Symbol
from nautilus_trader.model.instruments import Cfd
from nautilus_trader.model.objects import Price, Quantity

# Venue name for The Trading Pit's MT5 feed (broker: MEX Atlantic).
TTP_VENUE = "TTP"


def xauusd_ttp() -> Cfd:
    """Gold vs US Dollar CFD as offered on The Trading Pit's MT5 (XAUUSD).

    Specs mirror the broker's symbol specification: 2 price decimals, 0.01 tick,
    contract size 100 (1 lot = 100 oz), USD-quoted, ~0.0007% commission per side.
    Size is measured in **ounces** (1 MT5 lot = 100).
    """
    return Cfd(
        instrument_id=InstrumentId.from_str(f"XAUUSD.{TTP_VENUE}"),
        raw_symbol=Symbol("XAUUSD"),
        asset_class=AssetClass.COMMODITY,
        base_currency=XAU,
        quote_currency=USD,
        price_precision=2,
        price_increment=Price.from_str("0.01"),
        size_precision=0,
        size_increment=Quantity.from_int(1),
        lot_size=Quantity.from_int(100),
        margin_init=Decimal("0.10"),  # ~10:1 leverage (broker margin ~10% of notional)
        margin_maint=Decimal("0.10"),
        maker_fee=Decimal("0.000007"),  # 0.0007% of notional per side
        taker_fee=Decimal("0.000007"),
        ts_event=0,
        ts_init=0,
    )
