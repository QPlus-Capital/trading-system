"""The swappable broker/market profile -- one source for all broker-specific costs.

The keystone of the broker-agnostic framework (see docs/roadmap.md): switching broker / prop /
own-account is swapping this profile, and the backtest applies that broker's costs net-in-run.

Where each cost lives (use NautilusTrader natively where it is precise; build the delta only
where it is not):
- **spread**    -- from the bid/ask bars in the data (not a profile knob).
- **commission**-- the instrument's maker/taker fee (instrument definition).
- **slippage**  -- NautilusTrader's ``FillModel`` (``prob_slippage``), configured from here.
- **swap**      -- our exact per-broker logic (POINTS / interest mode, correct rollover day),
                   applied to the R-multiple trade stream (:func:`swap_r_per_trade`). The native
                   ``FXRolloverInterestModule`` only models interest-on-notional, an approximation
                   for the fixed-points swaps FX/gold use, so we build the precise delta instead.
                   Rates are a persisted snapshot pulled from the live terminal
                   (:func:`pull_swap_specs` / :func:`dump_swap_snapshot`) so backtests are
                   reproducible and offline; the snapshot is also the live calibration input.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
from nautilus_trader.backtest.config import ImportableFillModelConfig

from core.data.mt5_csv import MT5_SERVER_TZ
from core.paths import REPO_ROOT

_INT_YEAR = 360.0  # standard bank year for interest-mode swaps


# --------------------------------------------------------------------------------------------
# Per-instrument broker terms (commission + margin) -- the broker-specific half of an instrument
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class InstrumentSpec:
    """The broker-specific terms of one instrument (the market-intrinsic specs -- tick, contract
    size, precision, currency -- stay in ``core.instruments``; these are what a broker sets)."""

    maker_fee: Decimal  # commission per side, as a fraction of notional
    taker_fee: Decimal
    margin_init: Decimal  # initial margin fraction (== maintenance here); ~1/leverage


# --------------------------------------------------------------------------------------------
# Swap cost primitives (the broker-exact overnight-financing model)
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class SwapSpec:
    """Per-symbol swap parameters needed to price the overnight cost (in the account currency)."""

    mode: str  # "POINTS" or "INT_*"
    swap_long: float  # points (POINTS) or annual % (INT), charged on longs
    swap_short: float  # ... charged on shorts (can be POSITIVE = a credit)
    rollover_py: int  # python weekday (Mon=0) of the triple-swap day
    tick_value: float  # money per tick_size move per lot (account currency)
    tick_size: float


def swap_per_lot_night(
    spec: SwapSpec, *, is_long: bool, price: float, int_year: float = _INT_YEAR
) -> float:
    """Signed swap money per lot per night (negative = you pay, positive = credit)."""
    rate = spec.swap_long if is_long else spec.swap_short
    if spec.mode == "POINTS":
        return rate * spec.tick_value  # points -> money (tick_size == point for these symbols)
    # Interest mode: annual % on the notional; tick_value/tick_size converts to the account ccy.
    return price * (rate / 100.0) / int_year * (spec.tick_value / spec.tick_size)


def night_units(open_ns: int, close_ns: int, rollover_py: int) -> float:
    """Number of swap charges between open and close: 1x per weekday night, 3x on the rollover day.

    Weekends carry no separate charge -- the triple on the rollover weekday pre-charges them
    (the standard MetaTrader model).

    Counted on the BROKER SERVER's calendar, not UTC: MT5 rolls swaps at server midnight. The
    trade timestamps are real UTC (see ``core.data.mt5_csv``), so a position held 20:30->22:00 UTC
    in summer crosses the EET rollover while staying on one UTC date -- counting UTC dates would
    charge zero nights instead of one.
    """
    o = pd.Timestamp(open_ns, tz="UTC").tz_convert(MT5_SERVER_TZ).date()
    c = pd.Timestamp(close_ns, tz="UTC").tz_convert(MT5_SERVER_TZ).date()
    units = 0.0
    d = o
    while d < c:  # a rollover happens at the end of each held day before the close day
        wd = d.weekday()
        if wd == rollover_py:
            units += 3.0
        elif wd < 5:  # Mon-Fri
            units += 1.0
        d += timedelta(days=1)
    return units


def swap_r_per_trade(trades: pd.DataFrame, spec: SwapSpec) -> np.ndarray:
    """Signed swap cost per trade, expressed in **R** (risk units) -- scale-invariant.

    A trade sized so a stop-out loses exactly 1 R holds ``1 / loss_per_lot`` lots per R of risk,
    and over ``night_units`` nights accrues ``swap_per_lot_night`` per lot; so the swap in R is
    ``units * swap_per_lot_night / loss_per_lot``. Being in R it is independent of the account's
    risk amount and nets directly onto the R-multiple stream (``r += swap_r``). Negative = a cost,
    positive = a credit (index shorts).

    Requires columns ``entry``, ``exit``, ``ts_opened``, ``ts_closed``, ``sl_pct`` and the trade
    direction. Direction comes from an explicit ``is_long`` column; only legacy streams written
    before that column existed fall back to inferring it from the outcome, which misclassifies any
    trade whose costs flip the sign of ``r`` (the price moved our way, the net result did not) and
    then books the swap with the WRONG sign -- index shorts earn a credit that longs pay (#10).
    """
    if "is_long" in trades.columns:
        long_flags = trades["is_long"].to_numpy(dtype=bool)
    else:
        win_col = "r" if "r" in trades.columns else "pnl_base"
        won = trades[win_col].to_numpy(dtype=float) > 0
        exits = trades["exit"].to_numpy(dtype=float) > trades["entry"].to_numpy(dtype=float)
        long_flags = won == exits
    out = np.zeros(len(trades))
    for i, t in enumerate(trades.itertuples(index=False)):
        is_long = bool(long_flags[i])
        loss_per_lot = (t.entry * t.sl_pct / 100.0 / spec.tick_size) * spec.tick_value
        if loss_per_lot <= 0:
            continue
        units = night_units(int(t.ts_opened), int(t.ts_closed), spec.rollover_py)
        out[i] = units * swap_per_lot_night(spec, is_long=is_long, price=t.entry) / loss_per_lot
    return out


# --------------------------------------------------------------------------------------------
# The broker profile
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class BrokerProfile:
    """Broker-specific cost parameters that drive the backtest (slippage + swap).

    ``prob_slippage`` is the probability that a fill slips one tick against us (the NautilusTrader
    ``FillModel``). At H4 bar resolution slippage is irreducibly a model input (no tick data), so
    it lives here as an explicit, swappable assumption rather than being hidden or omitted.

    ``swap_specs`` maps raw symbol -> :class:`SwapSpec` (a persisted snapshot of the broker's live
    swap rates). Empty = swap not modelled; attach a snapshot with :meth:`with_swaps`.
    """

    name: str
    prob_slippage: float = 0.0  # P(a fill slips one tick); 0 = frictionless (baseline)
    random_seed: int = 13
    swap_specs: dict[str, SwapSpec] = field(default_factory=dict)
    instrument_specs: dict[str, InstrumentSpec] = field(default_factory=dict)

    def fill_model_config(self) -> ImportableFillModelConfig | None:
        """The venue's fill model for this broker's slippage, or ``None`` if frictionless."""
        if self.prob_slippage <= 0.0:
            return None
        return ImportableFillModelConfig(
            fill_model_path="nautilus_trader.backtest.models:FillModel",
            config_path="nautilus_trader.backtest.config:FillModelConfig",
            config={
                "prob_fill_on_limit": 1.0,
                "prob_slippage": self.prob_slippage,
                "random_seed": self.random_seed,
            },
        )

    def with_swaps(self, swap_specs: dict[str, SwapSpec]) -> BrokerProfile:
        """A copy of this profile carrying the given swap-rate snapshot."""
        return replace(self, swap_specs=swap_specs)

    def with_instruments(self, instrument_specs: dict[str, InstrumentSpec]) -> BrokerProfile:
        """A copy of this profile carrying the given per-instrument broker terms."""
        return replace(self, instrument_specs=instrument_specs)

    def swap_spec(self, symbol: str) -> SwapSpec | None:
        """The swap spec for ``symbol`` (raw), or ``None`` if not in the snapshot."""
        return self.swap_specs.get(symbol)

    def instrument_spec(self, symbol: str) -> InstrumentSpec:
        """The broker terms (commission + margin) for ``symbol`` (raw). Fail-fast if missing."""
        try:
            return self.instrument_specs[symbol]
        except KeyError:
            raise KeyError(
                f"broker profile '{self.name}' has no instrument spec for '{symbol}'"
            ) from None


# Per-symbol commission + margin for the current MT5 feed (The Trading Pit / MEX Atlantic).
# Metals: ~0.0007% per side, ~10:1. FX: ~2 USD per 100k lot per side, ~50:1. Indices: no
# commission (cost is in the spread), ~15:1. Switching broker = a different table here.
_METAL = InstrumentSpec(Decimal("0.000007"), Decimal("0.000007"), Decimal("0.10"))
_FX = InstrumentSpec(Decimal("0.00002"), Decimal("0.00002"), Decimal("0.02"))
_INDEX = InstrumentSpec(Decimal("0"), Decimal("0"), Decimal("0.0667"))
_TTP_SPECS: dict[str, InstrumentSpec] = {
    "XAUUSD": _METAL,
    "XAGUSD": _METAL,
    "EURUSD": _FX,
    "GBPUSD": _FX,
    "AUDUSD": _FX,
    "USDCHF": _FX,
    "USDJPY": _FX,
    "USDCAD": _FX,
    "US30": _INDEX,
    "DE40": _INDEX,
    "USTEC": _INDEX,
    "US500": _INDEX,
}

# Frictionless reference: spread + commission only, no slippage (the zero-slippage baseline).
FRICTIONLESS = BrokerProfile(name="frictionless", prob_slippage=0.0, instrument_specs=_TTP_SPECS)

# The live prop-firm broker. prob_slippage is a starting estimate for H4 CFDs -- calibrate it
# against the live account's actual fills once enough trades have closed.
TTP_MARKETS = BrokerProfile(name="ttp_markets", prob_slippage=0.15, instrument_specs=_TTP_SPECS)


# --------------------------------------------------------------------------------------------
# Swap-rate snapshot persistence (reproducible, offline; refreshed from the live terminal)
# --------------------------------------------------------------------------------------------
def swap_snapshot_path(name: str) -> Path:
    """Conventional path of a broker's persisted swap snapshot."""
    return REPO_ROOT / "core" / "config" / "broker" / f"{name}_swaps.json"


def dump_swap_snapshot(specs: dict[str, SwapSpec], path: Path) -> None:
    """Persist a swap-rate snapshot to JSON (so the backtest is reproducible and offline)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {sym: asdict(spec) for sym, spec in specs.items()}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True))


def load_swap_snapshot(path: Path) -> dict[str, SwapSpec]:
    """Load a swap-rate snapshot written by :func:`dump_swap_snapshot`."""
    payload = json.loads(path.read_text())
    return {sym: SwapSpec(**fields) for sym, fields in payload.items()}


def standard_broker() -> BrokerProfile:
    """The STANDARD backtest profile: TTP Markets with its real swap snapshot attached.

    TTP is the account actually traded live, so its costs are the truth the framework validates
    against. Swap is carried as a per-trade cost of carry (netted as a realized cost, never marked
    to market). Falls back to the swap-less TTP profile if the snapshot has not been pulled yet.
    """
    snap = swap_snapshot_path(TTP_MARKETS.name)
    return TTP_MARKETS.with_swaps(load_swap_snapshot(snap)) if snap.exists() else TTP_MARKETS


def pull_swap_specs(bridge: object, names: list[str]) -> dict[str, SwapSpec]:
    """Snapshot the current per-symbol swap parameters from the live terminal."""
    import MetaTrader5 as mt5

    modes = {1: "POINTS", 5: "INT_CURRENT", 6: "INT_OPEN"}
    out: dict[str, SwapSpec] = {}
    for name in names:
        s = mt5.symbol_info(bridge.terminal_symbol(name))  # type: ignore[attr-defined]
        out[name] = SwapSpec(
            mode=modes.get(int(s.swap_mode), f"MODE_{s.swap_mode}"),
            swap_long=float(s.swap_long),
            swap_short=float(s.swap_short),
            rollover_py=(int(s.swap_rollover3days) + 6) % 7,  # MT5 dow (Sun=0) -> python (Mon=0)
            tick_value=float(s.trade_tick_value),
            tick_size=float(s.trade_tick_size),
        )
    return out
