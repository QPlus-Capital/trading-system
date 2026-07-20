"""A time-keyed parameter schedule: which parameters govern NEW entries, and when.

This is the contract between parameter *selection* and *execution*. Selection optimizes each
walk-forward segment on its own training interval and emits a schedule; execution replays that
schedule inside one continuous engine run, switching parameters only for new entries. Because the
schedule is complete before the run starts, the executing strategy has no path to a selection
decision -- it cannot consult data it should not have seen.

Positions are never reopened at a boundary. A position keeps the parameters that opened it,
including its stop and target, until it really closes; the segment it CLOSES in owns its result.
"""

from __future__ import annotations

import msgspec


class ParamSegment(msgspec.Struct, frozen=True):
    """Parameters governing new entries from ``from_ns`` until the next segment starts.

    ``entries_allowed`` is False for an interval that belongs to no test window -- an embargo, or
    a gap left by a step larger than the test length. Such an interval still MANAGES open
    positions: suppressing entries is a statement about information, while abandoning a position
    mid-flight would be a trade nobody made.
    """

    from_ns: int
    stop_loss_pct: float
    take_profit_pct: float
    entries_allowed: bool = True


def segment_at(segments: tuple[ParamSegment, ...], ts_ns: int) -> ParamSegment | None:
    """The segment governing ``ts_ns``, or ``None`` before the first one begins.

    ``None`` means "outside the scheduled span" -- the read-only pre-roll that warms indicators.
    Callers must treat it as *no entries*, never as *default parameters*.
    """
    found: ParamSegment | None = None
    for seg in segments:
        if seg.from_ns <= ts_ns:
            found = seg
        else:
            break
    return found


def entry_params_at(
    segments: tuple[ParamSegment, ...], ts_ns: int
) -> tuple[float, float] | None:
    """``(stop_loss_pct, take_profit_pct)`` for a position OPENED at ``ts_ns``.

    Looked up by the position's own open time, which is what keeps a position that straddles a
    boundary on the stop and target it was opened with rather than re-anchoring it to whatever
    the next segment chose.
    """
    seg = segment_at(segments, ts_ns)
    return None if seg is None else (seg.stop_loss_pct, seg.take_profit_pct)
