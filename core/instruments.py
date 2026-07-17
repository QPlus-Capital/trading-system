"""Instrument definitions for the venues we trade.

Instruments model the **market-intrinsic** contract details (precision, tick, sizing,
currency) the backtest engine needs. Sizes are expressed in the underlying units (e.g.
ounces of gold), not broker "lots"; ``lot_size`` records the broker's lot for reference.

The **broker-specific** terms -- commission and margin -- come from the :class:`BrokerProfile`
(default :data:`TTP_MARKETS`), so switching broker is swapping the profile, not editing this file.
"""

from nautilus_trader.model.currencies import AUD, CAD, CHF, EUR, GBP, JPY, USD, XAG, XAU
from nautilus_trader.model.enums import AssetClass
from nautilus_trader.model.identifiers import InstrumentId, Symbol
from nautilus_trader.model.instruments import Cfd
from nautilus_trader.model.objects import Currency, Price, Quantity

from core.broker import TTP_MARKETS, BrokerProfile

# Venue name for The Trading Pit's MT5 feed (broker: MEX Atlantic).
TTP_VENUE = "TTP"


def xauusd_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """Gold vs US Dollar CFD as offered on The Trading Pit's MT5 (XAUUSD).

    Specs mirror the broker's symbol specification: 2 price decimals, 0.01 tick,
    contract size 100 (1 lot = 100 oz), USD-quoted. Commission + margin come from ``profile``.
    Size is measured in **ounces** (1 MT5 lot = 100).
    """
    s = profile.instrument_spec("XAUUSD")
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
        margin_init=s.margin_init,
        margin_maint=s.margin_init,
        maker_fee=s.maker_fee,
        taker_fee=s.taker_fee,
        ts_event=0,
        ts_init=0,
    )


def _fx_cfd(
    symbol: str, base: Currency, *, price_precision: int = 5, profile: BrokerProfile = TTP_MARKETS
) -> Cfd:
    """An FX pair CFD (100k contract). Commission + margin come from ``profile``.

    Size is measured in base-currency units (1 MT5 lot = 100 000). JPY pairs quote
    with 3 decimals; everything else with 5. Pairs whose quote currency is not USD
    (USDCHF/USDJPY/USDCAD) are modelled USD-quoted -- a small approximation that barely
    affects percent-based metrics; ``base`` then just labels the foreign leg.
    """
    s = profile.instrument_spec(symbol)
    tick = "0.001" if price_precision == 3 else "0.00001"
    return Cfd(
        instrument_id=InstrumentId.from_str(f"{symbol}.{TTP_VENUE}"),
        raw_symbol=Symbol(symbol),
        asset_class=AssetClass.FX,
        base_currency=base,
        quote_currency=USD,
        price_precision=price_precision,
        price_increment=Price.from_str(tick),
        size_precision=0,
        size_increment=Quantity.from_int(1),
        lot_size=Quantity.from_int(100_000),
        margin_init=s.margin_init,
        margin_maint=s.margin_init,
        maker_fee=s.maker_fee,
        taker_fee=s.taker_fee,
        ts_event=0,
        ts_init=0,
    )


def eurusd_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """Euro vs US Dollar CFD (EURUSD)."""
    return _fx_cfd("EURUSD", EUR, profile=profile)


def gbpusd_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """British Pound vs US Dollar CFD (GBPUSD)."""
    return _fx_cfd("GBPUSD", GBP, profile=profile)


def audusd_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """Australian Dollar vs US Dollar CFD (AUDUSD); USD-quoted (clean)."""
    return _fx_cfd("AUDUSD", AUD, profile=profile)


def usdchf_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """US Dollar vs Swiss Franc CFD (USDCHF); CHF-settled, modelled USD-quoted (see note)."""
    return _fx_cfd("USDCHF", CHF, profile=profile)


def usdjpy_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """US Dollar vs Japanese Yen CFD (USDJPY); 3 decimals, JPY-settled (see note)."""
    return _fx_cfd("USDJPY", JPY, price_precision=3, profile=profile)


def usdcad_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """US Dollar vs Canadian Dollar CFD (USDCAD); CAD-settled, modelled USD-quoted (see note)."""
    return _fx_cfd("USDCAD", CAD, profile=profile)


def xagusd_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """Silver vs US Dollar CFD (XAGUSD).

    3 price decimals, 0.001 tick, contract size 5000 (1 lot = 5000 oz), USD-quoted.
    Commission + margin come from ``profile``. Size is measured in **ounces**.
    """
    s = profile.instrument_spec("XAGUSD")
    return Cfd(
        instrument_id=InstrumentId.from_str(f"XAGUSD.{TTP_VENUE}"),
        raw_symbol=Symbol("XAGUSD"),
        asset_class=AssetClass.COMMODITY,
        base_currency=XAG,
        quote_currency=USD,
        price_precision=3,
        price_increment=Price.from_str("0.001"),
        size_precision=0,
        size_increment=Quantity.from_int(1),
        lot_size=Quantity.from_int(5000),
        margin_init=s.margin_init,
        margin_maint=s.margin_init,
        maker_fee=s.maker_fee,
        taker_fee=s.taker_fee,
        ts_event=0,
        ts_init=0,
    )


def _index_cfd(symbol: str, size_increment: str, *, profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """A stock-index CFD (2 decimals, contract size 1). Commission + margin come from ``profile``.

    Size is in index units (1 lot = 1 point = 1 unit of the quote currency per point).
    The cost is entirely in the spread. DE40 is EUR-settled but modelled USD-quoted
    here -- a small approximation that barely affects percent-based metrics.
    """
    s = profile.instrument_spec(symbol)
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
        margin_init=s.margin_init,
        margin_maint=s.margin_init,
        maker_fee=s.maker_fee,
        taker_fee=s.taker_fee,
        ts_event=0,
        ts_init=0,
    )


def us30_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """US 30 (Dow Jones) index CFD (US30), volume step 0.01."""
    return _index_cfd("US30", "0.01", profile=profile)


def de40_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """Germany 40 (DAX) index CFD (DE40), volume step 0.1; EUR-settled (see note)."""
    return _index_cfd("DE40", "0.1", profile=profile)


def ustec_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """US 100 (Nasdaq 100) index CFD (USTEC), volume step 0.01."""
    return _index_cfd("USTEC", "0.01", profile=profile)


def us500_ttp(profile: BrokerProfile = TTP_MARKETS) -> Cfd:
    """US 500 (S&P 500) index CFD (US500), volume step 0.01."""
    return _index_cfd("US500", "0.01", profile=profile)
