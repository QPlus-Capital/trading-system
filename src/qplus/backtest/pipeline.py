"""Pipeline runner: chain the framework stages into one strategy evaluation.

Given a Stage 1 study table (per instrument x variation x training length, with the
risk-adjusted metrics), the pipeline:

1. **Stage 2** -- picks the global structure + tradeable universe (:mod:`select.universe`);
2. **Stage 1->3** -- extracts the timed OOS trade stream for that structure over the chosen
   instruments (:mod:`portfolio.trades`);
3. **Stage 3/4** -- scores portfolio feasibility (flat vs throttle) under the prop-firm
   hybrid rule (:mod:`portfolio.scorecard`).

Stage 1 (the study) is the heavy compute and is run first, separately, to produce the
study table this consumes. The per-instrument extraction is injected (``extract_fn``) so
the chaining is unit-testable without backtests.

Usage::

    uv run python -m qplus.backtest.pipeline config/study/overnight.py reports/study/run_x/study.csv
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from qplus.backtest.config import load_config_module
from qplus.backtest.foundation.recipe import SweepRecipe
from qplus.backtest.portfolio import scorecard
from qplus.backtest.portfolio.curves import load_daily_close
from qplus.backtest.portfolio.trades import extract_market_trades
from qplus.backtest.select import universe

# extract_fn(market, config_overrides, train_months) -> timed trades for that instrument.
ExtractFn = Callable[[str, dict[str, Any], int], pd.DataFrame]


@dataclass(frozen=True)
class PipelineResult:
    """The end-to-end outcome: what was selected and how it scores."""

    selection: universe.Selection
    portfolio: scorecard.PortfolioResult


def run_pipeline(
    study_df: pd.DataFrame,
    extract_fn: ExtractFn,
    daily_close: dict[str, pd.Series],
    *,
    variations: dict[str, dict[str, Any]],
    start_balance: float = 200_000.0,
    limit_frac: float = 0.06,
    train_months: int | None = None,
) -> PipelineResult:
    """Stage 2 -> extraction -> Stage 3/4, returning the selection and the scorecard."""
    selection = universe.select(study_df)
    tm = train_months if train_months is not None else selection.train_months
    overrides = variations[selection.variation]
    frames = [extract_fn(market, overrides, tm) for market in selection.instruments]
    trades = pd.concat(frames, ignore_index=True)
    result = scorecard.score(
        trades, daily_close, start_balance=start_balance, limit_frac=limit_frac
    )
    return PipelineResult(selection=selection, portfolio=result)


def make_extract_fn(
    instrument_specs: dict[str, tuple[Any, str, float]],
    *,
    test_months: int,
    param_grid: dict[str, list[Any]],
    holdout_months: int = 0,
    phase: str = "holdout",
) -> ExtractFn:
    """Default extractor for the portfolio stream.

    Enforces **non-overlapping** windows (``step = test``) so no trade is double-counted
    (F1), and extracts the reserved-**holdout** slice by default so the portfolio is scored
    once on data no stage selected on (F2).
    """

    def extract(market: str, overrides: dict[str, Any], train_months: int) -> pd.DataFrame:
        factory, csv, leverage = instrument_specs[market]
        recipe = SweepRecipe(
            factory(), csv, leverage=leverage, param_grid=param_grid, config_overrides=overrides
        )
        return extract_market_trades(
            recipe,
            train_months=train_months,
            test_months=test_months,
            step_months=test_months,  # F1: non-overlapping -> no double-counted trades
            param_grid=param_grid,
            holdout_months=holdout_months,
            phase=phase,
        )

    return extract


def main(argv: list[str] | None = None) -> None:
    """CLI: run the pipeline from a study config module + a Stage 1 study.csv."""
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        raise SystemExit("usage: python -m qplus.backtest.pipeline <study_config.py> <study.csv>")
    cfg = load_config_module(Path(args[0]))
    study_df = pd.read_csv(args[1])

    holdout_m = int(getattr(cfg, "HOLDOUT_MONTHS", 0))
    specs = {str(f().raw_symbol): (f, csv, lev) for f, csv, lev in cfg.INSTRUMENTS}
    extract_fn = make_extract_fn(
        specs,
        test_months=int(getattr(cfg, "TEST_MONTHS", 6)),
        param_grid=cfg.PARAM_GRID,
        holdout_months=holdout_m,
        phase="holdout",
    )

    selection = universe.select(study_df)
    daily_close = {m: load_daily_close(str(specs[m][1])) for m in selection.instruments}
    print(f"Stage 2 -> structure '{selection.variation}' @ train {selection.train_months}m")
    print(f"          universe: {', '.join(selection.instruments)}")
    print(f"Stage 3/4 scored on the reserved {holdout_m}-month holdout (untouched by selection)")

    result = run_pipeline(study_df, extract_fn, daily_close, variations=cfg.VARIATIONS)
    p = result.portfolio
    print("\n===== Stage 3/4 portfolio feasibility (hybrid TTP drawdown, HOLDOUT) =====")
    print(f"trades: {p.n_trades}   span: {p.years} years")
    print(f"flat:     risk {p.flat_risk}x -> {p.flat_return_pct}% ({p.flat_ann_pct}%/yr)")
    print(
        f"throttle: base {p.throttle_base}x -> {p.throttle_return_pct}% "
        f"({p.throttle_ann_pct}%/yr), {p.throttle_gain_pct:+}% vs flat"
    )


if __name__ == "__main__":
    main()
