"""Suppression-safe statistical decisions for immutable forward-test cohorts.

The protocol reads P-12 daily net portfolio R and resamples only through P-04. Efficacy remains
suppressed until both fixed endpoint conditions hold. An optional, separately named futility stop
is available only at its stricter interim boundary; operational hard safety stops remain outside
this statistical decision and never alter it.
"""

from __future__ import annotations

import calendar
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_CEILING, Decimal
from enum import StrEnum, auto
from uuid import UUID

from research.forward_test_registry import (
    Cohort,
    CohortStatus,
    ForwardTestRegistry,
    ObservationSeries,
    ObservationSource,
)
from research.portfolio import resample as p04_resample

DEFAULT_REPLICATIONS = p04_resample.DEFAULT_REPLICATIONS
DEFAULT_SEED = p04_resample.DEFAULT_SEED
SENSITIVITY_BLOCK_LENGTHS = p04_resample.SENSITIVITY_BLOCK_LENGTHS
select_block_length = p04_resample.select_block_length
stationary_bootstrap = p04_resample.stationary_bootstrap
EFFICACY_MONTHS = 30
EFFICACY_TRADES = Decimal("2400")
EFFICACY_CONFIDENCE = Decimal("0.95")
FUTILITY_MONTHS = 18
FUTILITY_TRADES = Decimal("1400")
FUTILITY_CONFIDENCE = Decimal("0.99")
EDGE_PER_TRADE = Decimal("0.10")


class DecisionState(StrEnum):
    """The exhaustive public outcomes of the fixed forward-test protocol."""

    NO_DECISION = auto()
    FUTILITY_STOP = auto()
    PASS = auto()
    FAIL = auto()
    INCONCLUSIVE = auto()


@dataclass(frozen=True)
class MeanBounds:
    """Exact bootstrap mean and one-sided empirical percentile bounds."""

    mean_daily_net_r: Decimal
    lower: Decimal
    upper: Decimal


@dataclass(frozen=True)
class BlockBounds:
    """Bounds associated with one mean stationary-bootstrap block length."""

    block_length: int
    bounds: MeanBounds


@dataclass(frozen=True)
class EfficacyAnalysis:
    """Endpoint-only efficacy statistics and fixed-block sensitivity."""

    daily_threshold: Decimal
    production: BlockBounds
    sensitivity: tuple[BlockBounds, ...]
    replications: int
    seed: int


@dataclass(frozen=True)
class FutilityAnalysis:
    """Statistics disclosed only when the permitted futility condition is met."""

    production: BlockBounds
    sensitivity: tuple[BlockBounds, ...]
    replications: int
    seed: int


@dataclass(frozen=True)
class ForwardDecision:
    """One read-only protocol evaluation at an explicit data cutoff."""

    cohort_id: UUID
    observation_source: ObservationSource
    cohort_status: CohortStatus
    registered_thresholds: tuple[tuple[str, Decimal], ...]
    registered_minimum_calendar_days: Decimal
    registered_minimum_trade_count: Decimal
    as_of_date: date
    endpoint_date: date
    futility_date: date
    realized_trade_count: Decimal
    observation_day_count: Decimal
    state: DecisionState
    efficacy: EfficacyAnalysis | None
    futility: FutilityAnalysis | None


def _finite_decimal(value: Decimal, label: str) -> Decimal:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise TypeError(f"{label} must be a finite Decimal")
    return value


def _nonnegative_integral_decimal(value: Decimal, label: str) -> Decimal:
    checked = _finite_decimal(value, label)
    if checked < 0 or checked != checked.to_integral_value():
        raise ValueError(f"{label} must be a non-negative integral Decimal")
    return checked


def _positive_integral_decimal(value: Decimal, label: str) -> Decimal:
    checked = _finite_decimal(value, label)
    if checked <= 0 or checked != checked.to_integral_value():
        raise ValueError(f"{label} must be a positive integral Decimal")
    return checked


