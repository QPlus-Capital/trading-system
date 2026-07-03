"""Stress testing: does the strategy survive worse conditions?

Runs a single-strategy recipe under adverse scenarios and prints a comparison of
return, max drawdown and trade count:

- **baseline** -- honest costs, full history;
- **higher slippage** -- re-import the data with a wider spread;
- **crisis windows** -- restrict to historical stress periods (gold crash 2013,
  COVID 2020, 2022 sell-off).

A robust strategy degrades gracefully; a collapse under mild stress is a warning.

Usage::

    uv run python -m qplus.backtest.validation.stress config/backtest/rsi_wpr_bb_xauusd.py
"""

import sys
import tempfile
from pathlib import Path
from typing import Any

from nautilus_trader.persistence.catalog.parquet import ParquetDataCatalog

from qplus.backtest.config import load_config_module
from qplus.backtest.foundation.execution import extract_trade_pnls
from qplus.backtest.foundation.montecarlo import equity_curve, max_drawdown
from qplus.data_ingest.mt5_csv import write_mt5_catalog

# (name, ISO start, ISO end) crisis windows.
_CRISIS_WINDOWS = [
    ("gold_crash_2013", "2013-04-01", "2013-09-01"),
    ("covid_2020", "2020-02-01", "2020-06-01"),
    ("selloff_2022", "2022-02-01", "2022-11-01"),
]
_SLIPPAGE_POINTS = [20.0, 50.0]


def _metrics(pnls: list[float], start_equity: float) -> dict[str, Any]:
    equity = equity_curve(pnls, start_equity)
    return {
        "trades": len(pnls),
        "return_pct": round((float(equity[-1]) - start_equity) / start_equity * 100, 2),
        "max_dd_pct": round(max_drawdown(equity) * 100, 2),
    }


def main(argv: list[str] | None = None) -> None:
    """CLI: run baseline, slippage and crisis-window stress scenarios."""
    args = sys.argv[1:] if argv is None else argv
    if not args:
        raise SystemExit("usage: python -m qplus.backtest.validation.stress <recipe.py>")
    module = load_config_module(Path(args[0]))

    # Seed the main catalog only if the instrument is missing (avoid duplicate bars).
    catalog_dir = Path(module.CATALOG_PATH)
    have = (
        {str(i.id) for i in ParquetDataCatalog(str(catalog_dir)).instruments()}
        if catalog_dir.exists()
        else set()
    )
    if str(module.INSTRUMENT.id) not in have:
        module.seed_catalog()

    rows: list[dict[str, Any]] = []

    def record(name: str, pnls: list[float], start_equity: float) -> None:
        rows.append({"scenario": name, **_metrics(pnls, start_equity)})
        print(f"  {name}: {rows[-1]}")

    print("baseline ...")
    pnls, start_equity = extract_trade_pnls(module.build_run_config(bypass_logging=True))
    record("baseline", pnls, start_equity)

    for points in _SLIPPAGE_POINTS:
        print(f"slippage {points:g} points ...")
        with tempfile.TemporaryDirectory() as tmp:
            write_mt5_catalog(
                module.CSV_PATH,
                tmp,
                instrument=module.INSTRUMENT,
                bar_spec=module.BAR_SPEC,
                slippage_points=points,
            )
            pnls, start_equity = extract_trade_pnls(
                module.build_run_config(catalog_path=tmp, bypass_logging=True)
            )
        record(f"slippage_{points:g}pts", pnls, start_equity)

    for name, start, end in _CRISIS_WINDOWS:
        print(f"crisis {name} ...")
        pnls, start_equity = extract_trade_pnls(
            module.build_run_config(bypass_logging=True, start=start, end=end)
        )
        record(name, pnls, start_equity)

    print("\n===== Stress test =====")
    header = f"{'scenario':<20}{'trades':>8}{'return %':>12}{'max dd %':>12}"
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['scenario']:<20}{row['trades']:>8}{row['return_pct']:>12}{row['max_dd_pct']:>12}"
        )


if __name__ == "__main__":
    main()
