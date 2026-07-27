"""Exact account-limit replay over complete P-10 loss-day bootstrap paths.

P-10 owns the scenario schema, Politis-White block selection, and stationary-bootstrap draw.
This module consumes those paths as immutable day bundles. It replays balance, close equity, and
the synchronized H4 minimum through the internal and prop-firm limits, then applies exact
one-sided Clopper-Pearson bounds to the two Stage-4 decision probabilities.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, Decimal, localcontext
from functools import cached_property

from research.portfolio.resample import DEFAULT_REPLICATIONS, DEFAULT_SEED
from research.portfolio.scenarios import (
    LossDayScenario,
    sample_scenario_paths,
    scenario_bootstrap_choices,
    scenario_path_probability_of_profit,
)

INTERNAL_DAILY_LIMIT = Decimal("0.025")
INTERNAL_TRAILING_LIMIT = Decimal("0.05")
PROP_DAILY_LIMIT = Decimal("0.03")
PROP_TRAILING_LIMIT = Decimal("0.06")
BREACH_PROBABILITY_LIMIT = Decimal("0.01")
NEGATIVE_RETURN_PROBABILITY_LIMIT = Decimal("0.05")
BOUND_CONFIDENCE = Decimal("0.95")
_FIVE_PERCENT = Decimal("0.05")
_HALF = Decimal("0.5")
_NINETY_FIVE_PERCENT = Decimal("0.95")
_BOUND_PRECISION = 60


def _validate_probability(value: Decimal, *, label: str) -> None:
    if not value.is_finite() or value < 0 or value > 1:
        raise ValueError(f"{label} must be a finite probability")


def _binomial_cdf(events: int, trials: int, probability: Decimal) -> Decimal:
    """Return ``P(X <= events)`` for ``X ~ Binomial(trials, probability)``."""
    if probability == 0:
        return Decimal("1")
    if probability == 1:
        return Decimal(int(events == trials))
    complement = Decimal("1") - probability
    term = complement**trials
    total = term
    odds = probability / complement
    for observed in range(events):
        term *= Decimal(trials - observed) * odds / Decimal(observed + 1)
        total += term
    return total


def clopper_pearson_upper(
    events: int,
    trials: int,
    *,
    confidence: Decimal = BOUND_CONFIDENCE,
) -> Decimal:
    """Return the exact one-sided Clopper-Pearson upper probability bound.

    For ``events < trials``, the upper limit is the unique probability where the exact binomial
    lower tail ``P(X <= events)`` equals ``1 - confidence``. Bisection returns the upper bracket,
    so finite Decimal precision cannot make the gate anti-conservative.
    """
    if (
        isinstance(events, bool)
        or isinstance(trials, bool)
        or not isinstance(events, int)
        or not isinstance(trials, int)
    ):
        raise TypeError("event and trial counts must be integers")
    if trials <= 0:
        raise ValueError("trial count must be positive")
    if events < 0 or events > trials:
        raise ValueError("event count must be between zero and the trial count")
    _validate_probability(confidence, label="confidence")
    if confidence <= 0 or confidence >= 1:
        raise ValueError("confidence must be strictly between zero and one")
    if events == trials:
        return Decimal("1")

    with localcontext() as context:
        context.prec = _BOUND_PRECISION
        alpha = Decimal("1") - confidence
        lower = Decimal(events) / Decimal(trials)
        upper = Decimal("1")
        while True:
            midpoint = (lower + upper) / 2
            if midpoint in (lower, upper):
                break
            cdf = _binomial_cdf(events, trials, midpoint)
            if cdf > alpha:
                lower = midpoint
            else:
                upper = midpoint
        return +upper


@dataclass(frozen=True)
class PathReplay:
    """One sampled path's exact return, drawdown, water time, and breach flags."""

    final_return: Decimal
    max_drawdown: Decimal
    time_under_water: Decimal
    internal_daily_breach: bool
    internal_trailing_breach: bool
    prop_daily_breach: bool
    prop_trailing_breach: bool

    @property
    def internal_any_breach(self) -> bool:
        return self.internal_daily_breach or self.internal_trailing_breach

    @property
    def prop_any_breach(self) -> bool:
        return self.prop_daily_breach or self.prop_trailing_breach


