"""The timestamped out-of-sample trade stream that the portfolio stage consumes.

The portfolio stage needs each out-of-sample trade with its open/close time and entry/exit price,
so the account's daily equity can be reconstructed. Parameters are chosen the same way as in the
edge study (Calmar on each window's training interval), but the out-of-sample span is executed as
ONE continuous run and the timed trades are recorded from it.

``timed_trades_from_report`` is the pure extraction from a NautilusTrader positions report
(unit-tested); ``extract_market_trades`` drives selection and that run for one instrument (needs
backtests). Under the venue's HEDGING OMS each round trip is its own closed Position, so every
closed trade is a real one; only a position still open when the span ends is skipped.
"""

from collections.abc import Callable
from typing import Any

import pandas as pd
from core.broker import BrokerProfile, standard_broker

from research.engine.config import extract_closed_positions
from research.engine.continuous import (
    base_config_of,
    run_continuous_oos,
    scoring_params,
    stage1_account_returns,
    stage1_trade_returns,
    stop_loss_lookup,
    stop_loss_pct_of,
)
from research.engine.grid import expand_grid
from research.engine.recipe import SweepRecipe
from research.engine.schedule_builder import build_schedule, oos_span, pinned_params
from research.engine.walkforward import (
    PREROLL,
    WalkForwardWindow,
    calmar_score,
    split_windows,
    walk_forward_windows,
)
from research.engine.walkforward_runner import _data_span

# ``pnl_base`` is the realized PnL in the account currency at the extraction's BASE risk
# (risk_per_trade=1%), i.e. money -- not a percentage. In the walk-forward stream this function
# produces, positions are sized off the constant basis, so ``pnl_base`` is flat; in the
# full-history stream (:mod:`research.portfolio.tail`) it compounds with the growing equity. ``r``
# is the scale-invariant twin either way: each trade's PnL divided by the risk that trade actually
# took, so re-booking ``r * risk_amount`` sizes at any flat risk regardless of which stream it came
# from.
_COLUMNS = [
    "market",
    "ts_opened",
    "ts_closed",
    "pnl_base",
    "entry",
    "exit",
    "sl_pct",
    "is_long",
    "r",
]


def assign_r(
    rows: list[dict[str, Any]],
    start_balance: float,
    base_risk_frac: float,
    *,
    fixed_basis: bool = False,
) -> list[dict[str, Any]]:
    """Add each trade's R-multiple: PnL divided by the risk the trade actually took.

    The denominator has to match how the backtest sized the position, and the two backtests that
    feed this size differently:

    * The full-history run (``fixed_basis=False``, the default) sizes every position at
      ``base_risk_frac`` of the *current* compounding equity, so the risk is recovered by walking
      the equity forward in close order over the single continuous account. This path produces the
      invariant ``full_history_trades.csv``; its behaviour must not change.
    * The walk-forward run (``fixed_basis=True``) sizes every position off the constant
      ``sizing_equity`` basis (:func:`research.engine.continuous.scoring_params`), so the risk is
      the SAME ``base_risk_frac * start_balance`` for every trade -- no walk. The denominator must
      match how the position was sized: dividing flat-sized trades by a walked compounding equity
      reports every trade but the first at the wrong R.

    R is what makes the framework sizing-agnostic: independent of the backtest's own sizing, so any
    flat or dynamic risk policy can re-book it linearly.
    """
    if fixed_basis:
        risk = base_risk_frac * start_balance
        for row in rows:
            row["r"] = row["pnl_base"] / risk if risk > 0 else 0.0
        return rows
    equity = start_balance
    for row in sorted(rows, key=lambda r: r["ts_closed"]):
        risk = base_risk_frac * equity
        row["r"] = row["pnl_base"] / risk if risk > 0 else 0.0
        equity += row["pnl_base"]
    return rows


