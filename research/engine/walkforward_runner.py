"""Walk-forward runner (engine driver).

Wires the pure walk-forward logic to the real backtest engine and a sweep config
module. For each rolling window it:

1. optimizes on the train period -- runs every parameter combination restricted to
   the train dates and picks the best by the drawdown-adjusted Calmar score;
2. evaluates the chosen parameters on the following, unseen test period.

The stitched test windows form the out-of-sample track record; walk-forward
efficiency (mean OOS return / mean in-sample return) summarizes how well the
optimization generalizes. Results are written to ``reports/``.

The sweep config module must define ``PARAM_GRID``, ``build_run_config(params,
start=, end=)``, ``INSTRUMENT``, ``CATALOG_PATH``, ``CSV_PATH`` and ``seed_catalog``.

Usage (optionally limit the number of windows for a quick check)::

    uv run python -m research.engine.walkforward_runner config/backtest/sweep_rsi_wpr_bb_xauusd.py
    uv run python -m research.engine.walkforward_runner config/backtest/sweep_rsi_wpr_bb_xauusd.py 2
"""


import sys
from pathlib import Path
from typing import Any

import pandas as pd
from core.data.mt5_csv import parse_mt5_timestamps, seeded_instruments
from core.paths import REPO_ROOT

from research.engine.config import extract_trade_pnls, load_config_module
from research.engine.grid import expand_grid
from research.engine.montecarlo import equity_curve, monte_carlo_paths, summarize
from research.engine.walkforward import (
    WalkForwardResult,
    calmar_score,
    run_walk_forward,
    split_windows,
    walk_forward_efficiency,
    walk_forward_windows,
)

_REPO_ROOT = REPO_ROOT
_TRAIN_MONTHS, _TEST_MONTHS, _STEP_MONTHS = 24, 6, 6

# #14: read-only warm-up ahead of every window. The signal engine needs ~26 bars before it
# reports "warmed up", but the Wilder-smoothed RSI/EMA keep converging well past that, so this is
# sized generously: 45 days is roughly 190 H4 bars. Trades that resolve inside the pre-roll are
# filtered out (closed_from), so it only ever informs indicators and carries open positions.
PREROLL = pd.Timedelta(days=45)