def replay_scenario_path(
    path: Sequence[LossDayScenario],
    *,
    start_balance: Decimal,
) -> PathReplay:
    """Replay one complete P-10 path through internal and prop-firm account limits."""
    if not path:
        raise ValueError("scenario path must be non-empty")
    if not start_balance.is_finite() or start_balance <= 0:
        raise ValueError("start balance must be finite and positive")
    if not (INTERNAL_DAILY_LIMIT < PROP_DAILY_LIMIT):
        raise RuntimeError("internal daily limit must be strictly tighter than the prop limit")
    if not (INTERNAL_TRAILING_LIMIT < PROP_TRAILING_LIMIT):
        raise RuntimeError("internal trailing limit must be strictly tighter than the prop limit")

    balance = start_balance
    close_equity = start_balance
    balance_hwm = start_balance
    equity_hwm = start_balance
    max_drawdown = Decimal("0")
    underwater_days = 0
    internal_daily = False
    internal_trailing = False
    prop_daily = False
    prop_trailing = False

    for scenario in path:
        opening_balance = balance
        minimum_equity = opening_balance + scenario.opening_to_minimum_equity_change
        balance += scenario.closing_balance_change
        close_equity += scenario.close_equity_change

        loss_money = max(Decimal("0"), opening_balance - minimum_equity)
        if opening_balance <= 0:
            internal_daily = True
            prop_daily = True
        else:
            internal_daily |= loss_money >= INTERNAL_DAILY_LIMIT * opening_balance
            prop_daily |= loss_money >= PROP_DAILY_LIMIT * opening_balance

        # Match P-09's conservative convention: the same day's realized close can raise the
        # trailing HWM before that day's synchronized H4 minimum is checked.
        balance_hwm = max(balance_hwm, balance)
        internal_floor = min(
            start_balance,
            balance_hwm - INTERNAL_TRAILING_LIMIT * start_balance,
        )
        prop_floor = min(
            start_balance,
            balance_hwm - PROP_TRAILING_LIMIT * start_balance,
        )
        internal_trailing |= minimum_equity <= internal_floor
        prop_trailing |= minimum_equity <= prop_floor

        equity_hwm = max(equity_hwm, close_equity)
        drawdown = max(Decimal("0"), (equity_hwm - minimum_equity) / equity_hwm)
        max_drawdown = max(max_drawdown, drawdown)
        underwater_days += int(close_equity < equity_hwm)

    if prop_daily and not internal_daily:
        raise RuntimeError("prop daily breach occurred without an internal daily breach")
    if prop_trailing and not internal_trailing:
        raise RuntimeError("prop trailing breach occurred without an internal trailing breach")

    return PathReplay(
        final_return=(balance - start_balance) / start_balance,
        max_drawdown=max_drawdown,
        time_under_water=Decimal(underwater_days) / Decimal(len(path)),
        internal_daily_breach=internal_daily,
        internal_trailing_breach=internal_trailing,
        prop_daily_breach=prop_daily,
        prop_trailing_breach=prop_trailing,
    )


def _nearest_rank(values: Sequence[Decimal], probability: Decimal) -> Decimal:
    if not values:
        raise ValueError("empirical distribution must be non-empty")
    if probability <= 0 or probability > 1:
        raise ValueError("nearest-rank probability must be in (0, 1]")
    ordered = sorted(values)
    rank = int((probability * Decimal(len(ordered))).to_integral_value(rounding=ROUND_CEILING))
    return ordered[rank - 1]


def _probability(count: int, trials: int) -> Decimal:
    return Decimal(count) / Decimal(trials)


