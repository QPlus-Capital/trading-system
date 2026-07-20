"""One continuous out-of-sample run per instrument, governed by a parameter schedule (#32).

The execution half. Independent per-window backtests cannot carry a position across a segment
boundary under the parameters that opened it -- each window is its own engine, so a straddling
position is either dropped or reopened. Running the whole out-of-sample span once, with the
schedule switching parameters for NEW entries only, removes that approximation: a position simply
stays open, on its original stop and target, until it really closes.

Two consequences follow from there being one account instead of many:

* the equity path compounds across the entire span, which is what actually happened, rather than
  restarting at the opening balance every window;
* each trade appears exactly once, so the stream needs no de-duplication at the seams.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

import pandas as pd
from core.strategies.param_schedule import ParamSegment, segment_at

from research.engine.montecarlo import equity_curve, max_drawdown
from research.engine.recipe import SweepRecipe
from research.engine.schedule_builder import build_schedule
from research.engine.walkforward import (
    PREROLL,
    WalkForwardResult,
    WalkForwardWindow,
    combo_key,
)


def stop_loss_lookup(segments: tuple[ParamSegment, ...]) -> Callable[[int], float]:
    """A callable giving the stop a trade opened at ``ts_ns`` was traded with.

    The swap cost is priced off the stop distance, so a stream whose trades were opened under
    different segments must record each trade's own stop rather than one number for the run.
    """

    def resolve(ts_ns: int) -> float:
        seg = segment_at(segments, ts_ns)
        return 0.0 if seg is None else float(seg.stop_loss_pct)

    return resolve


def run_continuous_oos(
    recipe: SweepRecipe,
    segments: tuple[ParamSegment, ...],
    *,
    span_start: pd.Timestamp,
    span_end: pd.Timestamp,
) -> pd.DataFrame:
    """Run the whole out-of-sample span once and return its positions report.

    The run begins a pre-roll before ``span_start`` so the indicators enter the first segment warm.
    Nothing trades in the pre-roll: the schedule has no segment there, and a lookup before the
    first segment authorises nothing. That is the same guarantee ``trade_from_ns`` gives a single
    window, expressed through the schedule so there is one gate rather than two.
    """
    from nautilus_trader.backtest.node import BacktestNode

    if not segments:
        raise ValueError("a continuous run needs a schedule; an empty one authorises no trade")
    cfg = recipe.build_run_config(
        {"segments": segments},
        start=(span_start - PREROLL).isoformat(),
        end=pd.Timestamp(span_end).isoformat(),
    )
    node = BacktestNode(configs=[cfg])
    try:
        node.run()
        report: pd.DataFrame = node.get_engines()[0].trader.generate_positions_report()
        return report
    finally:
        node.dispose()  # type: ignore[no-untyped-call]


def closed_pnls(
    recipe: SweepRecipe,
    segments: tuple[ParamSegment, ...],
    span_start: pd.Timestamp,
    span_end: pd.Timestamp,
) -> list[tuple[int, float]]:
    """``(close timestamp ns, realized PnL)`` for every trade of one continuous run."""
    from research.portfolio.trades import timed_trades_from_report

    pos = run_continuous_oos(recipe, segments, span_start=span_start, span_end=span_end)
    rows = timed_trades_from_report(
        pos, str(recipe.INSTRUMENT.raw_symbol), stop_loss_lookup(segments), closed_from=span_start
    )
    return [(int(row["ts_closed"]), float(row["pnl_base"])) for row in rows]


def constant_schedule(
    params: Mapping[str, Any], span_start: pd.Timestamp, span_end: pd.Timestamp
) -> tuple[ParamSegment, ...]:
    """A schedule that never switches -- one candidate held across the whole span.

    Stage 1 scores every grid candidate on every window to give the overfitting statistics a real
    per-candidate matrix. A candidate is by definition the same parameters everywhere, so it is a
    schedule with a single open segment: one continuous run, not one run per window. That is both
    the same arithmetic and less of it, because the read-only pre-roll is paid once instead of
    once per window.
    """
    return (
        ParamSegment(
            from_ns=int(pd.Timestamp(span_start).value),
            stop_loss_pct=float(params["stop_loss_pct"]),
            take_profit_pct=float(params["take_profit_pct"]),
            entries_allowed=True,
        ),
        ParamSegment(
            from_ns=int(pd.Timestamp(span_end).value),
            stop_loss_pct=0.0,
            take_profit_pct=0.0,
            entries_allowed=False,
        ),
    )


def window_returns(
    closed: Sequence[tuple[int, float]],
    windows: Sequence[WalkForwardWindow],
    start_balance: float,
) -> list[tuple[float, list[float]]]:
    """Per window: ``(return, per-trade returns)`` from one continuous stream of ``(ts, pnl)``.

    A trade belongs to the window its outcome RESOLVED in, so a position straddling a boundary
    counts once, on the far side. Each window's return is measured against the equity the account
    actually held when that window opened -- which in a continuous run is what earlier windows
    left behind, not the opening balance every time.
    """
    ordered = sorted(closed)
    out: list[tuple[float, list[float]]] = []
    for window in windows:
        start_ns = int(pd.Timestamp(window.test_start).value)
        end_ns = int(pd.Timestamp(window.test_end).value)
        opening = start_balance + sum(pnl for ts, pnl in ordered if ts < start_ns)
        inside = [pnl for ts, pnl in ordered if start_ns <= ts < end_ns]
        if opening <= 0:
            out.append((0.0, []))
            continue
        out.append((sum(inside) / opening, [pnl / opening for pnl in inside]))
    return out


def continuous_walk_forward(
    recipe: SweepRecipe,
    windows: Sequence[WalkForwardWindow],
    combos: Sequence[Mapping[str, Any]],
    optimize: Callable[[WalkForwardWindow], tuple[dict[str, Any], float]],
    *,
    collect_matrix: bool = False,
) -> list[WalkForwardResult]:
    """Stage 1's walk-forward, executed as continuous runs instead of one engine per window.

    Selection is unchanged: each window's parameters still come from its own training interval.
    What changes is execution -- the chosen schedule is run once across the whole span, and the
    resulting trades are attributed to the window they resolved in.

    ``collect_matrix`` additionally scores every grid candidate. A candidate holds one parameter
    set for the whole span, so that is one continuous run per candidate rather than one per
    candidate per window, and the pre-roll is paid once instead of once per window.
    """
    if not windows:
        return []
    span_start, span_end = min(w.test_start for w in windows), max(w.test_end for w in windows)
    chosen = [optimize(window) for window in windows]
    schedule = build_schedule(windows, [params for params, _ in chosen])
    per_window = window_returns(
        closed_pnls(recipe, schedule, span_start, span_end), windows, recipe.start_balance
    )

    by_combo: list[dict[str, float]] = [{} for _ in windows]
    if collect_matrix:
        for params in combos:
            candidate = constant_schedule(params, span_start, span_end)
            scored = window_returns(
                closed_pnls(recipe, candidate, span_start, span_end),
                windows,
                recipe.start_balance,
            )
            key = combo_key(params)
            for slot, (window_return, _) in zip(by_combo, scored, strict=True):
                slot[key] = window_return

    results: list[WalkForwardResult] = []
    for window, (params, is_return), (oos_return, trade_returns), combo_scores in zip(
        windows, chosen, per_window, by_combo, strict=True
    ):
        results.append(
            WalkForwardResult(
                window=window.label,
                best_params=params,
                is_return=is_return,
                oos_return=oos_return,
                oos_trades=len(trade_returns),
                oos_max_dd=max_drawdown(equity_curve(trade_returns, 1.0)),
                oos_returns=trade_returns,
                oos_by_combo=combo_scores,
            )
        )
    return results
