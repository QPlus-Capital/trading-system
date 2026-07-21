"""Behavioural tests for the reusable test-design helpers and generators."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from core.strategies.param_schedule import ParamSegment
from hypothesis import given
from research.engine.walkforward import WalkForwardWindow

from tests.support.assertions import (
    assert_aggregate_equals_parts,
    assert_config_propagates,
    assert_limit_monotonicity,
    assert_numeric_cases,
    assert_reconciles,
    assert_selection_execution_parity,
    assert_temporal_ownership,
)
from tests.support.strategies import (
    BoundaryTimestamps,
    SymbolLotMetadata,
    TradeSample,
    boundary_timestamps,
    finite_decimals,
    invalid_windows,
    schedule_segments,
    symbol_lot_metadata,
    trade_streams,
    valid_windows,
    zero_sparse_references,
)


def test_reconciliation_helper_accepts_exactly_once_and_rejects_drop_or_duplicate() -> None:
    expected = [{"id": 1}, {"id": 2}]
    assert_reconciles(expected, {"a": [expected[0]], "b": [expected[1]]}, key=lambda row: row["id"])
    with pytest.raises(AssertionError, match="exactly once"):
        assert_reconciles(expected, {"a": [expected[0], expected[0]]}, key=lambda row: row["id"])


def test_aggregate_helper_rejects_a_total_that_does_not_equal_its_parts() -> None:
    assert_aggregate_equals_parts([Decimal("1.2"), Decimal("2.3")], Decimal("3.5"))
    with pytest.raises(AssertionError, match="aggregate"):
        assert_aggregate_equals_parts([Decimal("1.2"), Decimal("2.3")], Decimal("3.6"))


def test_selection_execution_helper_rejects_a_lost_constant_non_default() -> None:
    selected = {"rsi_length": 21, "risk": Decimal("0.0018")}
    assert_selection_execution_parity(selected, dict(selected), selected)
    with pytest.raises(AssertionError, match="rsi_length"):
        assert_selection_execution_parity(selected, {"rsi_length": 14}, selected)


def test_config_helper_rejects_an_ignored_non_default_case() -> None:
    cases = {"default": 14, "constant-non-default": 21, "varying": 9}
    assert_config_propagates(cases, lambda value: value)
    with pytest.raises(AssertionError, match="constant-non-default"):
        assert_config_propagates(cases, lambda _value: 14)


def test_temporal_helper_rejects_a_wrong_boundary_owner() -> None:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    points = {"before": start - timedelta(seconds=1), "at-start": start}
    expected = {"before": None, "at-start": "window-1"}
    assert_temporal_ownership(points, expected, lambda ts: None if ts < start else "window-1")
    with pytest.raises(AssertionError, match="at-start"):
        assert_temporal_ownership(points, expected, lambda _ts: None)


def test_numeric_helper_rejects_a_threshold_equality_bug() -> None:
    cases = {"below": Decimal("0.99"), "at": Decimal("1.00"), "above": Decimal("1.01")}
    expected = {"below": False, "at": True, "above": True}
    assert_numeric_cases(cases, expected, lambda value: value >= Decimal(1))
    with pytest.raises(AssertionError, match="at"):
        assert_numeric_cases(cases, expected, lambda value: value > Decimal(1))


def test_limit_helper_rejects_a_stronger_limit_that_admits_a_blocked_case() -> None:
    samples = (1, 2, 3)
    assert_limit_monotonicity(samples, weaker=lambda x: x <= 3, stronger=lambda x: x <= 2)
    with pytest.raises(AssertionError, match="stronger"):
        assert_limit_monotonicity(samples, weaker=lambda x: x <= 2, stronger=lambda x: x <= 3)


@given(finite_decimals(min_value=Decimal("-10"), max_value=Decimal("10"), places=4))
def test_finite_decimal_strategy_never_emits_non_finite_or_excess_precision(value: Decimal) -> None:
    assert value.is_finite()
    exponent = value.as_tuple().exponent
    assert isinstance(exponent, int)
    assert exponent >= -4


@given(valid_windows())
def test_valid_window_strategy_emits_ordered_non_overlapping_windows(
    windows: tuple[WalkForwardWindow, ...],
) -> None:
    assert windows
    starts = [window.test_start for window in windows]
    ends = [window.test_end for window in windows]
    assert starts == sorted(starts)
    assert all(start < end for start, end in zip(starts, ends, strict=True))
    assert all(left <= right for left, right in zip(ends[:-1], starts[1:], strict=True))


@given(invalid_windows())
def test_invalid_window_strategy_emits_an_overlap(
    windows: tuple[WalkForwardWindow, WalkForwardWindow],
) -> None:
    first, second = windows
    assert second.test_start < first.test_end


@given(schedule_segments())
def test_schedule_segment_strategy_emits_strictly_ordered_starts(
    segments: tuple[ParamSegment, ...],
) -> None:
    starts = [segment.from_ns for segment in segments]
    assert starts == sorted(set(starts))


@given(trade_streams())
def test_trade_stream_strategy_emits_valid_lifecycles(trades: tuple[TradeSample, ...]) -> None:
    assert trades
    assert all(trade.open_day <= trade.close_day for trade in trades)


@given(zero_sparse_references())
def test_zero_sparse_reference_strategy_keeps_the_reference_sparse(pair: tuple[int, int]) -> None:
    reference, candidate = pair
    assert 0 <= reference <= 2
    assert candidate >= 0


@given(symbol_lot_metadata())
def test_symbol_metadata_strategy_emits_tradeable_step_aligned_limits(
    metadata: SymbolLotMetadata,
) -> None:
    step = metadata.lot_step
    assert metadata.min_lot % step == 0
    assert metadata.max_lot % step == 0


@given(boundary_timestamps())
def test_boundary_timestamp_strategy_orders_every_named_boundary(
    points: BoundaryTimestamps,
) -> None:
    assert points.before < points.start < points.within < points.end < points.after