@dataclass(frozen=True)
class PathRiskMetrics:
    """Empirical path distribution for one registered block-length choice."""

    prob_profit: Decimal
    negative_final_probability: Decimal
    final_return_p05: Decimal
    final_return_median: Decimal
    final_return_p95: Decimal
    expected_shortfall_05: Decimal
    max_drawdown_p05: Decimal
    max_drawdown_median: Decimal
    max_drawdown_p95: Decimal
    internal_daily_breach_probability: Decimal
    internal_trailing_breach_probability: Decimal
    internal_any_breach_probability: Decimal
    prop_daily_breach_probability: Decimal
    prop_trailing_breach_probability: Decimal
    prop_any_breach_probability: Decimal
    time_under_water_p05: Decimal
    time_under_water_median: Decimal
    time_under_water_p95: Decimal
    internal_any_breach_count: int
    negative_final_count: int

    def __post_init__(self) -> None:
        probabilities = {
            "probability of profit": self.prob_profit,
            "negative final probability": self.negative_final_probability,
            "internal daily breach probability": self.internal_daily_breach_probability,
            "internal trailing breach probability": self.internal_trailing_breach_probability,
            "internal any breach probability": self.internal_any_breach_probability,
            "prop daily breach probability": self.prop_daily_breach_probability,
            "prop trailing breach probability": self.prop_trailing_breach_probability,
            "prop any breach probability": self.prop_any_breach_probability,
            "time under water p05": self.time_under_water_p05,
            "time under water median": self.time_under_water_median,
            "time under water p95": self.time_under_water_p95,
        }
        for label, value in probabilities.items():
            _validate_probability(value, label=label)
        statistics = {
            "final return p05": self.final_return_p05,
            "final return median": self.final_return_median,
            "final return p95": self.final_return_p95,
            "expected shortfall": self.expected_shortfall_05,
            "maximum drawdown p05": self.max_drawdown_p05,
            "maximum drawdown median": self.max_drawdown_median,
            "maximum drawdown p95": self.max_drawdown_p95,
        }
        if any(not value.is_finite() for value in statistics.values()):
            raise ValueError("path-risk statistics must be finite")
        if self.internal_daily_breach_probability < self.prop_daily_breach_probability:
            raise ValueError("internal breach probability is below prop daily probability")
        if self.internal_trailing_breach_probability < self.prop_trailing_breach_probability:
            raise ValueError("internal breach probability is below prop trailing probability")
        if self.internal_any_breach_probability < self.prop_any_breach_probability:
            raise ValueError("internal breach probability is below prop any-limit probability")
        if self.internal_any_breach_probability < self.internal_daily_breach_probability:
            raise ValueError("internal any-limit probability is below its daily component")
        if self.internal_any_breach_probability < self.internal_trailing_breach_probability:
            raise ValueError("internal any-limit probability is below its trailing component")
        if self.prop_any_breach_probability < self.prop_daily_breach_probability:
            raise ValueError("prop any-limit probability is below its daily component")
        if self.prop_any_breach_probability < self.prop_trailing_breach_probability:
            raise ValueError("prop any-limit probability is below its trailing component")
        if self.prob_profit + self.negative_final_probability > 1:
            raise ValueError("profit and negative-return probabilities overlap")
        if not (
            self.final_return_p05 <= self.final_return_median <= self.final_return_p95
        ):
            raise ValueError("final-return percentiles must be ordered")
        if self.expected_shortfall_05 > self.final_return_p05:
            raise ValueError("expected shortfall must not exceed the fifth percentile")
        if not (
            self.max_drawdown_p05
            <= self.max_drawdown_median
            <= self.max_drawdown_p95
        ):
            raise ValueError("maximum-drawdown percentiles must be ordered")
        if not (
            self.time_under_water_p05
            <= self.time_under_water_median
            <= self.time_under_water_p95
        ):
            raise ValueError("time-under-water percentiles must be ordered")
        if self.internal_any_breach_count < 0 or self.negative_final_count < 0:
            raise ValueError("path event counts must be non-negative")

    def to_json(self) -> dict[str, str | int]:
        return {
            "prob_profit": str(self.prob_profit),
            "negative_final_probability": str(self.negative_final_probability),
            "final_return_p05": str(self.final_return_p05),
            "final_return_median": str(self.final_return_median),
            "final_return_p95": str(self.final_return_p95),
            "expected_shortfall_05": str(self.expected_shortfall_05),
            "max_drawdown_p05": str(self.max_drawdown_p05),
            "max_drawdown_median": str(self.max_drawdown_median),
            "max_drawdown_p95": str(self.max_drawdown_p95),
            "internal_daily_breach_probability": str(self.internal_daily_breach_probability),
            "internal_trailing_breach_probability": str(self.internal_trailing_breach_probability),
            "internal_any_breach_probability": str(self.internal_any_breach_probability),
            "prop_daily_breach_probability": str(self.prop_daily_breach_probability),
            "prop_trailing_breach_probability": str(self.prop_trailing_breach_probability),
            "prop_any_breach_probability": str(self.prop_any_breach_probability),
            "time_under_water_p05": str(self.time_under_water_p05),
            "time_under_water_median": str(self.time_under_water_median),
            "time_under_water_p95": str(self.time_under_water_p95),
            "internal_any_breach_count": self.internal_any_breach_count,
            "negative_final_count": self.negative_final_count,
        }


