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

from collections.abc import Callable

import pandas as pd
from core.strategies.param_schedule import ParamSegment, segment_at

from research.engine.recipe import SweepRecipe
from research.engine.walkforward_runner import PREROLL


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
