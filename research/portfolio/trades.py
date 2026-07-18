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

from collections.abc import Callable
from typing import Any

import pandas as pd
from core.broker import TTP_MARKETS

from research.engine.config import extract_trade_pnls
from research.engine.grid import expand_grid
from research.engine.recipe import SweepRecipe
from research.engine.walkforward import calmar_score, split_windows, walk_forward_windows
from research.engine.walkforward_runner import PREROLL, _data_span

# ``pnl_base`` is the realized PnL in the account currency at the extraction's BASE risk
# (risk_per_trade=1%), i.e. money -- not a percentage. It COMPOUNDS with the growing equity, so it
# must never be scaled linearly to another risk. ``r`` is the scale-invariant twin: the PnL divided
# by the risk that trade actually took. Re-book ``r * risk_amount`` to size at any flat risk.
_COLUMNS = [
    "market", "ts_opened", "ts_closed", "pnl_base", "entry", "exit", "sl_pct", "is_long", "r"
]


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
    pos: pd.DataFrame, market: str, sl_pct: float, *, closed_from: pd.Timestamp | None = None
) -> list[dict[str, Any]]:
    """Extract closed trades ``(ts_opened, ts_closed, pnl, entry, exit, sl_pct)`` from a report.

    ``sl_pct`` is the stop-loss % this window traded at -- recorded per trade so the overnight
    swap cost can be priced exactly (it depends on the stop distance), including the walk-forward
    holdout where the SL is re-optimised per window.

    ``closed_from`` keeps only trades that RESOLVED at or after that moment (#14). Paired with the
    pre-roll, each trade is attributed to the window its outcome landed in: a position opened
    before a boundary is carried and realised in the next window instead of vanishing, which is
    what live does -- and what previously hid exactly the losses that gap through a stop after a
    boundary.
    """
    out: list[dict[str, Any]] = []
    for _, row in pos.iterrows():
        if pd.isna(row["ts_closed"]):  # still open at the run end -> the NEXT window resolves it
            continue
        if closed_from is not None and pd.to_datetime(row["ts_closed"], utc=True) < closed_from:
            continue  # resolved inside the pre-roll -> belongs to the previous window
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
                # Direction straight from the report (#10). NOTE: our "entry" is the entry PRICE
                # while the report's "entry" is the entry SIDE -- read "side" and read it here,
                # before the name is reused. Swap is direction-dependent, and inferring direction
                # from the outcome misclassifies any trade whose costs flip its sign.
                "is_long": str(row["side"]).upper() == "LONG",
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
    final untouched slice (F2), mirroring
    :func:`research.engine.walkforward_runner.run_walkforward`.
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
        # #14: pre-roll the data so indicators enter the window warm and a position opened just
        # before the boundary is carried; timed_trades_from_report then keeps only what RESOLVED
        # inside the window, so trades are neither dropped at a seam nor counted twice.
        cfg = recipe.build_run_config(
            best,
            start=(window.test_start - PREROLL).isoformat(),
            end=window.test_end.isoformat(),
        )
        node = BacktestNode(configs=[cfg])
        try:
            node.run()
            pos = node.get_engines()[0].trader.generate_positions_report()
        finally:
            node.dispose()  # type: ignore[no-untyped-call]
        window_rows = timed_trades_from_report(
            pos, market, float(best["stop_loss_pct"]), closed_from=window.test_start
        )
        # Per-window R: this window's backtest started fresh at the recipe's start balance.
        rows.extend(assign_r(window_rows, recipe.start_balance, recipe.base_risk_frac))
    return pd.DataFrame(rows, columns=_COLUMNS)


# --- Portfolio-stage extractor factory (injected into stage 3) ---


ExtractFn = Callable[[str, dict[str, Any], int], pd.DataFrame]


def make_extract_fn(
    instrument_specs: dict[str, tuple[Any, str, float]],
    *,
    test_months: int,
    param_grid: dict[str, list[Any]],
    holdout_months: int = 0,
    phase: str = "holdout",
    embargo_days: int = 0,
    start_balance: float = 200_000.0,
    risk_per_trade_pct: float = 1.0,
    fixed_stops: dict[str, dict[str, Any]] | None = None,
) -> ExtractFn:
    """Default extractor for the portfolio stream.

    Enforces **non-overlapping** windows (``step = test``) so no trade is double-counted
    (F1), and extracts the reserved-**holdout** slice by default so the portfolio is scored
    once on data no stage selected on (F2).

    ``start_balance`` / ``risk_per_trade_pct`` are the account the extraction's backtests size
    against; pass the real account so every stage measures the same thing. The per-trade R that
    comes out is scale-invariant either way, but the position quantities are not, and a small
    enough account silently falls back to the fixed trade size.

    ``fixed_stops`` maps a market to the SL/TP it should trade in EVERY window instead of
    re-optimising the stop per window. This validates the config we actually deploy (fixed stops),
    whose gentle tail permits a tradeable size -- as opposed to the re-optimised path, which chases
    the tightest stop on the grid and is tail-capped to an untradeable one.
    """

    def extract(market: str, overrides: dict[str, Any], train_months: int) -> pd.DataFrame:
        factory, csv, leverage = instrument_specs[market]
        # Net-of-cost portfolio: the broker profile applies slippage in-engine (spread +
        # commission are already in), consistent with the study + live, so the feasibility is
        # not over-optimistic (avoids the gross-of-cost sizing trap).
        recipe = SweepRecipe(
            factory(),
            csv,
            leverage=leverage,
            param_grid=param_grid,
            config_overrides=overrides,
            broker=TTP_MARKETS,
            start_balance=start_balance,
            risk_per_trade_pct=risk_per_trade_pct,
        )
        return extract_market_trades(
            recipe,
            train_months=train_months,
            test_months=test_months,
            step_months=test_months,  # F1: non-overlapping -> no double-counted trades
            param_grid=param_grid,
            holdout_months=holdout_months,
            phase=phase,
            embargo_days=embargo_days,
            fixed_params=(fixed_stops or {}).get(market),
        )

    return extract
