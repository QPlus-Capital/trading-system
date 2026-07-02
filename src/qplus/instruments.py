"""Instrument definitions for the venues we trade.

Instruments model the contract details (precision, tick, sizing, fees) the backtest
engine needs. Sizes are expressed in the underlying units (e.g. ounces of gold),
not broker "lots"; ``lot_size`` records the broker's lot for reference.
"""

from decimal import Decimal

from nautilus_trader.model.currencies import EUR, GBP, USD, XAU
from nautilus_trader.model.enums import AssetClass
from nautilus_trader.model.identifiers import InstrumentId, Symbol
from nautilus_trader.model.instruments import Cfd
from nautilus_trader.model.objects import Currency, Price, Quantity

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


def _fx_cfd(symbol: str, base: Currency) -> Cfd:
    """An FX pair CFD (5 decimals, 100k contract, 2% margin, ~2 USD/lot commission).

    Size is measured in base-currency units (1 MT5 lot = 100 000).
    """
    return Cfd(
        instrument_id=InstrumentId.from_str(f"{symbol}.{TTP_VENUE}"),
        raw_symbol=Symbol(symbol),
        asset_class=AssetClass.FX,
        base_currency=base,
        quote_currency=USD,
        price_precision=5,
        price_increment=Price.from_str("0.00001"),
        size_precision=0,
        size_increment=Quantity.from_int(1),
        lot_size=Quantity.from_int(100_000),
        margin_init=Decimal("0.02"),  # ~50:1 leverage
        margin_maint=Decimal("0.02"),
        maker_fee=Decimal("0.00002"),  # ~2 USD per 100k lot per side
        taker_fee=Decimal("0.00002"),
        ts_event=0,
        ts_init=0,
    )


def eurusd_ttp() -> Cfd:
    """Euro vs US Dollar CFD (EURUSD)."""
    return _fx_cfd("EURUSD", EUR)


def gbpusd_ttp() -> Cfd:
    """British Pound vs US Dollar CFD (GBPUSD)."""
    return _fx_cfd("GBPUSD", GBP)


def _index_cfd(symbol: str, size_increment: str) -> Cfd:
    """A stock-index CFD (2 decimals, contract size 1, ~15:1 margin, no commission).

    Size is in index units (1 lot = 1 point = 1 unit of the quote currency per point).
    The cost is entirely in the spread. DE40 is EUR-settled but modelled USD-quoted
    here -- a small approximation that barely affects percent-based metrics.
    """
    return Cfd(
        instrument_id=InstrumentId.from_str(f"{symbol}.{TTP_VENUE}"),
        raw_symbol=Symbol(symbol),
        asset_class=AssetClass.INDEX,
        base_currency=None,
        quote_currency=USD,
        price_precision=2,
        price_increment=Price.from_str("0.01"),
        size_precision=len(size_increment.split(".")[1]),
        size_increment=Quantity.from_str(size_increment),
        lot_size=Quantity.from_int(1),
        margin_init=Decimal("0.0667"),  # ~15:1 leverage
        margin_maint=Decimal("0.0667"),
        maker_fee=Decimal("0"),
        taker_fee=Decimal("0"),
        ts_event=0,
        ts_init=0,
    )


def us30_ttp() -> Cfd:
    """US 30 (Dow Jones) index CFD (US30), volume step 0.01."""
    return _index_cfd("US30", "0.01")


def de40_ttp() -> Cfd:
    """Germany 40 (DAX) index CFD (DE40), volume step 0.1; EUR-settled (see note)."""
    return _index_cfd("DE40", "0.1")
