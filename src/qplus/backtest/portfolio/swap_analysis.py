"""Swap-cost report + snapshot refresh: how much do overnight swaps erode the edge?

The strategy holds positions over multiple days. This pulls the live per-symbol swap rates from
the terminal, **persists them as a snapshot** (`config/broker/mex_atlantic_swaps.json`) so the
backtest can apply them reproducibly and offline (see `qplus.backtest.broker`), and reports the
impact on the key metrics. The swap maths itself lives in `broker.swap_r_per_trade`; this module
is the human-readable report + the way the snapshot gets refreshed.

Swap is signed and direction-dependent: e.g. index CFDs pay a POSITIVE swap on SHORTS (a
credit) and charge it on longs -- so for a long/short reversal strategy it is NOT uniformly a
cost. Two calculation modes cover our 9 markets:
- **POINTS** (FX, gold): swap is in points -> money = points * tick_value.
- **INT_CURRENT** (indices): annual interest on the notional -> money = price * rate% / 360.

The rates are a *current* snapshot, broker-specific (TTP Markets != MEX Atlantic) and drift over
time -- so it is a calibrated estimate, refreshed by re-running this, not exact per-day history.

Run from the repo root (MT5 terminal open + logged in)::

    uv run python -m qplus.backtest.portfolio.swap_analysis
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from qplus.backtest.broker import (
    MEX_ATLANTIC,
    SwapSpec,
    dump_swap_snapshot,
    pull_swap_specs,
    swap_r_per_trade,
    swap_snapshot_path,
)
from qplus.backtest.config import load_config_module
from qplus.backtest.portfolio.equity_report import _START_BALANCE, _market_trades

_REPO_ROOT = __import__("pathlib").Path(__file__).resolve().parents[4]


def market_swaps(
    trades: pd.DataFrame, spec: SwapSpec, sl_pct: float, risk_amount: float
) -> pd.DataFrame:
    """Per-trade gross (flat) PnL and swap PnL for one market, in the account currency.

    ``trades`` has columns ts_opened, ts_closed, entry, exit, r (from the equity-report backtest).
    Swap is priced in R by :func:`swap_r_per_trade` (scale-invariant) and booked at ``risk_amount``.
    """
    t = trades.assign(sl_pct=sl_pct)
    swap_r = swap_r_per_trade(t, spec)
    r = t["r"].to_numpy(dtype=float)
    is_long = (r > 0) == (t["exit"].to_numpy() > t["entry"].to_numpy())
    return pd.DataFrame(
        {"flat_pnl": risk_amount * r, "swap_pnl": risk_amount * swap_r, "is_long": is_long}
    )


def _profit_factor(pnl: np.ndarray) -> float:
    losses = -pnl[pnl < 0].sum()
    return float(pnl[pnl > 0].sum() / losses) if losses > 0 else float("inf")


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

    # Persist the snapshot so backtests can apply swap reproducibly and offline (the profile then
    # drives the net-of-swap equity report). This terminal is the MEX Atlantic demo.
    snapshot = swap_snapshot_path(MEX_ATLANTIC.name)
    dump_swap_snapshot(specs, snapshot)
    print(f"swap snapshot saved -> {snapshot.relative_to(_REPO_ROOT)}\n")

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
