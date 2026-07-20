"""#32: the contract between parameter selection and continuous execution.

A stitched walk-forward cannot carry a position across a segment boundary under the parameters
that opened it, because each window is its own engine run. One continuous run can, provided the
parameters are handed to it as a schedule keyed by time -- which is what these tests pin.
"""

from __future__ import annotations

import pandas as pd
import pytest
from core.strategies.param_schedule import ParamSegment, entry_params_at, segment_at
from research.engine.schedule_builder import (
    UnschedulableGrid,
    build_schedule,
    check_switchable,
    oos_span,
)
from research.engine.walkforward import WalkForwardWindow, walk_forward_windows


def _window(test_start: str, test_end: str) -> WalkForwardWindow:
    ts, te = pd.Timestamp(test_start), pd.Timestamp(test_end)
    return WalkForwardWindow(ts - pd.DateOffset(months=24), ts, ts, te)


def _ns(when: str) -> int:
    return int(pd.Timestamp(when).value)


# ------------------------------------------------------------------ looking a segment up
def test_a_position_keeps_the_parameters_of_the_segment_it_opened_in() -> None:
    """The whole point: a trade opened before a boundary is governed by the OLD segment."""
    segments = (
        ParamSegment(_ns("2020-01-01"), 0.5, 2.0),
        ParamSegment(_ns("2020-07-01"), 1.5, 4.0),
    )
    assert entry_params_at(segments, _ns("2020-06-30")) == (0.5, 2.0)
    assert entry_params_at(segments, _ns("2020-07-01")) == (1.5, 4.0)  # boundary is inclusive


def test_before_the_first_segment_there_are_no_parameters_at_all() -> None:
    """The pre-roll warms indicators and must not be given a default set to trade on."""
    segments = (ParamSegment(_ns("2020-01-01"), 0.5, 2.0),)
    assert segment_at(segments, _ns("2019-12-31")) is None
    assert entry_params_at(segments, _ns("2019-12-31")) is None


def test_an_empty_schedule_never_authorises_anything() -> None:
    assert segment_at((), _ns("2020-01-01")) is None


# ------------------------------------------------------------------ building the schedule
def test_contiguous_windows_produce_one_segment_each() -> None:
    windows = [_window("2020-01-01", "2020-07-01"), _window("2020-07-01", "2021-01-01")]
    params = [{"stop_loss_pct": 0.5, "take_profit_pct": 2.0},
              {"stop_loss_pct": 1.5, "take_profit_pct": 4.0}]
    segments = build_schedule(windows, params)

    assert [s.entries_allowed for s in segments] == [True, True, False]
    assert segments[-1].from_ns == _ns("2021-01-01")  # nothing opens after the last test window
    assert entry_params_at(segments, _ns("2020-08-01")) == (1.5, 4.0)


def test_a_gap_between_test_windows_accepts_no_entries() -> None:
    """A step longer than the test length leaves an interval no window owns."""
    windows = [_window("2020-01-01", "2020-07-01"), _window("2020-10-01", "2021-04-01")]
    params = [{"stop_loss_pct": 0.5, "take_profit_pct": 2.0},
              {"stop_loss_pct": 0.5, "take_profit_pct": 2.0}]
    segments = build_schedule(windows, params)

    gap = segment_at(segments, _ns("2020-08-15"))
    assert gap is not None and not gap.entries_allowed
    resumed = segment_at(segments, _ns("2020-11-01"))
    assert resumed is not None and resumed.entries_allowed


def test_the_schedule_does_not_depend_on_the_order_windows_arrive_in() -> None:
    """Acceptance: results invariant to whether windows are supplied together or incrementally."""
    windows = [_window("2020-07-01", "2021-01-01"), _window("2020-01-01", "2020-07-01")]
    params = [{"stop_loss_pct": 1.5, "take_profit_pct": 4.0},
              {"stop_loss_pct": 0.5, "take_profit_pct": 2.0}]
    shuffled = build_schedule(windows, params)
    ordered = build_schedule(list(reversed(windows)), list(reversed(params)))
    assert shuffled == ordered


def test_windows_and_parameters_must_correspond() -> None:
    with pytest.raises(ValueError, match="each window must carry"):
        build_schedule([_window("2020-01-01", "2020-07-01")], [])


def test_the_span_covers_every_test_window() -> None:
    windows = [_window("2020-07-01", "2021-01-01"), _window("2020-01-01", "2020-07-01")]
    assert oos_span(windows) == (pd.Timestamp("2020-01-01"), pd.Timestamp("2021-01-01"))


def test_an_empty_window_list_has_no_span() -> None:
    with pytest.raises(ValueError, match="no out-of-sample span"):
        oos_span([])


# ------------------------------------------------------------------ what may vary per segment
def test_a_grid_of_risk_parameters_is_schedulable() -> None:
    check_switchable({"stop_loss_pct": [0.2, 0.5], "take_profit_pct": [1.0, 2.0]})


def test_a_grid_that_varies_an_indicator_length_is_refused() -> None:
    """Indicators are rolling: a mid-run change would trade the next segment on a cold engine.

    The real grid varies only stop and target, so this never fires today -- it exists so that
    adding an indicator length later stops the run instead of silently producing that.
    """
    with pytest.raises(UnschedulableGrid, match="rsi_length"):
        check_switchable({"stop_loss_pct": [0.2, 0.5], "rsi_length": [14, 21]})


def test_a_constant_indicator_length_is_fine() -> None:
    """Pinning a value is not varying it, so it cannot desynchronise anything."""
    check_switchable({"stop_loss_pct": [0.2, 0.5], "rsi_length": [14]})


# ------------------------------------------------------------------ against the real windows
def test_the_real_window_scheme_produces_a_contiguous_schedule() -> None:
    """With step == test the study's own windows leave no gap, so entries never pause."""
    windows = walk_forward_windows(
        "2010-01-01", "2020-01-01", train_months=24, test_months=6, step_months=6, embargo_days=7
    )
    params = [{"stop_loss_pct": 0.5, "take_profit_pct": 2.0}] * len(windows)
    segments = build_schedule(windows, params)

    assert len(segments) == len(windows) + 1  # one per window, plus the closing stop
    assert all(s.entries_allowed for s in segments[:-1])
    assert not segments[-1].entries_allowed


# --------------------------------------------------------- Codex round 1 on PR #42
def test_pinned_grid_keys_are_carried_into_the_continuous_run() -> None:
    """A grid key with one value is a SETTING; training sees it, so execution must too.

    Without this the continuous run is configured from the schedule alone -- which carries only
    stop and target -- and every other pinned key silently falls back to the strategy default.
    """
    from research.engine.continuous import constant_params

    pinned = constant_params(
        {"stop_loss_pct": [0.2, 0.5], "take_profit_pct": [1.0], "rsi_length": [21]}
    )
    assert pinned == {"rsi_length": 21}, "switchable keys come from the schedule, not from here"


def test_a_searched_key_is_not_mistaken_for_a_pinned_one() -> None:
    from research.engine.continuous import constant_params

    assert constant_params({"rsi_length": [14, 21]}) == {}


def test_the_default_grid_is_schedulable() -> None:
    """The shipped default must not raise before every ad-hoc walk-forward."""
    from research.engine.recipe import DEFAULT_PARAM_GRID

    check_switchable(DEFAULT_PARAM_GRID)