def summarize_sampled_paths(
    paths: Sequence[Sequence[LossDayScenario]],
    *,
    start_balance: Decimal,
) -> PathRiskMetrics:
    """Summarize an already-sampled P-10 path collection without resampling it."""
    if not paths:
        raise ValueError("sampled path collection must be non-empty")
    horizon_days = len(paths[0])
    if horizon_days <= 0 or any(len(path) != horizon_days for path in paths):
        raise ValueError("sampled paths must share one positive calendar-day horizon")
    replays = tuple(replay_scenario_path(path, start_balance=start_balance) for path in paths)
    finals = tuple(replay.final_return for replay in replays)
    drawdowns = tuple(replay.max_drawdown for replay in replays)
    water = tuple(replay.time_under_water for replay in replays)
    trials = len(replays)
    tail_count = max(
        1,
        int((_FIVE_PERCENT * Decimal(trials)).to_integral_value(rounding=ROUND_CEILING)),
    )
    worst_returns = sorted(finals)[:tail_count]

    negative = sum(value < 0 for value in finals)
    internal_daily = sum(replay.internal_daily_breach for replay in replays)
    internal_trailing = sum(replay.internal_trailing_breach for replay in replays)
    internal_any = sum(replay.internal_any_breach for replay in replays)
    prop_daily = sum(replay.prop_daily_breach for replay in replays)
    prop_trailing = sum(replay.prop_trailing_breach for replay in replays)
    prop_any = sum(replay.prop_any_breach for replay in replays)

    return PathRiskMetrics(
        prob_profit=scenario_path_probability_of_profit(paths),
        negative_final_probability=_probability(negative, trials),
        final_return_p05=_nearest_rank(finals, _FIVE_PERCENT),
        final_return_median=_nearest_rank(finals, _HALF),
        final_return_p95=_nearest_rank(finals, _NINETY_FIVE_PERCENT),
        expected_shortfall_05=sum(worst_returns) / Decimal(tail_count),
        max_drawdown_p05=_nearest_rank(drawdowns, _FIVE_PERCENT),
        max_drawdown_median=_nearest_rank(drawdowns, _HALF),
        max_drawdown_p95=_nearest_rank(drawdowns, _NINETY_FIVE_PERCENT),
        internal_daily_breach_probability=_probability(internal_daily, trials),
        internal_trailing_breach_probability=_probability(internal_trailing, trials),
        internal_any_breach_probability=_probability(internal_any, trials),
        prop_daily_breach_probability=_probability(prop_daily, trials),
        prop_trailing_breach_probability=_probability(prop_trailing, trials),
        prop_any_breach_probability=_probability(prop_any, trials),
        time_under_water_p05=_nearest_rank(water, _FIVE_PERCENT),
        time_under_water_median=_nearest_rank(water, _HALF),
        time_under_water_p95=_nearest_rank(water, _NINETY_FIVE_PERCENT),
        internal_any_breach_count=internal_any,
        negative_final_count=negative,
    )


@dataclass(frozen=True)
class PathRiskSensitivity:
    """One P-10 block choice and its complete P-11 path-risk distribution."""

    label: str
    block_length: int
    metrics: PathRiskMetrics

    def to_json(self) -> dict[str, str | int]:
        return {
            "label": self.label,
            "block_length": self.block_length,
            **self.metrics.to_json(),
        }


