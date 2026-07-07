"""Phase 1: how much do overnight swap/financing costs erode the backtest edge?

The strategy holds positions over multiple days, and swaps are the one real cost NOT modelled
in the backtest. This pulls the live per-symbol swap rates from the terminal, applies them to
the full-history trade stream (per trade: direction, lot volume at the live flat risk, and
nights held including the triple-swap rollover day), and reports the impact on the key metrics.

Swap is signed and direction-dependent: e.g. index CFDs pay a POSITIVE swap on SHORTS (a
credit) and charge it on longs -- so for a long/short reversal strategy it is NOT uniformly a
cost. Two calculation modes cover our 9 markets:
- **POINTS** (FX, gold): swap is in points -> money = points * tick_value.
- **INT_CURRENT** (indices): annual interest on the notional -> money = price * rate% / 360.

Estimate, not exact history: swap rates are a *current* snapshot, broker-specific (TTP Markets
!= MEX Atlantic), and change over time. Read it as order-of-magnitude.

Run from the repo root (MT5 terminal open + logged in)::

    uv run python -m qplus.backtest.portfolio.swap_analysis
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import numpy as np
import pandas as pd

from qplus.backtest.config import load_config_module
from qplus.backtest.portfolio.equity_report import _START_BALANCE, _market_trades

_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[4]
_INT_YEAR = 360.0  # standard bank year for interest-mode swaps


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
    """
    o = pd.Timestamp(open_ns).date()
    c = pd.Timestamp(close_ns).date()
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


def market_swaps(
    trades: pd.DataFrame, spec: SwapSpec, sl_pct: float, risk_amount: float
) -> pd.DataFrame:
    """Per-trade gross (flat) PnL and swap PnL for one market, in the account currency.

    ``trades`` has columns ts_opened, ts_closed, entry, exit, r (from the equity-report backtest).
    Volume is the flat-risk lot size (a stop-out loses ``risk_amount``); direction is inferred
    from the sign of ``r`` vs the price move.
    """
    rows = []
    for t in trades.itertuples(index=False):
        is_long = (t.r > 0) == (t.exit > t.entry)
        stop_distance = t.entry * sl_pct / 100.0
        loss_per_lot = (stop_distance / spec.tick_size) * spec.tick_value
        volume = risk_amount / loss_per_lot if loss_per_lot > 0 else 0.0
        units = night_units(int(t.ts_opened), int(t.ts_closed), spec.rollover_py)
        swap = units * swap_per_lot_night(spec, is_long=is_long, price=t.entry) * volume
        rows.append((risk_amount * t.r, swap, is_long))
    return pd.DataFrame(rows, columns=["flat_pnl", "swap_pnl", "is_long"])


def _profit_factor(pnl: np.ndarray) -> float:
    losses = -pnl[pnl < 0].sum()
    return float(pnl[pnl > 0].sum() / losses) if losses > 0 else float("inf")


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


def main() -> None:
    """Run the 9 backtests, apply live swap rates, and report the impact on the edge."""
    from qplus.live.mt5_bridge import Mt5Bridge

    cfg = load_config_module(_REPO_ROOT / "config" / "live" / "paper_rsi_wpr_bb.py")
    risk_amount = float(cfg.RISK_PER_TRADE_PCT) / 100.0 * _START_BALANCE
    switches = dict(cfg.STRATEGY_SWITCHES)
    names = [str(f().raw_symbol) for f, *_ in cfg.MARKETS]

    bridge = Mt5Bridge()
    bridge.connect()
    try:
        specs = pull_swap_specs(bridge, names)
    finally:
        bridge.shutdown()

    parts = []
    t0, t1 = None, None
    print(f"{'market':7s} {'trades':>6s} {'L/S':>9s} {'gross':>10s} {'swap':>10s} {'swap %':>7s}")
    for factory, csv, leverage, sl, tp in cfg.MARKETS:
        name = str(factory().raw_symbol)
        trades = _market_trades(factory, csv, leverage, sl, tp, switches)
        o, c = int(trades["ts_opened"].min()), int(trades["ts_closed"].max())
        t0, t1 = (o if t0 is None else min(t0, o)), (c if t1 is None else max(c, t1))
        m = market_swaps(trades, specs[name], sl, risk_amount)
        m["market"] = name
        parts.append(m)
        gross = m["flat_pnl"].sum()
        swap = m["swap_pnl"].sum()
        longs, shorts = int(m["is_long"].sum()), int((~m["is_long"]).sum())
        pct = swap / gross * 100 if gross else 0.0
        print(
            f"{name:7s} {len(m):>6d} {longs:>4d}/{shorts:<4d} {gross:>10,.0f} "
            f"{swap:>+10,.0f} {pct:>+6.1f}%"
        )

    all_t = pd.concat(parts, ignore_index=True)
    gross = all_t["flat_pnl"].to_numpy()
    net = gross + all_t["swap_pnl"].to_numpy()
    years = (t1 - t0) / (365.25 * 86400 * 1e9) if t0 is not None and t1 is not None else 1.0
    swap_total = all_t["swap_pnl"].sum()
    g_ret, n_ret = gross.sum() / _START_BALANCE, net.sum() / _START_BALANCE
    print("\n===== swap impact (flat 0.15% off 200k, full history) =====")
    swap_pct = swap_total / gross.sum() * 100
    print(f"total swap:       {swap_total:+,.0f} EUR ({swap_pct:+.1f}% of gross)")
    print(f"total return:     gross {g_ret:+.1%}  ->  net {n_ret:+.1%}")
    print(f"return p.a.:      gross {g_ret / years:+.1%}  ->  net {n_ret / years:+.1%}")
    print(f"profit factor:    gross {_profit_factor(gross):.2f}  ->  net {_profit_factor(net):.2f}")
    print(f"expectancy/trade: gross {gross.mean():+,.0f} EUR  ->  net {net.mean():+,.0f} EUR")


if __name__ == "__main__":
    main()