def _data_span(csv_path: str | Path) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return (first, last) bar timestamp from an MT5 CSV (fast date-only read)."""
    df = pd.read_csv(csv_path, sep="\t", usecols=["<DATE>", "<TIME>"])
    # #18: same conversion as the bars themselves -- the span sets every window boundary, so a
    # server-frame span against real-UTC bars would offset train/test/holdout splits by hours.
    stamps = parse_mt5_timestamps(df)
    return stamps.iloc[0], stamps.iloc[-1]


def run_walkforward(
    recipe: Any,
    *,
    train_months: int = _TRAIN_MONTHS,
    test_months: int = _TEST_MONTHS,
    step_months: int = _STEP_MONTHS,
    max_windows: int | None = None,
    holdout_months: int = 0,
    phase: str = "select",
    embargo_days: int = 0,
    collect_matrix: bool = False,
) -> list[WalkForwardResult]:
    """Run the full walk-forward for a recipe (config module or SweepRecipe).

    The recipe must expose ``CSV_PATH``, ``PARAM_GRID`` and ``build_run_config``.
    Assumes the catalog is already seeded. Returns the per-window results.

    With ``holdout_months > 0`` the last ``holdout_months`` are reserved: ``phase="select"``
    runs only the pre-holdout windows (for study/selection), ``phase="holdout"`` runs only
    the reserved windows (the honest final evaluation of an already-chosen config).

    ``collect_matrix`` additionally scores EVERY grid candidate on each test window, so the
    overfitting statistics get a real per-candidate performance matrix instead of comparing a
    handful of variations (#13). It costs roughly 20-25% more runtime -- the train-window grid
    search already dominates -- so the study opts in and ad-hoc runs do not pay for it.
    """
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
    if max_windows is not None:
        windows = windows[:max_windows]
    combos = expand_grid(recipe.PARAM_GRID)

    def optimize(
        train_start: pd.Timestamp, train_end: pd.Timestamp
    ) -> tuple[dict[str, Any], float]:
        best_params: dict[str, Any] = combos[0]
        best_score = float("-inf")
        best_return = 0.0
        for params in combos:
            pnls, start_equity = extract_trade_pnls(
                recipe.build_run_config(
                    params,
                    start=(train_start - PREROLL).isoformat(),
                    end=train_end.isoformat(),
                    trade_from=train_start.isoformat(),
                ),
                closed_from=train_start,
            )
            score = calmar_score(pnls, start_equity)
            if score > best_score:
                best_score = score
                best_params = params
                curve = equity_curve(pnls, start_equity)
                best_return = (float(curve[-1]) - start_equity) / start_equity
        return best_params, best_return

    def evaluate(
        params: dict[str, Any], test_start: pd.Timestamp, test_end: pd.Timestamp
    ) -> tuple[list[float], float]:
        # #14: READ-ONLY pre-roll -- bars before test_start warm the indicators (live never
        # restarts cold) but trade_from suppresses orders, so a pre-roll trade can never move the
        # balance that the reported trades are sized from. closed_from stays as a safety net.
        return extract_trade_pnls(
            recipe.build_run_config(
                params,
                start=(test_start - PREROLL).isoformat(),
                end=test_end.isoformat(),
                trade_from=test_start.isoformat(),
            ),
            closed_from=test_start,
        )

    return run_walk_forward(windows, optimize, evaluate, combos if collect_matrix else None)


def main(argv: list[str] | None = None) -> None:
    """CLI: run the walk-forward validation for a sweep config module."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit(
            "usage: python -m research.engine.walkforward_runner <sweep_config.py> [max_windows]"
        )
    path = Path(args[0])
    module = load_config_module(path)
    max_windows = int(args[1]) if len(args) > 1 else None

    catalog_dir = Path(module.CATALOG_PATH)
    needed = str(module.INSTRUMENT.id)
    # The presence check IS the staleness gate: a stale catalog is discarded here, so the seeding
    # below cannot be skipped just because the old-frame instrument happened to be present.
    have = seeded_instruments(catalog_dir, {needed: Path(module.CSV_PATH)})
    if needed not in have:
        print(f"Instrument {needed} not in catalog -> seeding ...")
        module.seed_catalog()

    results = run_walkforward(module, max_windows=max_windows)
    print(f"{len(results)} out-of-sample windows evaluated")

    rows = [
        {
            "window": r.window,
            **r.best_params,
            "is_return_pct": round(r.is_return * 100, 2),
            "oos_return_pct": round(r.oos_return * 100, 2),
            "oos_trades": r.oos_trades,
            "oos_max_dd_pct": round(r.oos_max_dd * 100, 2),
        }
        for r in results
    ]
    out_path = _REPO_ROOT / "reports" / f"walkforward_{path.stem}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_path, index=False)

    oos_returns = [r.oos_return for r in results]
    mean_oos = sum(oos_returns) / len(oos_returns) if oos_returns else 0.0
    pct_profitable = sum(1 for x in oos_returns if x > 0) / len(oos_returns) if oos_returns else 0.0

    print("\n===== Walk-forward result (out-of-sample) =====")
    print(f"windows:               {len(results)}")
    print(f"mean OOS return/window: {mean_oos:.2%}")
    print(f"profitable windows:     {pct_profitable:.0%}")
    print(f"walk-forward efficiency: {walk_forward_efficiency(results):.2f}")
    print(f"\nPer-window results: {out_path}")

    # Monte-Carlo on the *out-of-sample* trades (the honest track record).
    base = float(str(module.VENUE.starting_balances[0]).split()[0].replace("_", ""))
    oos_returns = [r for result in results for r in result.oos_returns]
    if oos_returns:
        dollar_pnls = [r * base for r in oos_returns]
        paths = monte_carlo_paths(dollar_pnls, n_sims=500, start_equity=base)
        stats = summarize(paths, base)
        print("\n===== Out-of-sample Monte-Carlo =====")
        print(f"OOS trades:            {len(oos_returns)}")
        print(f"probability of profit: {stats['prob_profit']:.0%}")
        print(f"median max drawdown:   {stats['max_dd_median']:.1%}")
        print(f"95th pct max drawdown: {stats['max_dd_p95']:.1%}")


if __name__ == "__main__":
    main()
