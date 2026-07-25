"""One continuous out-of-sample run per instrument, governed by a parameter schedule (#32).

The execution half. Independent per-window backtests cannot carry a position across a segment
boundary under the parameters that opened it -- each window is its own engine, so a straddling
position is either dropped or reopened. Running the whole out-of-sample span once, with the
schedule switching parameters for NEW entries only, removes that approximation: a position simply
stays open, on its original stop and target, until it really closes.

Two consequences follow from there being one account instead of many:

* each trade appears exactly once, so the stream needs no de-duplication at the seams;
* sizing is pinned to a constant basis rather than left to compound across the span.

The pin matters because the strategy's sizing is not scale-invariant: lot quantisation, minimum
and maximum quantities and margin bind differently at 50k than at 500m. Left to compound, a late
window trades a different account size than an early one, so the per-window returns are not
comparable and their mean is not an equal-weighted measure of edge; on index CFDs the balance also
passes the engine's MONEY_MAX ceiling and the run dies. So every scoring backtest -- the training
runs that select parameters and the out-of-sample run that grades them -- sizes off the same
``sizing_equity`` via :func:`scoring_params`, and :func:`window_returns` divides by that same
constant. Both halves are required together: a flat position size over a growing denominator would
shrink every later window's return by whatever the account had earned. Stage 1 measures edge on
equal footing; compounding belongs to the portfolio stage and to live trading.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any

import pandas as pd
from core.broker import BrokerProfile, swap_r_per_trade
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


def scoring_params(recipe: Any, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """``params`` plus the fixed sizing basis every scoring backtest must share.

    Selection and evaluation have to model ONE strategy, so the training runs that pick the
    parameters and the out-of-sample run that scores them must size the same way. Both go through
    a recipe config, so both pass their parameters through here; a caller that sized without it
    would rank candidates under compounding and then grade them flat -- the exact split this run
    exists to remove. The basis is carried as ``Decimal`` because it is money.
    """
    return {**dict(params or {}), "sizing_equity": Decimal(str(start_balance_of(recipe)))}


def base_config_of(recipe: Any) -> dict[str, Any]:
    """The configuration a recipe merges its parameters onto.

    Same shape of problem as :func:`start_balance_of`, and the same axis: a config MODULE
    re-exports the uppercase names and does not carry the recipe's own attributes. Reaching only
    for the public property would hand back an empty mapping there, so a stop or target fixed in
    ``config_overrides`` -- present in every training run -- would be missing when the schedule
    is built, and the span would be refused or run without it.
    """
    for attribute in ("base_config", "_base_config"):
        found = getattr(recipe, attribute, None)
        if isinstance(found, dict):
            return dict(found)
    wrapped = getattr(recipe, "_R", None)  # a config module built from a SweepRecipe
    if wrapped is not None:
        return base_config_of(wrapped)
    return {}


def base_risk_fraction_of(recipe: Any) -> float:
    """The dimensionless risk fraction used by every constant-basis scoring trade."""
    direct = getattr(recipe, "base_risk_frac", None)
    if direct is not None:
        value = float(direct)
    else:
        wrapped = getattr(recipe, "_R", None)
        if wrapped is not None:
            return base_risk_fraction_of(wrapped)
        configured = base_config_of(recipe).get("risk_per_trade_pct")
        if configured is None:
            raise AttributeError(
                f"{type(recipe).__name__} exposes neither base_risk_frac nor "
                "risk_per_trade_pct; Stage 1 cannot convert R into an account return"
            )
        value = float(configured) / 100.0
    if value <= 0:
        raise ValueError(f"base_risk_frac must be positive, got {value}")
    return value


def broker_of(recipe: Any) -> BrokerProfile:
    """The frozen broker profile carried by a scoring recipe.

    Loading a snapshot inside this helper would let different workers or candidate runs observe
    different files during one study. The orchestration boundary loads ``standard_broker()`` once
    and every recipe carries that same in-memory profile.
    """
    direct = getattr(recipe, "broker", None)
    if isinstance(direct, BrokerProfile):
        return direct
    wrapped = getattr(recipe, "_R", None)
    if wrapped is not None:
        return broker_of(wrapped)
    raise AttributeError(
        f"{type(recipe).__name__} carries no BrokerProfile; Stage 1 refuses a swap-unpriced stream"
    )


def stop_loss_pct_of(recipe: Any, params: Mapping[str, Any]) -> float:
    """Resolve the stop distance actually composed into a training run."""
    value = {**base_config_of(recipe), **dict(params)}.get("stop_loss_pct")
    if value is None:
        raise AttributeError("Stage-1 swap pricing requires the trade's stop_loss_pct")
    stop = float(value)
    if stop <= 0:
        raise ValueError(f"stop_loss_pct must be positive, got {stop}")
    return stop


_STAGE1_TRADE_COLUMNS = (
    "market",
    "ts_opened",
    "ts_closed",
    "pnl_base",
    "entry",
    "exit",
    "sl_pct",
    "is_long",
    "r",
    "swap_r",
    "net_r",
)


def stage1_trade_returns(
    positions: pd.DataFrame,
    recipe: Any,
    stop_loss_pct: float | Callable[[int], float],
    *,
    closed_from: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Closed Stage-1 trades with gross ``r``, realized ``swap_r``, and exact ``net_r``.

    The report is reduced through the same timestamp/direction/stop extraction and
    :func:`core.broker.swap_r_per_trade` convention Stage 3 uses. Swap remains separate from gross
    price R and is attached once to the closed-position row; there is no holding-period mark.
    """
    from research.portfolio.trades import assign_r, timed_trades_from_report

    if positions.empty or "ts_closed" not in positions.columns:
        return pd.DataFrame(columns=_STAGE1_TRADE_COLUMNS)
    market = str(recipe.INSTRUMENT.raw_symbol)
    rows = timed_trades_from_report(
        positions,
        market,
        stop_loss_pct,
        closed_from=closed_from,
    )
    assigned = assign_r(
        rows,
        start_balance_of(recipe),
        base_risk_fraction_of(recipe),
        fixed_basis=True,
    )
    frame = pd.DataFrame(assigned)
    if frame.empty:
        return pd.DataFrame(columns=_STAGE1_TRADE_COLUMNS)
    frame["swap_r"] = 0.0
    if (spec := broker_of(recipe).swap_spec(market)) is not None:
        frame["swap_r"] = swap_r_per_trade(frame, spec)
    frame["net_r"] = frame["r"].to_numpy(dtype=float) + frame["swap_r"].to_numpy(dtype=float)
    return frame.loc[:, list(_STAGE1_TRADE_COLUMNS)]


