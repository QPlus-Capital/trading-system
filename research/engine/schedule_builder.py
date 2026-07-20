"""Build an execution schedule from walk-forward windows and their selected parameters.

The selection half of #32. Each segment's parameters come from that segment's own training
interval and nothing else; the result is handed to the execution half as data, so a continuous
run cannot reach back into selection while it is running.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import pandas as pd
from core.strategies.param_schedule import ParamSegment

from research.engine.walkforward import WalkForwardWindow

#: Grid keys a continuous run may switch between segments. Everything else feeds the rolling
#: indicators, which cannot be re-parameterised mid-run without discarding their state -- and a
#: silently reset indicator would make the segment after every boundary trade on a cold engine.
SWITCHABLE = ("stop_loss_pct", "take_profit_pct")


class UnschedulableGrid(ValueError):
    """The parameter grid varies something a continuous run cannot switch mid-flight."""


def pinned_params(params_per_window: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Non-switchable parameters the CHOSEN sets agree on, or a refusal naming the disagreement.

    The constraint belongs on the selection, not on the grid. A grid may offer several indicator
    lengths and still be perfectly schedulable -- what cannot be executed as one continuous run is
    a selection that wants a DIFFERENT one in different segments, because a rolling indicator
    cannot be re-parameterised mid-flight without the next segment trading on a cold engine.
    Judging the grid instead would refuse searches that work and, worse, invite narrowing a
    research grid to satisfy an execution detail.

    The returned settings are constant for the whole span, so they are passed to the run directly
    rather than through the schedule (which carries only what actually switches).
    """
    if not params_per_window:
        return {}
    keys = {k for params in params_per_window for k in params} - set(SWITCHABLE)
    pinned: dict[str, Any] = {}
    for key in sorted(keys):
        values = {str(params.get(key)) for params in params_per_window}
        if len(values) > 1:
            raise UnschedulableGrid(
                f"the selection wants different '{key}' in different segments "
                f"({', '.join(sorted(values))}), which one continuous run cannot honour: it "
                "feeds a rolling indicator, and switching it mid-run would leave the next "
                "segment trading on an engine that was never warmed for it.\n"
                "  Pin that parameter for the span, or run the segments separately."
            )
        pinned[key] = params_per_window[0].get(key)
    return pinned


def build_schedule(
    windows: Sequence[WalkForwardWindow],
    params_per_window: Sequence[Mapping[str, Any]],
) -> tuple[ParamSegment, ...]:
    """One segment per test window, plus a no-entry segment for every gap between them.

    A gap arises whenever the step exceeds the test length: that interval belongs to no test
    window, so it may not open anything, while positions carried into it stay managed. The
    schedule ends with a closing no-entry segment so nothing opens after the final test window.
    """
    if len(windows) != len(params_per_window):
        raise ValueError(
            f"{len(windows)} windows but {len(params_per_window)} parameter sets -- each window "
            "must carry exactly the parameters its own training interval selected"
        )
    ordered = sorted(zip(windows, params_per_window, strict=True), key=lambda p: p[0].test_start)
    segments: list[ParamSegment] = []
    previous_end: pd.Timestamp | None = None
    for window, params in ordered:
        if previous_end is not None and window.test_start > previous_end:
            segments.append(_closed(previous_end))
        segments.append(
            ParamSegment(
                from_ns=int(pd.Timestamp(window.test_start).value),
                # Absent means the strategy's own default of 0.0, which is exactly what a
                # single-window run would trade -- a grid that does not search the stop simply
                # is not risk-managed, and the two paths must agree about that.
                stop_loss_pct=float(params.get("stop_loss_pct", 0.0)),
                take_profit_pct=float(params.get("take_profit_pct", 0.0)),
                entries_allowed=True,
            )
        )
        previous_end = window.test_end
    if previous_end is not None:
        segments.append(_closed(previous_end))
    return tuple(segments)


def _closed(at: pd.Timestamp) -> ParamSegment:
    """A no-entry segment; the stop/target are irrelevant because nothing may open here."""
    return ParamSegment(
        from_ns=int(pd.Timestamp(at).value),
        stop_loss_pct=0.0,
        take_profit_pct=0.0,
        entries_allowed=False,
    )


def oos_span(windows: Sequence[WalkForwardWindow]) -> tuple[pd.Timestamp, pd.Timestamp]:
    """``(first test_start, last test_end)`` -- the interval one continuous run has to cover."""
    if not windows:
        raise ValueError("no walk-forward windows: there is no out-of-sample span to run")
    return min(w.test_start for w in windows), max(w.test_end for w in windows)