def _positive_int(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


def _seed(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("seed must be an integer")
    return value


def daily_threshold(
    realized_trade_count: Decimal,
    observation_day_count: Decimal,
) -> Decimal:
    """Convert the fixed +0.10R per-trade edge to exact daily net portfolio R."""
    trades = _nonnegative_integral_decimal(realized_trade_count, "realized_trade_count")
    days = _positive_integral_decimal(observation_day_count, "observation_day_count")
    return EDGE_PER_TRADE * trades / days


def _calendar_anniversary(start_timestamp: datetime, months: int) -> date:
    if (
        not isinstance(start_timestamp, datetime)
        or start_timestamp.tzinfo is None
        or start_timestamp.utcoffset() is None
    ):
        raise ValueError("cohort start_timestamp must be timezone-aware")
    if isinstance(months, bool) or not isinstance(months, int) or months < 0:
        raise ValueError("months must be a non-negative integer")
    start = start_timestamp.date()
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def endpoint_reached(
    start_timestamp: datetime,
    as_of_date: date,
    realized_trade_count: Decimal,
) -> bool:
    """Return whether both fixed efficacy endpoint conditions hold."""
    if not isinstance(as_of_date, date) or isinstance(as_of_date, datetime):
        raise TypeError("as_of_date must be a date")
    trades = _nonnegative_integral_decimal(realized_trade_count, "realized_trade_count")
    return (
        as_of_date >= _calendar_anniversary(start_timestamp, EFFICACY_MONTHS)
        and trades >= EFFICACY_TRADES
    )


def _futility_reached(
    start_timestamp: datetime,
    as_of_date: date,
    realized_trade_count: Decimal,
) -> bool:
    return (
        as_of_date >= _calendar_anniversary(start_timestamp, FUTILITY_MONTHS)
        and realized_trade_count >= FUTILITY_TRADES
    )


def _validated_daily_values(values: Sequence[Decimal]) -> tuple[Decimal, ...]:
    result = tuple(_finite_decimal(value, "daily_net_portfolio_r") for value in values)
    if not result:
        raise ValueError("daily net portfolio R must contain at least one observation")
    return result


def _nearest_rank(sorted_values: Sequence[Decimal], probability: Decimal) -> Decimal:
    if not sorted_values:
        raise ValueError("quantile values must be non-empty")
    checked = _finite_decimal(probability, "probability")
    if checked <= 0 or checked >= 1:
        raise ValueError("probability must be strictly between zero and one")
    sample_count = Decimal(len(sorted_values))
    rank = int((checked * sample_count).to_integral_value(rounding=ROUND_CEILING))
    return sorted_values[max(1, rank) - 1]


def bootstrap_mean_bounds(
    daily_net_r: Sequence[Decimal],
    mean_block_length: int,
    confidence: Decimal,
    *,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> MeanBounds:
    """Return exact empirical one-sided bounds from P-04 stationary resample indices.

    P-04 emits binary-float arrays, so the resampler receives integral observation indices rather
    than R values. Each sampled index selects the original exact Decimal observation; all means,
    quantile ranks, bounds, and comparisons therefore remain Decimal.
    """
    values = _validated_daily_values(daily_net_r)
    block_length = _positive_int(mean_block_length, "mean_block_length")
    repetitions = _positive_int(replications, "replications")
    random_seed = _seed(seed)
    level = _finite_decimal(confidence, "confidence")
    if level <= 0 or level >= 1:
        raise ValueError("confidence must be strictly between zero and one")

    sample_size = len(values)
    denominator = Decimal(sample_size)
    resampled_indices = stationary_bootstrap(
        range(sample_size),
        block_length,
        replications=repetitions,
        seed=random_seed,
    )
    means: list[Decimal] = []
    for path in resampled_indices:
        total = Decimal("0")
        for raw_index in path:
            index = int(raw_index)
            if raw_index != index or index < 0 or index >= sample_size:
                raise RuntimeError("stationary bootstrap returned a non-integral index")
            total += values[index]
        means.append(total / denominator)
    means.sort()
    return MeanBounds(
        mean_daily_net_r=sum(values, Decimal("0")) / denominator,
        lower=_nearest_rank(means, Decimal("1") - level),
        upper=_nearest_rank(means, level),
    )


def _block_analyses(
    values: tuple[Decimal, ...],
    cohort_id: UUID,
    confidence: Decimal,
    *,
    replications: int,
    seed: int,
) -> tuple[BlockBounds, tuple[BlockBounds, ...]]:
    production_length = select_block_length(
        {f"cohort:{cohort_id}": tuple(str(value) for value in values)}
    )
    cache: dict[int, MeanBounds] = {}

    def analyze(block_length: int) -> BlockBounds:
        if block_length not in cache:
            cache[block_length] = bootstrap_mean_bounds(
                values,
                block_length,
                confidence,
                replications=replications,
                seed=seed,
            )
        return BlockBounds(block_length, cache[block_length])

    production = analyze(production_length)
    sensitivity = tuple(analyze(block_length) for block_length in SENSITIVITY_BLOCK_LENGTHS)
    return production, sensitivity


def _validate_series(
    cohort: Cohort,
    series: ObservationSeries,
    as_of_date: date,
) -> tuple[Decimal, ...]:
    if series.cohort_id != cohort.cohort_id:
        raise ValueError("observation series belongs to a different cohort")
    if series.source is not cohort.observation_source:
        raise ValueError("observation series source does not match the cohort")
    start_date = cohort.start_timestamp.date()
    seen_days: set[date] = set()
    selected: list[tuple[date, Decimal]] = []
    for observation in series.observations:
        if not isinstance(observation.loss_day, date) or isinstance(observation.loss_day, datetime):
            raise TypeError("observation loss_day must be a date")
        if observation.loss_day < start_date:
            raise ValueError("observation loss_day is before cohort start")
        if observation.loss_day in seen_days:
            raise ValueError("observation series repeats a loss day")
        seen_days.add(observation.loss_day)
        value = _finite_decimal(
            observation.daily_net_portfolio_r,
            "daily_net_portfolio_r",
        )
        if observation.loss_day <= as_of_date:
            selected.append((observation.loss_day, value))
    selected.sort(key=lambda item: item[0])
    return tuple(value for _, value in selected)


def _decision(
    cohort: Cohort,
    *,
    as_of_date: date,
    realized_trade_count: Decimal,
    observation_day_count: Decimal,
    state: DecisionState,
    efficacy: EfficacyAnalysis | None = None,
    futility: FutilityAnalysis | None = None,
) -> ForwardDecision:
    return ForwardDecision(
        cohort_id=cohort.cohort_id,
        observation_source=cohort.observation_source,
        cohort_status=cohort.status,
        registered_thresholds=tuple(sorted(cohort.thresholds.items())),
        registered_minimum_calendar_days=cohort.minimum_calendar_days,
        registered_minimum_trade_count=cohort.minimum_trade_count,
        as_of_date=as_of_date,
        endpoint_date=_calendar_anniversary(cohort.start_timestamp, EFFICACY_MONTHS),
        futility_date=_calendar_anniversary(cohort.start_timestamp, FUTILITY_MONTHS),
        realized_trade_count=realized_trade_count,
        observation_day_count=observation_day_count,
        state=state,
        efficacy=efficacy,
        futility=futility,
    )


def evaluate_forward_test(
    registry: ForwardTestRegistry,
    cohort_id: UUID,
    realized_trade_count: Decimal,
    as_of_date: date,
    *,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> ForwardDecision:
    """Evaluate one registry cohort without writing data or exposing early efficacy."""
    trades = _nonnegative_integral_decimal(realized_trade_count, "realized_trade_count")
    repetitions = _positive_int(replications, "replications")
    random_seed = _seed(seed)
    if not isinstance(as_of_date, date) or isinstance(as_of_date, datetime):
        raise TypeError("as_of_date must be a date")

    cohort = registry.cohort(cohort_id)
    start_date = _calendar_anniversary(cohort.start_timestamp, 0)
    if as_of_date < start_date:
        raise ValueError("as_of_date is before cohort start")
    values = _validate_series(cohort, registry.observations(cohort_id), as_of_date)
    observed_days = Decimal(len(values))

    if endpoint_reached(cohort.start_timestamp, as_of_date, trades):
        threshold = daily_threshold(trades, observed_days)
        production, sensitivity = _block_analyses(
            values,
            cohort.cohort_id,
            EFFICACY_CONFIDENCE,
            replications=repetitions,
            seed=random_seed,
        )
        if production.bounds.lower > threshold:
            state = DecisionState.PASS
        elif production.bounds.upper < threshold:
            state = DecisionState.FAIL
        else:
            state = DecisionState.INCONCLUSIVE
        return _decision(
            cohort,
            as_of_date=as_of_date,
            realized_trade_count=trades,
            observation_day_count=observed_days,
            state=state,
            efficacy=EfficacyAnalysis(
                threshold,
                production,
                sensitivity,
                repetitions,
                random_seed,
            ),
        )

    if _futility_reached(cohort.start_timestamp, as_of_date, trades):
        production, sensitivity = _block_analyses(
            values,
            cohort.cohort_id,
            FUTILITY_CONFIDENCE,
            replications=repetitions,
            seed=random_seed,
        )
        if production.bounds.upper < 0:
            return _decision(
                cohort,
                as_of_date=as_of_date,
                realized_trade_count=trades,
                observation_day_count=observed_days,
                state=DecisionState.FUTILITY_STOP,
                futility=FutilityAnalysis(
                    production,
                    sensitivity,
                    repetitions,
                    random_seed,
                ),
            )

    return _decision(
        cohort,
        as_of_date=as_of_date,
        realized_trade_count=trades,
        observation_day_count=observed_days,
        state=DecisionState.NO_DECISION,
    )
