"""Monte-Carlo equity report for a single backtest recipe.

Runs a recipe once, extracts the realized PnL of each closed trade, and produces:

- a Monte-Carlo fan chart (many bootstrapped equity paths + the actual curve),
  saved as a PNG under ``reports/``, and
- summary statistics (final-equity percentiles, drawdown, probability of profit).

Run from the repo root::

    uv run python -m qplus.backtest.report config/backtest/rsi_wpr_bb_xauusd.py

Note: the paths are bootstrapped from the *in-sample* trades, so the fan shows how
sensitive the result is to trade order/selection -- not an out-of-sample forecast.
"""

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from nautilus_trader.backtest.node import BacktestNode  # noqa: E402
from nautilus_trader.config import BacktestRunConfig  # noqa: E402
from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog  # noqa: E402

from qplus.backtest.montecarlo import (  # noqa: E402
    equity_curve,
    monte_carlo_paths,
    summarize,
)
from qplus.backtest.runner import load_config_module  # noqa: E402

_N_SIMS = 500
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _parse_money(value: object) -> float:
    """Parse a NautilusTrader money string like ``'1784.69 USD'`` into a float."""
    return float(str(value).split()[0].replace("_", ""))


def extract_trade_pnls(run_config: BacktestRunConfig) -> tuple[list[float], float]:
    """Run the config and return (realized PnL per trade, starting equity)."""
    node = BacktestNode(configs=[run_config])
    try:
        node.run()
        engine = node.get_engines()[0]
        positions = engine.trader.generate_positions_report()
        pnls = [_parse_money(v) for v in positions["realized_pnl"]]
    finally:
        node.dispose()  # type: ignore[no-untyped-call]
    start_equity = _parse_money(run_config.venues[0].starting_balances[0])
    return pnls, start_equity


def plot_monte_carlo(
    paths: np.ndarray,
    actual: np.ndarray,
    start_equity: float,
    out_png: Path,
    title: str,
) -> None:
    """Save the Monte-Carlo fan chart (bootstrapped paths + the actual curve)."""
    x = range(paths.shape[1])
    fig, ax = plt.subplots(figsize=(11, 6))
    for path in paths:
        ax.plot(x, path, color="0.7", linewidth=0.4, alpha=0.12)
    ax.plot(x, np.median(paths, axis=0), color="tab:blue", linewidth=1.5, label="MC median")
    ax.plot(
        x,
        np.percentile(paths, 5, axis=0),
        color="tab:blue",
        linewidth=1.0,
        linestyle="--",
        label="MC 5th / 95th pct",
    )
    ax.plot(x, np.percentile(paths, 95, axis=0), color="tab:blue", linewidth=1.0, linestyle="--")
    ax.plot(range(len(actual)), actual, color="black", linewidth=2.0, label="actual")
    ax.axhline(start_equity, color="0.5", linewidth=0.8)
    ax.set_xlabel("trade #")
    ax.set_ylabel("equity (USD)")
    ax.set_title(f"Monte-Carlo equity paths -- {title}")
    ax.legend(loc="upper left")
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=120)
    plt.close(fig)


def main(argv: list[str] | None = None) -> None:
    """CLI entry point: run a recipe, Monte-Carlo its trades, save the chart."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit("usage: python -m qplus.backtest.report <recipe.py>")
    path = Path(args[0])
    module = load_config_module(path)

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

    run_config = module.build_run_config(bypass_logging=True)
    pnls, start_equity = extract_trade_pnls(run_config)
    if not pnls:
        raise SystemExit("No trades were produced -- nothing to analyse.")

    paths = monte_carlo_paths(pnls, n_sims=_N_SIMS, start_equity=start_equity)
    stats = summarize(paths, start_equity)
    actual = equity_curve(pnls, start_equity)

    out_png = _REPO_ROOT / "reports" / f"montecarlo_{path.stem}.png"
    plot_monte_carlo(paths, actual, start_equity, out_png, path.stem)

    print("\n===== Monte-Carlo summary =====")
    print(f"trades:              {len(pnls)}")
    print(f"start equity:        {start_equity:,.0f}")
    print(f"actual final equity: {actual[-1]:,.0f}")
    print(f"MC median final:     {stats['final_median']:,.0f}")
    print(f"MC 5th / 95th pct:   {stats['final_p05']:,.0f} / {stats['final_p95']:,.0f}")
    print(f"probability of profit: {stats['prob_profit']:.1%}")
    print(f"median max drawdown:   {stats['max_dd_median']:.1%}")
    print(f"95th pct max drawdown: {stats['max_dd_p95']:.1%}")
    print(f"\nChart: {out_png}")


if __name__ == "__main__":
    main()
