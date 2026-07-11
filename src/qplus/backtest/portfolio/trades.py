"""The timestamped out-of-sample trade stream that the portfolio stage consumes.

The portfolio stage needs each out-of-sample trade with its open/close time and entry/exit price,
so the account's daily equity can be reconstructed. This runs the same walk-forward as the edge
study (choose parameters on train by Calmar), but on each test window records the timed trades
instead of only their PnL.

``timed_trades_from_report`` is the pure extraction from a NautilusTrader positions report
(unit-tested); ``extract_market_trades`` drives the walk-forward for one instrument (needs
backtests). Under the venue's HEDGING OMS each round trip is its own closed Position, so every
closed trade is a real one; only positions still open at the window end (no close time) are skipped.
"""

from typing import Any

import pandas as pd

from qplus.backtest.edge.engine import _data_span
from qplus.backtest.edge.walkforward import calmar_score, split_windows, walk_forward_windows
from qplus.backtest.foundation.execution import extract_trade_pnls
from qplus.backtest.foundation.grid import expand_grid
from qplus.backtest.foundation.recipe import SweepRecipe

# ``pnl_base`` is the realized PnL in the account currency at the extraction's BASE risk
# (risk_per_trade=1%), i.e. money -- not a percentage. It COMPOUNDS with the growing equity, so it
# must never be scaled linearly to another risk. ``r`` is the scale-invariant twin: the PnL divided
# by the risk that trade actually took. Re-book ``r * risk_amount`` to size at any flat risk.
_COLUMNS = ["market", "ts_opened", "ts_closed", "pnl_base", "entry", "exit", "sl_pct", "r"]


def assign_r(
    rows: list[dict[str, Any]], start_balance: float, base_risk_frac: float
) -> list[dict[str, Any]]:
    """Add each trade's R-multiple: ``pnl / (base_risk * equity when it was booked)``.

    The backtest sizes every position at ``base_risk_frac`` of the *current* equity, so the risk a
    trade took is recovered by walking the equity forward in close order. Call this per WINDOW: each
    walk-forward window is its own backtest starting at ``start_balance``, so a single continuous
    walk across windows would invent compounding that never happened.

    R is what makes the framework sizing-agnostic: it is independent of the backtest's own
    compounding, so any flat or dynamic risk policy can re-book it linearly.
    """
    equity = start_balance
    for row in sorted(rows, key=lambda r: r["ts_closed"]):
        risk = base_risk_frac * equity
        row["r"] = row["pnl_base"] / risk if risk > 0 else 0.0
        equity += row["pnl_base"]
    return rows


def timed_trades_from_report(
    pos: pd.DataFrame, market: str, sl_pct: float
) -> list[dict[str, Any]]:
    """Extract closed trades ``(ts_opened, ts_closed, pnl, entry, exit, sl_pct)`` from a report.

    ``sl_pct`` is the stop-loss % this window traded at -- recorded per trade so the overnight
    swap cost can be priced exactly (it depends on the stop distance), including the walk-forward
    holdout where the SL is re-optimised per window.
    """
    out: list[dict[str, Any]] = []
    for _, row in pos.iterrows():
        if pd.isna(row["ts_closed"]):  # still open at the window end -> skip
            continue
        pnl = float(str(row["realized_pnl"]).split()[0].replace("_", ""))
        out.append(
            {
                "market": market,
                "ts_opened": int(pd.Timestamp(row["ts_opened"]).value),
                "ts_closed": int(pd.Timestamp(row["ts_closed"]).value),
                "pnl_base": pnl,
                "entry": float(row["avg_px_open"]),
                "exit": float(row["avg_px_close"]),
                "sl_pct": float(sl_pct),
            }
        )
    return out


def extract_market_trades(
    recipe: SweepRecipe,
    *,
    train_months: int,
    test_months: int,
    step_months: int,
    param_grid: dict[str, list[Any]] | None = None,
    holdout_months: int = 0,
    phase: str = "select",
    embargo_days: int = 0,
    fixed_params: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Walk-forward one instrument and return every OOS trade with timestamps + prices.

    Assumes the catalog is already seeded. Per window, optimizes on train by the
    drawdown-adjusted Calmar score, then records the timed trades of the test window.

    If ``fixed_params`` is given, the per-window optimization is SKIPPED and those parameters
    are used in every window instead -- the frozen-config walk-forward. Run over the same
    windows as the optimized version it isolates one effect: the cost of trading fixed SL/TP
    (as we do live) versus re-optimising each window (what the holdout otherwise validates).

    For a clean portfolio stream the caller MUST pass non-overlapping windows
    (``step_months == test_months``); otherwise trades in the overlap are recorded in two
    windows and double-counted (F1). ``holdout_months`` / ``phase`` reserve/select the
    final untouched slice (F2), mirroring :func:`qplus.backtest.edge.engine.run_walkforward`.
    """
    from nautilus_trader.backtest.node import BacktestNode

    if step_months < test_months:
        # N5: overlapping test windows would record the same trade in two windows and
        # double-count it in the portfolio stream. Require non-overlapping windows.
        raise ValueError(
            f"step_months ({step_months}) < test_months ({test_months}) -> overlapping test "
            "windows would double-count trades; pass step_months == test_months"
        )
    grid = param_grid if param_grid is not None else recipe.PARAM_GRID
    combos = expand_grid(grid)
    start, end = _data_span(recipe.CSV_PATH)
    windows = walk_forward_windows(
        start,
        end,
        train_months=train_months,
        test_months=test_months,
        step_months=step_months,
        embargo_days=embargo_days,
    )
    selection, holdout = split_windows(windows, end, holdout_months)
    windows = holdout if phase == "holdout" else selection
    market = str(recipe.INSTRUMENT.raw_symbol)

    rows: list[dict[str, Any]] = []
    for window in windows:
        if fixed_params is not None:
            best = fixed_params  # frozen config: no per-window optimization
        else:
            best, best_score = combos[0], float("-inf")
            for params in combos:
                pnls, equity = extract_trade_pnls(
                    recipe.build_run_config(
                        params,
                        start=window.train_start.isoformat(),
                        end=window.train_end.isoformat(),
                    )
                )
                score = calmar_score(pnls, equity)
                if score > best_score:
                    best_score, best = score, params
        cfg = recipe.build_run_config(
            best, start=window.test_start.isoformat(), end=window.test_end.isoformat()
        )
        node = BacktestNode(configs=[cfg])
        try:
            node.run()
            pos = node.get_engines()[0].trader.generate_positions_report()
        finally:
            node.dispose()  # type: ignore[no-untyped-call]
        window_rows = timed_trades_from_report(pos, market, float(best["stop_loss_pct"]))
        # Per-window R: this window's backtest started fresh at the recipe's start balance.
        rows.extend(assign_r(window_rows, recipe.start_balance, recipe.base_risk_frac))
    return pd.DataFrame(rows, columns=_COLUMNS)
