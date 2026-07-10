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

    uv run python -m qplus.backtest.pipeline config/study/robustness.py <run_dir>/study.csv
"""

import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from qplus.backtest.broker import TTP_MARKETS
from qplus.backtest.config import load_config_module
from qplus.backtest.foundation.recipe import SweepRecipe
from qplus.backtest.portfolio import scorecard
from qplus.backtest.portfolio.curves import load_daily_close, load_daily_extremes
from qplus.backtest.portfolio.trades import extract_market_trades
from qplus.backtest.select import universe

# extract_fn(market, config_overrides, train_months) -> timed trades for that instrument.
ExtractFn = Callable[[str, dict[str, Any], int], pd.DataFrame]


@dataclass(frozen=True)
class PipelineResult:
    """The end-to-end outcome: what was selected and how it scores."""

    selection: universe.Selection
    portfolio: scorecard.PortfolioResult
    verdict: scorecard.Verdict


def run_pipeline(
    study_df: pd.DataFrame,
    extract_fn: ExtractFn,
    daily_close: dict[str, pd.Series],
    *,
    variations: dict[str, dict[str, Any]],
    daily_high: dict[str, pd.Series] | None = None,
    daily_low: dict[str, pd.Series] | None = None,
    start_balance: float = 200_000.0,
    limit_frac: float = 0.06,
    train_months: int | None = None,
    force_variation: str | None = None,
) -> PipelineResult:
    """Stage 2 -> extraction -> Stage 3/4, returning the selection and the scorecard.

    Passing ``daily_high``/``daily_low`` makes the drawdown feasibility use the intraday-worst
    equity (H1) rather than the EOD close. ``force_variation`` overrides the automatic
    return-first selection to score a specific variation instead (its best train-length + its
    own qualifying universe) -- for comparing candidates head to head.
    """
    df = study_df[study_df["variation"] == force_variation] if force_variation else study_df
    selection = universe.select(df)
    tm = train_months if train_months is not None else selection.train_months
    overrides = variations[selection.variation]
    frames = [extract_fn(market, overrides, tm) for market in selection.instruments]
    trades = pd.concat(frames, ignore_index=True)
    result = scorecard.score(
        trades,
        daily_close,
        daily_high=daily_high,
        daily_low=daily_low,
        start_balance=start_balance,
        limit_frac=limit_frac,
    )
    verdict = scorecard.acceptance_verdict(result, trades, start_balance=start_balance)
    return PipelineResult(selection=selection, portfolio=result, verdict=verdict)


def make_extract_fn(
    instrument_specs: dict[str, tuple[Any, str, float]],
    *,
    test_months: int,
    param_grid: dict[str, list[Any]],
    holdout_months: int = 0,
    phase: str = "holdout",
    embargo_days: int = 0,
) -> ExtractFn:
    """Default extractor for the portfolio stream.

    Enforces **non-overlapping** windows (``step = test``) so no trade is double-counted
    (F1), and extracts the reserved-**holdout** slice by default so the portfolio is scored
    once on data no stage selected on (F2).
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
        )

    return extract


def main(argv: list[str] | None = None) -> None:
    """CLI: run the pipeline from a study config module + a Stage 1 study.csv.

    Extra args are variation names to force and compare head to head, e.g.::

        python -m qplus.backtest.pipeline config/study/robustness.py <study.csv> \
            no_confirms no_bb_wpr ema20

    With no variation args it auto-selects (return-first) as before.
    """
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        raise SystemExit(
            "usage: python -m qplus.backtest.pipeline <study_config.py> <study.csv> [variation ...]"
        )
    cfg = load_config_module(Path(args[0]))
    study_df = pd.read_csv(args[1])
    forced = args[2:]  # variation names to force; empty -> auto-select once

    holdout_m = int(getattr(cfg, "HOLDOUT_MONTHS", 0))
    specs = {str(f().raw_symbol): (f, csv, lev) for f, csv, lev in cfg.INSTRUMENTS}
    extract_fn = make_extract_fn(
        specs,
        test_months=int(getattr(cfg, "TEST_MONTHS", 6)),
        param_grid=cfg.PARAM_GRID,
        holdout_months=holdout_m,
        phase="holdout",
        embargo_days=int(getattr(cfg, "EMBARGO_DAYS", 0)),
    )
    # Load each instrument's daily data once (variations use different subsets of it).
    daily_close = {m: load_daily_close(str(specs[m][1])) for m in specs}
    extremes = {m: load_daily_extremes(str(specs[m][1])) for m in specs}
    daily_high = {m: hl[0] for m, hl in extremes.items()}
    daily_low = {m: hl[1] for m, hl in extremes.items()}

    rows: list[tuple[str, PipelineResult]] = []
    for fv in forced or [None]:  # type: ignore[list-item]
        result = run_pipeline(
            study_df,
            extract_fn,
            daily_close,
            variations=cfg.VARIATIONS,
            daily_high=daily_high,
            daily_low=daily_low,
            force_variation=fv,
        )
        s, p, v = result.selection, result.portfolio, result.verdict
        label = fv or "AUTO"
        print(
            f"\n[{label}] structure {s.variation} @ {s.train_months}m, "
            f"{len(s.instruments)} markets | HOLDOUT {p.years}y, {p.n_trades} trades"
        )
        # Headline = the HONEST flat live-risk numbers (what we plan/trade). The ceiling is only
        # a headroom reference (compounded, over-optimistic) -- never the planning figure.
        print(
            f"  @ {p.live_risk_pct:.2f}% flat: {p.live_ann_pct:+.1f}%/yr "
            f"(EUR {p.live_return_eur:,.0f}/yr), maxDD {p.live_max_dd_pct:.1f}%, "
            f"MC profit {v.prob_profit:.0%} | VERDICT {'PASS' if v.passed else 'FAIL'}"
        )
        print(f"    headroom: DD ceiling allows up to {p.flat_risk * 0.01 * 100:.2f}% flat risk")
        rows.append((label, result))

    print("\n===== comparison (HONEST flat live-risk, HOLDOUT, net of costs) =====")
    print(
        f"{'variation':14s} {'trn':>4s} {'mkts':>4s} {'risk':>6s} "
        f"{'ann':>8s} {'EUR/yr':>10s} {'maxDD':>6s} ok"
    )
    for label, r in rows:
        s, p, v = r.selection, r.portfolio, r.verdict
        print(
            f"{label:14s} {s.train_months:>4d}m {len(s.instruments):>4d} "
            f"{p.live_risk_pct:>5.2f}% {p.live_ann_pct:>+7.1f}% {p.live_return_eur:>10,.0f} "
            f"{p.live_max_dd_pct:>5.1f}% {'PASS' if v.passed else 'FAIL'}"
        )


if __name__ == "__main__":
    main()
