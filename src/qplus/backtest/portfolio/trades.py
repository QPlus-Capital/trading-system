"""Stage 1 -> 3 connective tissue: the timestamped OOS trade stream.

The portfolio stages (3/4) need each out-of-sample trade with its open/close time and
entry/exit price, so the account's daily equity can be reconstructed. This runs the same
walk-forward as Stage 1 (choose parameters on train by Calmar) but, on each test window,
records the timed trades instead of only their PnL.

``timed_trades_from_report`` is the pure extraction from a NautilusTrader positions report
(unit-tested); ``extract_market_trades`` drives the walk-forward for one instrument (needs
backtests). Under NETTING every closed round-trip except the last is flagged
``is_snapshot=True`` but is a real trade -- kept; only positions still open at the window
end (no close time) are skipped.
"""

from typing import Any

import pandas as pd

from qplus.backtest.edge.engine import _data_span
from qplus.backtest.edge.walkforward import calmar_score, walk_forward_windows
from qplus.backtest.foundation.execution import extract_trade_pnls
from qplus.backtest.foundation.grid import expand_grid
from qplus.backtest.foundation.recipe import SweepRecipe

_COLUMNS = ["market", "ts_opened", "ts_closed", "pnl_1pct", "entry", "exit"]


def timed_trades_from_report(pos: pd.DataFrame, market: str) -> list[dict[str, Any]]:
    """Extract closed trades ``(ts_opened, ts_closed, pnl, entry, exit)`` from a report."""
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
                "pnl_1pct": pnl,
                "entry": float(row["avg_px_open"]),
                "exit": float(row["avg_px_close"]),
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
) -> pd.DataFrame:
    """Walk-forward one instrument and return every OOS trade with timestamps + prices.

    Assumes the catalog is already seeded. Per window, optimizes on train by the
    drawdown-adjusted Calmar score, then records the timed trades of the test window.
    """
    from nautilus_trader.backtest.node import BacktestNode

    grid = param_grid if param_grid is not None else recipe.PARAM_GRID
    combos = expand_grid(grid)
    start, end = _data_span(recipe.CSV_PATH)
    windows = walk_forward_windows(
        start, end, train_months=train_months, test_months=test_months, step_months=step_months
    )
    market = str(recipe.INSTRUMENT.raw_symbol)

    rows: list[dict[str, Any]] = []
    for window in windows:
        best, best_score = combos[0], float("-inf")
        for params in combos:
            pnls, equity = extract_trade_pnls(
                recipe.build_run_config(
                    params, start=window.train_start.isoformat(), end=window.train_end.isoformat()
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
        rows.extend(timed_trades_from_report(pos, market))
    return pd.DataFrame(rows, columns=_COLUMNS)
