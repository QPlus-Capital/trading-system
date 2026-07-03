"""Compute the deflated Sharpe ratio and PBO for a sweep's strategy on real data.

Runs every parameter combination over the full history, then:

- picks the best combination by the drawdown-adjusted Calmar score and reports its
  **deflated Sharpe ratio** (corrected for the number of trials);
- builds a (time-slice x trial) return matrix and reports the **probability of
  backtest overfitting** (PBO).

Usage::

    uv run python -m qplus.backtest.validation.validate config/backtest/sweep_rsi_wpr_bb_xauusd.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from nautilus_trader.backtest.node import BacktestNode
from nautilus_trader.config import BacktestRunConfig
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from qplus.backtest.config import load_config_module
from qplus.backtest.edge.walkforward import calmar_score
from qplus.backtest.foundation.grid import expand_grid
from qplus.backtest.foundation.overfitting import deflated_sharpe_ratio, pbo, sharpe_ratio

_N_SLICES = 20
_N_SPLITS = 10


def _money(value: object) -> float:
    return float(str(value).split()[0].replace("_", ""))


def _extract_trades(run_config: BacktestRunConfig) -> tuple[list[float], list[pd.Timestamp], float]:
    """Run a config and return (per-trade returns, close timestamps, start equity)."""
    node = BacktestNode(configs=[run_config])
    try:
        node.run()
        positions = node.get_engines()[0].trader.generate_positions_report()
        closed = positions[positions["ts_closed"].notna()]
        start_equity = _money(run_config.venues[0].starting_balances[0])
        returns = [_money(v) / start_equity for v in closed["realized_pnl"]]
        timestamps = [pd.Timestamp(t) for t in closed["ts_closed"]]
    finally:
        node.dispose()  # type: ignore[no-untyped-call]
    return returns, timestamps, start_equity


def main(argv: list[str] | None = None) -> None:
    """CLI: compute deflated Sharpe ratio and PBO for a sweep config module."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit("usage: python -m qplus.backtest.validation.validate <sweep_config.py>")
    module = load_config_module(Path(args[0]))

    catalog_dir = Path(module.CATALOG_PATH)
    have = (
        {str(i.id) for i in ParquetDataCatalog(str(catalog_dir)).instruments()}
        if catalog_dir.exists()
        else set()
    )
    if str(module.INSTRUMENT.id) not in have:
        print("Seeding catalog ...")
        module.seed_catalog()

    combos = expand_grid(module.PARAM_GRID)
    print(f"Running {len(combos)} trials over full history ...")

    returns_per_trial: list[list[float]] = []
    ts_per_trial: list[list[pd.Timestamp]] = []
    sharpes: list[float] = []
    for i, params in enumerate(combos, start=1):
        returns, timestamps, _ = _extract_trades(module.build_run_config(params))
        returns_per_trial.append(returns)
        ts_per_trial.append(timestamps)
        sharpes.append(sharpe_ratio(returns))
        print(f"[{i}/{len(combos)}] trades={len(returns)}")

    scores = [calmar_score(r, 1.0) for r in returns_per_trial]
    best = int(np.argmax(scores))
    sharpe_variance = float(np.var(sharpes, ddof=1))
    dsr = deflated_sharpe_ratio(
        returns_per_trial[best], n_trials=len(combos), sharpe_variance=sharpe_variance
    )

    # Build the (time-slice x trial) return matrix for PBO.
    all_ts = [t for trial in ts_per_trial for t in trial]
    edges = pd.date_range(min(all_ts), max(all_ts), periods=_N_SLICES + 1)
    edge_ns = np.array([e.value for e in edges])
    matrix = np.zeros((_N_SLICES, len(combos)))
    for j, (returns, timestamps) in enumerate(zip(returns_per_trial, ts_per_trial, strict=True)):
        for ret, ts in zip(returns, timestamps, strict=True):
            idx = int(
                np.clip(np.searchsorted(edge_ns, ts.value, side="right") - 1, 0, _N_SLICES - 1)
            )
            matrix[idx, j] += ret
    pbo_value = pbo(matrix.tolist(), n_splits=_N_SPLITS)

    print("\n===== Overfitting check =====")
    print(f"trials:                 {len(combos)}")
    print(f"best params (by Calmar): {combos[best]}")
    print(f"deflated Sharpe ratio:   {dsr:.3f}   (prob. the edge is real after N trials)")
    print(f"prob. of overfitting:    {pbo_value:.2f}   (0 = robust, ~0.5 = chance)")


if __name__ == "__main__":
    main()
