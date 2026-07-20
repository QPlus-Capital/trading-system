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
from research.engine.schedule_builder import build_schedule, pinned_params
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


def start_balance_of(recipe: Any) -> float:
    """The account balance a recipe's backtests start from.

    A :class:`SweepRecipe` carries it directly. A config MODULE -- the interface the runner's CLI
    documents, which re-exports only the uppercase names -- does not, and reading the attribute
    there would break the advertised ``python -m research.engine.walkforward_runner <config.py>``
    path. Both express the same number through the venue, so fall back to that.
    """
    direct = getattr(recipe, "start_balance", None)
    if direct is not None:
        return float(direct)
    balances = list(getattr(recipe.VENUE, "starting_balances", []) or [])
    if not balances:
        raise AttributeError(
            f"{type(recipe).__name__} exposes neither start_balance nor a venue starting "
            "balance; a continuous run cannot measure a return without one"
        )
    return float(str(balances[0]).split()[0].replace("_", ""))


def run_continuous_oos(
    recipe: SweepRecipe,
    segments: tuple[ParamSegment, ...],
    *,
    span_start: pd.Timestamp,
    span_end: pd.Timestamp,
    params: Mapping[str, Any] | None = None,
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
        {
            **dict(params or {}),
            "segments": segments,
            # The stop-time liquidation is the end of the backtest, not an exit anyone traded.
            # Booking it would put an artificial close on the final position -- exactly the
            # boundary truncation this whole change removes, moved to the last seam.
            "flatten_on_stop": False,
        },
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
    params: Mapping[str, Any] | None = None,
) -> list[tuple[int, float]]:
    """``(close timestamp ns, realized PnL)`` for every trade of one continuous run."""
    from research.portfolio.trades import timed_trades_from_report

    pos = run_continuous_oos(
        recipe, segments, span_start=span_start, span_end=span_end, params=params
    )
    rows = timed_trades_from_report(
        pos, str(recipe.INSTRUMENT.raw_symbol), stop_loss_lookup(segments), closed_from=span_start
    )
    return [(int(row["ts_closed"]), float(row["pnl_base"])) for row in rows]


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

    Windows are treated as covering the interval up to the NEXT window's start, not merely up to
    their own end. With the study's contiguous windows the two are identical; where a step larger
    than the test length leaves a gap, a position carried into that gap and closed there would
    otherwise belong to no window at all -- its PnL would still move the next window's opening
    equity while the trade itself vanished from every count.
    """
    ordered = sorted(closed)
    starts = [int(pd.Timestamp(w.test_start).value) for w in windows]
    out: list[tuple[float, list[float]]] = []
    for i, window in enumerate(windows):
        start_ns = starts[i]
        end_ns = (
            starts[i + 1] if i + 1 < len(starts) else int(pd.Timestamp(window.test_end).value)
        )
        opening = start_balance + sum(pnl for ts, pnl in ordered if ts < start_ns)
        if opening <= 0:
            # The account is gone. Reporting a flat window would let every later window average
            # in as harmless, which flatters exactly the strategy whose losses caused this.
            raise RuntimeError(
                f"account exhausted before window {window.label}: equity {opening:,.0f} "
                "-- post-ruin windows have no meaningful return and must not be averaged in"
            )
        inside = [pnl for ts, pnl in ordered if start_ns <= ts < end_ns]
        out.append((sum(inside) / opening, [pnl / opening for pnl in inside]))
    return out


def continuous_walk_forward(
    recipe: Any,
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
    # Sorted ONCE, here, so optimization, attribution and the result list all see the same order.
    # build_schedule sorts its own input; window_returns derives interval ends from sequence
    # order, so an unsorted caller would bound a window by an earlier start and hand the returns
    # to the wrong labels.
    windows = sorted(windows, key=lambda w: w.test_start)
    for earlier, later in zip(windows, windows[1:], strict=False):
        if later.test_start < earlier.test_end:
            # Two segments would claim the same instant, so the schedule cannot say which
            # parameters govern it and each window is silently shortened to the next one's start.
            raise ValueError(
                f"test windows overlap ({earlier.label} and {later.label}): a continuous run "
                "needs step_months >= test_months, or no segment owns the overlap"
            )
    span_start, span_end = min(w.test_start for w in windows), max(w.test_end for w in windows)
    balance = start_balance_of(recipe)
    chosen = [optimize(window) for window in windows]
    selected = [params for params, _ in chosen]
    # Refuses a selection that wants a different indicator setting per segment; returns what the
    # segments agree on, which is constant for the span and therefore configured directly.
    pinned = pinned_params(selected)
    schedule = build_schedule(windows, selected)
    per_window = window_returns(
        closed_pnls(recipe, schedule, span_start, span_end, pinned),
        windows,
        balance,
    )

    by_combo: list[dict[str, float]] = [{} for _ in windows]
    if collect_matrix:
        for params in combos:
            # The SAME window and gap boundaries as the chosen path. A single span-wide segment
            # would let a candidate trade through gaps no test window owns, so the matrix would
            # compare periods the chosen strategy never traded -- and PBO/DSR are computed from
            # exactly that comparison.
            candidate = build_schedule(windows, [params] * len(windows))
            scored = window_returns(
                closed_pnls(recipe, candidate, span_start, span_end, {**pinned, **params}),
                windows,
                balance,
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