def timed_trades_from_report(
    pos: pd.DataFrame,
    market: str,
    sl_pct: float | Callable[[int], float],
    *,
    closed_from: pd.Timestamp | None = None,
) -> list[dict[str, Any]]:
    """Extract closed trades ``(ts_opened, ts_closed, pnl, entry, exit, sl_pct)`` from a report.

    ``sl_pct`` is the stop-loss % the trade was opened at -- recorded per trade so the overnight
    swap cost can be priced exactly (it depends on the stop distance). A single window trades one
    stop, so a float is enough there; a continuous run (#32) switches stops at segment boundaries
    while positions carry across them, so it passes a callable resolving the stop from the trade's
    own open timestamp.

    ``closed_from`` keeps only trades that RESOLVED at or after that moment -- a safety net for the
    read-only pre-roll, which warms the indicators without placing orders.

    A position still open when the run ends is skipped: it has no outcome to record. Under the
    continuous run that can only be the final open position of the whole span, not one position
    per seam.
    """
    out: list[dict[str, Any]] = []
    for _, row in pos.iterrows():
        if pd.isna(row["ts_closed"]):  # still open at the run end -> the NEXT window resolves it
            continue
        if closed_from is not None and pd.to_datetime(row["ts_closed"], utc=True) < closed_from:
            continue  # resolved inside the pre-roll -> belongs to the previous window
        pnl = float(str(row["realized_pnl"]).split()[0].replace("_", ""))
        opened_ns = int(pd.Timestamp(row["ts_opened"]).value)
        stop = sl_pct(opened_ns) if callable(sl_pct) else float(sl_pct)
        out.append(
            {
                "market": market,
                "ts_opened": opened_ns,
                "ts_closed": int(pd.Timestamp(row["ts_closed"]).value),
                "pnl_base": pnl,
                "entry": float(row["avg_px_open"]),
                "exit": float(row["avg_px_close"]),
                "sl_pct": float(stop),
                # Direction straight from the report (#10). NOTE: our "entry" is the entry PRICE
                # while the report's "entry" is the entry SIDE -- read "side" and read it here,
                # before the name is reused. Swap is direction-dependent, and inferring direction
                # from the outcome misclassifies any trade whose costs flip its sign.
                "is_long": str(row["side"]).upper() == "LONG",
            }
        )
    return out