@dataclass(frozen=True)
class PathRiskSummary:
    """Selected path-risk gates plus all registered block-length sensitivities."""

    seed: int
    replications: int
    horizon_days: int
    selected_block_length: int
    sensitivity: tuple[PathRiskSensitivity, ...]

    def __post_init__(self) -> None:
        if (
            isinstance(self.seed, bool)
            or isinstance(self.replications, bool)
            or isinstance(self.horizon_days, bool)
            or isinstance(self.selected_block_length, bool)
            or not isinstance(self.seed, int)
            or not isinstance(self.replications, int)
            or not isinstance(self.horizon_days, int)
            or not isinstance(self.selected_block_length, int)
        ):
            raise TypeError("path-risk summary seed and counts must be integers")
        if self.replications <= 0 or self.horizon_days <= 0:
            raise ValueError("path-risk summary counts must be positive")
        if self.selected_block_length <= 0:
            raise ValueError("selected block length must be positive")
        expected_labels = ("plugin", "fixed_5", "fixed_10", "fixed_20", "fixed_60")
        if tuple(item.label for item in self.sensitivity) != expected_labels:
            raise ValueError("path-risk sensitivity labels are incomplete or out of order")
        if self.sensitivity[0].block_length != self.selected_block_length:
            raise ValueError("selected block length disagrees with the plug-in result")
        for item in self.sensitivity:
            if item.block_length <= 0:
                raise ValueError("sensitivity block lengths must be positive")
            if item.metrics.internal_any_breach_count > self.replications:
                raise ValueError("internal breach count exceeds the replication count")
            if item.metrics.negative_final_count > self.replications:
                raise ValueError("negative return count exceeds the replication count")
            if item.metrics.internal_any_breach_probability != _probability(
                item.metrics.internal_any_breach_count,
                self.replications,
            ):
                raise ValueError("internal breach count and probability disagree")
            if item.metrics.negative_final_probability != _probability(
                item.metrics.negative_final_count,
                self.replications,
            ):
                raise ValueError("negative return count and probability disagree")

    @property
    def selected(self) -> PathRiskMetrics:
        return self.sensitivity[0].metrics

    @property
    def prob_profit(self) -> Decimal:
        """P-10's selected probability-of-profit diagnostic."""
        return self.selected.prob_profit

    @cached_property
    def internal_breach_upper_95(self) -> Decimal:
        return clopper_pearson_upper(
            self.selected.internal_any_breach_count,
            self.replications,
        )

    @cached_property
    def negative_return_upper_95(self) -> Decimal:
        return clopper_pearson_upper(
            self.selected.negative_final_count,
            self.replications,
        )

    @property
    def internal_breach_gate_passes(self) -> bool:
        return self.internal_breach_upper_95 <= BREACH_PROBABILITY_LIMIT

    @property
    def negative_return_gate_passes(self) -> bool:
        return self.negative_return_upper_95 <= NEGATIVE_RETURN_PROBABILITY_LIMIT

    def to_json(self) -> dict[str, object]:
        selected = self.selected.to_json()
        selected.update(
            {
                "internal_breach_upper_95": str(self.internal_breach_upper_95),
                "negative_return_upper_95": str(self.negative_return_upper_95),
                "internal_breach_gate_limit": str(BREACH_PROBABILITY_LIMIT),
                "negative_return_gate_limit": str(NEGATIVE_RETURN_PROBABILITY_LIMIT),
                "internal_breach_gate_passes": self.internal_breach_gate_passes,
                "negative_return_gate_passes": self.negative_return_gate_passes,
            }
        )
        return {
            "method": "P-10 complete loss-day stationary bootstrap with P-11 limit replay",
            "seed": self.seed,
            "replications": self.replications,
            "horizon_days": self.horizon_days,
            "selected_block_length": self.selected_block_length,
            "confidence": str(BOUND_CONFIDENCE),
            "prob_profit": str(self.prob_profit),
            "selected": selected,
            "sensitivity": [item.to_json() for item in self.sensitivity],
        }


def summarize_path_risk(
    scenarios: Sequence[LossDayScenario],
    *,
    start_balance: Decimal,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> PathRiskSummary:
    """Consume P-10 paths and report P-11 risk without rebuilding either mechanism."""
    source = tuple(scenarios)
    choices = scenario_bootstrap_choices(source)
    sensitivity: list[PathRiskSensitivity] = []
    for label, block_length in choices:
        paths = sample_scenario_paths(
            source,
            mean_block_length=block_length,
            replications=replications,
            seed=seed,
        )
        metrics = summarize_sampled_paths(paths, start_balance=start_balance)
        sensitivity.append(
            PathRiskSensitivity(
                label=label,
                block_length=block_length,
                metrics=metrics,
            )
        )
    return PathRiskSummary(
        seed=seed,
        replications=replications,
        horizon_days=len(source),
        selected_block_length=choices[0][1],
        sensitivity=tuple(sensitivity),
    )
