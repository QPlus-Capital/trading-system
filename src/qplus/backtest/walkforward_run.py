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

    uv run python -m qplus.backtest.walkforward_run config/backtest/sweep_rsi_wpr_bb_xauusd.py
    uv run python -m qplus.backtest.walkforward_run config/backtest/sweep_rsi_wpr_bb_xauusd.py 2
"""

import sys
from pathlib import Path
from typing import Any

import pandas as pd
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from qplus.backtest.montecarlo import equity_curve, monte_carlo_paths, summarize
from qplus.backtest.report import extract_trade_pnls, plot_monte_carlo
from qplus.backtest.runner import load_config_module
from qplus.backtest.sweep import expand_grid
from qplus.backtest.walkforward import (
    calmar_score,
    run_walk_forward,
    walk_forward_efficiency,
    walk_forward_windows,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TRAIN_MONTHS, _TEST_MONTHS, _STEP_MONTHS = 24, 6, 6


def _data_span(csv_path: str | Path) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Return (first, last) bar timestamp from an MT5 CSV (fast date-only read)."""
    df = pd.read_csv(csv_path, sep="\t", usecols=["<DATE>", "<TIME>"])
    stamps = pd.to_datetime(df["<DATE>"] + " " + df["<TIME>"], format="%Y.%m.%d %H:%M:%S", utc=True)
    return stamps.iloc[0], stamps.iloc[-1]


def main(argv: list[str] | None = None) -> None:
    """CLI: run the walk-forward validation for a sweep config module."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit(
            "usage: python -m qplus.backtest.walkforward_run <sweep_config.py> [max_windows]"
        )
    path = Path(args[0])
    module = load_config_module(path)
    max_windows = int(args[1]) if len(args) > 1 else None

    catalog_dir = Path(module.CATALOG_PATH)
    needed = str(module.INSTRUMENT.id)
    have = (
        {str(i.id) for i in ParquetDataCatalog(str(catalog_dir)).instruments()}
        if catalog_dir.exists()
        else set()
    )
    if needed not in have:
        print(f"Instrument {needed} not in catalog -> seeding ...")
        module.seed_catalog()

    start, end = _data_span(module.CSV_PATH)
    windows = walk_forward_windows(
        start, end, train_months=_TRAIN_MONTHS, test_months=_TEST_MONTHS, step_months=_STEP_MONTHS
    )
    if max_windows is not None:
        windows = windows[:max_windows]
    combos = expand_grid(module.PARAM_GRID)
    print(
        f"{len(windows)} windows x {len(combos)} combos = {len(windows) * len(combos)} train runs"
    )

    def optimize(
        train_start: pd.Timestamp, train_end: pd.Timestamp
    ) -> tuple[dict[str, Any], float]:
        best_params: dict[str, Any] = combos[0]
        best_score = float("-inf")
        best_return = 0.0
        for params in combos:
            pnls, start_equity = extract_trade_pnls(
                module.build_run_config(
                    params, start=train_start.isoformat(), end=train_end.isoformat()
                )
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
        return extract_trade_pnls(
            module.build_run_config(params, start=test_start.isoformat(), end=test_end.isoformat())
        )

    results = run_walk_forward(windows, optimize, evaluate)

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
        png = _REPO_ROOT / "reports" / f"walkforward_montecarlo_{path.stem}.png"
        plot_monte_carlo(
            paths, equity_curve(dollar_pnls, base), base, png, f"OOS Monte-Carlo -- {path.stem}"
        )
        print("\n===== Out-of-sample Monte-Carlo =====")
        print(f"OOS trades:            {len(oos_returns)}")
        print(f"probability of profit: {stats['prob_profit']:.0%}")
        print(f"median max drawdown:   {stats['max_dd_median']:.1%}")
        print(f"95th pct max drawdown: {stats['max_dd_p95']:.1%}")
        print(f"Chart: {png}")


if __name__ == "__main__":
    main()