def extract_market_trades(
    recipe: SweepRecipe,
    *,
    train_months: int,
    test_months: int,
    step_months: int,
    param_grid: dict[str, list[Any]] | None = None,
    holdout_months: int = 0,
    phase: str = "select",
    embargo_days: int = 0,
    fixed_params: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Walk-forward one instrument and return every OOS trade with timestamps + prices.

    Assumes the catalog is already seeded. Selection optimizes each window on its own training
    interval by the drawdown-adjusted Calmar score; execution then replays those choices as a
    schedule inside ONE continuous run across the whole out-of-sample span (#32), so a position
    open at a segment boundary carries on the parameters that opened it instead of being dropped
    or reopened.

    If ``fixed_params`` is given, the per-window optimization is SKIPPED and those parameters
    are used in every window instead -- the frozen-config walk-forward. Run over the same
    windows as the optimized version it isolates one effect: the cost of trading fixed SL/TP
    (as we do live) versus re-optimising each window (what the holdout otherwise validates).

    The caller MUST pass non-overlapping windows (``step_months == test_months``): overlapping
    test windows would have two segments claiming the same instant, so the schedule could not say
    which parameters govern it (F1). ``holdout_months`` / ``phase`` reserve/select the
    final untouched slice (F2), mirroring
    :func:`research.engine.walkforward_runner.run_walkforward`.
    """

    if step_months < test_months:
        # N5: overlapping test windows would record the same trade in two windows and
        # double-count it in the portfolio stream. Require non-overlapping windows.
        raise ValueError(
            f"step_months ({step_months}) < test_months ({test_months}) -> overlapping test "
            "windows would double-count trades; pass step_months == test_months"
        )
    grid = param_grid if param_grid is not None else recipe.PARAM_GRID
    combos = expand_grid(grid)
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
    market = str(recipe.INSTRUMENT.raw_symbol)

    if not windows:
        return pd.DataFrame([], columns=_COLUMNS)

    # SELECTION: each segment's parameters come from its own training interval and nothing else.
    per_window = [
        fixed_params if fixed_params is not None else _optimize(recipe, combos, window)
        for window in windows
    ]
    # Refuses a selection wanting different indicator settings per segment, and returns what they
    # agree on -- covering both the grid's pinned keys and any frozen fixed_params.
    pinned = pinned_params(per_window)
    segments = build_schedule(windows, per_window, defaults=base_config_of(recipe))

    # EXECUTION: one run over the whole span (#32). Positions carry across segment boundaries on
    # the parameters that opened them, so no trade is dropped or reopened at a seam.
    span_start, span_end = oos_span(windows)
    # Pinned grid keys must reach the run too, or execution trades the strategy defaults while
    # selection scored the pinned ones.
    pos = run_continuous_oos(
        recipe, segments, span_start=span_start, span_end=span_end, params=pinned
    )
    rows = timed_trades_from_report(pos, market, stop_loss_lookup(segments), closed_from=span_start)
    # Positions were sized off the constant basis, so every trade's risk is the same
    # base_risk_frac * start_balance -- R divides by that, not by a walked compounding equity that
    # the flat-sized trades never traded against.
    return pd.DataFrame(
        assign_r(rows, recipe.start_balance, recipe.base_risk_frac, fixed_basis=True),
        columns=_COLUMNS,
    )


def _optimize(
    recipe: SweepRecipe, combos: list[dict[str, Any]], window: WalkForwardWindow
) -> dict[str, Any]:
    """The parameters this window's TRAINING interval selects, by drawdown-adjusted score.

    Kept a separate step from execution on purpose (#32): the schedule is complete before the
    continuous run begins, so the running strategy has no path to a selection decision and cannot
    consult data from beyond the segment it is trading.
    """
    best, best_score = combos[0], float("-inf")
    for params in combos:
        # Warm this pass the same way as the walk-forward runner's: a cold train window here
        # would pick different params than Stage 1 did, so the portfolio numbers would no longer
        # describe the methodology that was selected.
        positions, _start_equity = extract_closed_positions(
            recipe.build_run_config(
                # The same constant basis the OOS run uses, so selection and execution model one
                # strategy. A compounding training run here would rank candidates by a scale the
                # graded run does not share.
                {
                    **scoring_params(recipe, params),
                    # The engine boundary is not a strategy exit. Leave the final position open so
                    # the closed-position extractor excludes it from the training score.
                    "flatten_on_stop": False,
                },
                start=(window.train_start - PREROLL).isoformat(),
                end=window.train_end.isoformat(),
                trade_from=window.train_start.isoformat(),
            ),
            closed_from=window.train_start,
        )
        frame = stage1_trade_returns(
            positions,
            recipe,
            stop_loss_pct_of(recipe, params),
            closed_from=window.train_start,
        )
        score = calmar_score(stage1_account_returns(frame, recipe), 1.0)
        if score > best_score:
            best_score, best = score, params
    return best


# --- Portfolio-stage extractor factory (injected into stage 3) ---


ExtractFn = Callable[[str, dict[str, Any], int], pd.DataFrame]


def make_extract_fn(
    instrument_specs: dict[str, tuple[Any, str, float]],
    *,
    test_months: int,
    param_grid: dict[str, list[Any]],
    holdout_months: int = 0,
    phase: str = "holdout",
    embargo_days: int = 0,
    start_balance: float = 200_000.0,
    risk_per_trade_pct: float = 1.0,
    fixed_stops: dict[str, dict[str, Any]] | None = None,
    broker: BrokerProfile | None = None,
) -> ExtractFn:
    """Default extractor for the portfolio stream.

    Enforces **non-overlapping** windows (``step = test``) so no trade is double-counted
    (F1), and extracts the reserved-**holdout** slice by default so the portfolio is scored
    once on data no stage selected on (F2).

    ``start_balance`` / ``risk_per_trade_pct`` are the account the extraction's backtests size
    against; pass the real account so every stage measures the same thing. The per-trade R that
    comes out is scale-invariant either way, but the position quantities are not, and a small
    enough account silently falls back to the fixed trade size.

    ``fixed_stops`` maps a market to the SL/TP it should trade in EVERY window instead of
    re-optimising the stop per window. This validates the config we actually deploy (fixed stops),
    whose gentle tail permits a tradeable size -- as opposed to the re-optimised path, which chases
    the tightest stop on the grid and is tail-capped to an untradeable one.
    """

    active_broker = broker if broker is not None else standard_broker()

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
            broker=active_broker,
            start_balance=start_balance,
            risk_per_trade_pct=risk_per_trade_pct,
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
            fixed_params=(fixed_stops or {}).get(market),
        )

    return extract