def stage1_account_returns(trades: pd.DataFrame, recipe: Any) -> list[float]:
    """Dimensionless constant-basis account returns derived only from ``net_r``."""
    if trades.empty:
        return []
    values = trades["net_r"].to_numpy(dtype=float) * base_risk_fraction_of(recipe)
    return [float(value) for value in values]


def stage1_close_events(trades: pd.DataFrame, recipe: Any) -> list[tuple[int, float]]:
    """``(close timestamp, net account return)`` events, one per realized trade."""
    returns = stage1_account_returns(trades, recipe)
    return [
        (int(timestamp), value)
        for timestamp, value in zip(trades["ts_closed"], returns, strict=True)
    ]


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
            **scoring_params(recipe, params),
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


def closed_stage1_returns(
    recipe: SweepRecipe,
    segments: tuple[ParamSegment, ...],
    span_start: pd.Timestamp,
    span_end: pd.Timestamp,
    params: Mapping[str, Any] | None = None,
) -> list[tuple[int, float]]:
    """``(close timestamp ns, net account return)`` for one continuous scoring run."""
    pos = run_continuous_oos(
        recipe, segments, span_start=span_start, span_end=span_end, params=params
    )
    frame = stage1_trade_returns(
        pos,
        recipe,
        stop_loss_lookup(segments),
        closed_from=span_start,
    )
    return stage1_close_events(frame, recipe)


def window_returns(
    closed: Sequence[tuple[int, float]],
    windows: Sequence[WalkForwardWindow],
    basis: float,
) -> list[tuple[float, list[float]]]:
    """Per window: ``(return, per-trade returns)`` from one continuous stream of ``(ts, pnl)``.

    A trade belongs to the window its outcome RESOLVED in, so a position straddling a boundary
    counts once, on the far side. Every window is measured against the SAME ``basis`` -- the
    constant equity the run sized every trade from (``sizing_equity``), not the balance the
    account holds by then.

    The constant denominator is the other half of constant sizing, not a simplification. A flat
    position size divided by a growing balance would report a smaller return for a later window
    purely because earlier windows earned, the opposite of the equal footing this is for. Sizing
    and denominator move together or neither is meaningful.

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
        last = i + 1 == len(starts)
        # Half-open everywhere except at the very end. Between windows the next one's start owns
        # the instant, so it must not be counted twice; at the final boundary there is no next
        # window, and an exclusive bound would drop a position closing exactly on test_end from
        # every result while its PnL still sat in the account.
        end_ns = int(pd.Timestamp(window.test_end).value) if last else starts[i + 1]
        equity = basis + sum(pnl for ts, pnl in ordered if ts < start_ns)
        if equity <= 0:
            # The account is gone. Reporting a flat window would let every later window average
            # in as harmless, which flatters exactly the strategy whose losses caused this. The
            # denominator below stays the constant basis; this only asks whether there was still
            # an account to trade, and a run that lost more than it started with had none.
            raise RuntimeError(
                f"account exhausted before window {window.label}: equity {equity:,.0f} "
                "-- post-ruin windows have no meaningful return and must not be averaged in"
            )
        inside = [
            pnl
            for ts, pnl in ordered
            if start_ns <= ts and (ts <= end_ns if last else ts < end_ns)
        ]
        out.append((sum(inside) / basis, [pnl / basis for pnl in inside]))
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
    chosen = [optimize(window) for window in windows]
    selected = [params for params, _ in chosen]
    # Refuses a selection that wants a different indicator setting per segment; returns what the
    # segments agree on, which is constant for the span and therefore configured directly.
    pinned = pinned_params(selected)
    base = base_config_of(recipe)
    schedule = build_schedule(windows, selected, defaults=base)
    per_window = window_returns(
        closed_stage1_returns(recipe, schedule, span_start, span_end, pinned),
        windows,
        1.0,
    )

    by_combo: list[dict[str, float]] = [{} for _ in windows]
    if collect_matrix:
        for params in combos:
            # The SAME window and gap boundaries as the chosen path. A single span-wide segment
            # would let a candidate trade through gaps no test window owns, so the matrix would
            # compare periods the chosen strategy never traded -- and PBO/DSR are computed from
            # exactly that comparison.
            candidate = build_schedule(windows, [params] * len(windows), defaults=base)
            scored = window_returns(
                closed_stage1_returns(
                    recipe,
                    candidate,
                    span_start,
                    span_end,
                    {**pinned, **params},
                ),
                windows,
                1.0,
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
