"""Hansen-Lunde-Nason Model Confidence Set for candidate return families.

The range procedure compares negative daily net returns on P-03's common day grid. It reuses
P-05's P-04-backed paired stationary-bootstrap indices and long-run-variance estimator, then
publishes monotone model p-values and exact 90% membership for later selection by P-08.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import numpy as np
import numpy.typing as npt

from research.engine.spa import (
    SpaInputError,
    _monte_carlo_p_value,
    _validated_matrix,
    stationary_bootstrap_indices,
    stationary_bootstrap_variances,
)
from research.portfolio.resample import DEFAULT_REPLICATIONS, DEFAULT_SEED

MCS_ALPHA = Decimal("0.10")
MCS_CONFIDENCE = Decimal("0.90")
MCS_SCHEMA_VERSION = 1
MCS_ARTIFACT = "mcs.json"
MCS_METHOD = "Hansen-Lunde-Nason (2011) range-statistic Model Confidence Set"
MCS_LOSS = "negative daily net return"
MCS_STATISTIC = "T_R"
MIN_OBSERVATIONS = 3

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]


class McsInputError(ValueError):
    """The candidate family or serialized MCS evidence is invalid."""


def _finite_float(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (int, float, Decimal, np.integer, np.floating),
    ):
        raise McsInputError(f"{label} must be finite")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise McsInputError(f"{label} must be finite") from exc
    if not math.isfinite(result):
        raise McsInputError(f"{label} must be finite")
    return result


def _probability(value: object, *, label: str) -> float:
    result = _finite_float(value, label=label)
    if not 0.0 <= result <= 1.0:
        raise McsInputError(f"{label} must be between zero and one")
    return result


def _positive_integer(value: object, *, label: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise McsInputError(f"{label} must be an integer of at least {minimum}")
    result = int(value)
    if result < minimum:
        raise McsInputError(f"{label} must be an integer of at least {minimum}")
    return result


@dataclass(frozen=True)
class RangeDecision:
    """One equivalence-test result and its coherent range elimination."""

    statistic: float
    p_value: float
    eliminated: str
    elimination_score: float


@dataclass(frozen=True)
class McsStep:
    """One nested equivalence test before removing its worst candidate."""

    current_candidates: tuple[str, ...]
    statistic: float
    p_value: float
    eliminated: str
    elimination_score: float

    def __post_init__(self) -> None:
        if len(self.current_candidates) < 2:
            raise McsInputError("MCS step must contain at least two candidates")
        if tuple(sorted(self.current_candidates)) != self.current_candidates:
            raise McsInputError("MCS step candidates must be sorted")
        if len(set(self.current_candidates)) != len(self.current_candidates):
            raise McsInputError("MCS step candidates must be unique")
        if any(not name for name in self.current_candidates):
            raise McsInputError("MCS step candidate names must be non-empty")
        if self.eliminated not in self.current_candidates:
            raise McsInputError("MCS eliminated candidate must belong to the current set")
        statistic = _finite_float(self.statistic, label="MCS range statistic")
        if statistic < 0.0:
            raise McsInputError("MCS range statistic must be non-negative")
        _probability(self.p_value, label="MCS set p_value")
        _finite_float(self.elimination_score, label="MCS elimination score")

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_candidates": list(self.current_candidates),
            "set_size": len(self.current_candidates),
            "statistic": self.statistic,
            "p_value": self.p_value,
            "eliminated": self.eliminated,
            "elimination_score": self.elimination_score,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> McsStep:
        try:
            current_raw = payload["current_candidates"]
            if not isinstance(current_raw, list) or not all(
                isinstance(name, str) for name in current_raw
            ):
                raise McsInputError("MCS step candidates must be a string list")
            step = cls(
                current_candidates=tuple(current_raw),
                statistic=_finite_float(payload["statistic"], label="MCS range statistic"),
                p_value=_probability(payload["p_value"], label="MCS set p_value"),
                eliminated=payload["eliminated"],
                elimination_score=_finite_float(
                    payload["elimination_score"],
                    label="MCS elimination score",
                ),
            )
            if not isinstance(step.eliminated, str):
                raise McsInputError("MCS eliminated candidate must be a string")
            set_size = _positive_integer(payload["set_size"], label="MCS set_size", minimum=2)
        except KeyError as exc:
            raise McsInputError(f"MCS step is missing {exc.args[0]!r}") from exc
        if set_size != len(step.current_candidates):
            raise McsInputError("MCS step set_size disagrees with its candidates")
        return step


@dataclass(frozen=True)
class McsCandidate:
    """One candidate's loss, elimination rank, p-value, and derived membership."""

    name: str
    mean_loss: float
    elimination_rank: int
    mcs_p_value: float

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name:
            raise McsInputError("MCS candidate name must be a non-empty string")
        _finite_float(self.mean_loss, label=f"MCS candidate {self.name!r} mean_loss")
        _positive_integer(
            self.elimination_rank,
            label=f"MCS candidate {self.name!r} elimination_rank",
        )
        _probability(
            self.mcs_p_value,
            label=f"MCS candidate {self.name!r} mcs_p_value",
        )

    @property
    def in_mcs(self) -> bool:
        """Return exact 90% membership from the model p-value."""
        return Decimal(str(self.mcs_p_value)) >= MCS_ALPHA

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mean_loss": self.mean_loss,
            "elimination_rank": self.elimination_rank,
            "mcs_p_value": self.mcs_p_value,
            "in_mcs": self.in_mcs,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> McsCandidate:
        try:
            candidate = cls(
                name=payload["name"],
                mean_loss=_finite_float(payload["mean_loss"], label="MCS candidate mean_loss"),
                elimination_rank=_positive_integer(
                    payload["elimination_rank"],
                    label="MCS candidate elimination_rank",
                ),
                mcs_p_value=_probability(
                    payload["mcs_p_value"],
                    label="MCS candidate mcs_p_value",
                ),
            )
        except KeyError as exc:
            raise McsInputError(f"MCS candidate is missing {exc.args[0]!r}") from exc
        if not isinstance(candidate.name, str):
            raise McsInputError("MCS candidate name must be a string")
        recorded = payload.get("in_mcs")
        if not isinstance(recorded, bool) or recorded != candidate.in_mcs:
            raise McsInputError("MCS membership flag disagrees with its p-value")
        return candidate


@dataclass(frozen=True)
class McsResult:
    """Complete range-elimination path and 90% model confidence set."""

    candidates: tuple[McsCandidate, ...]
    steps: tuple[McsStep, ...]
    block_length: int
    replications: int
    seed: int
    observation_count: int

    def __post_init__(self) -> None:
        _positive_integer(self.block_length, label="MCS block_length")
        _positive_integer(self.replications, label="MCS replications", minimum=2)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise McsInputError("MCS seed must be an integer")
        _positive_integer(
            self.observation_count,
            label="MCS observation_count",
            minimum=MIN_OBSERVATIONS,
        )
        if not self.candidates:
            raise McsInputError("MCS requires at least one candidate")
        names = tuple(candidate.name for candidate in self.candidates)
        if names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise McsInputError("MCS candidates must be unique and sorted")
        ranks = sorted(candidate.elimination_rank for candidate in self.candidates)
        if ranks != list(range(1, len(self.candidates) + 1)):
            raise McsInputError("MCS elimination ranks must be complete and unique")
        if len(self.steps) != len(self.candidates) - 1:
            raise McsInputError("MCS step count must be one less than candidate count")

        by_rank = sorted(self.candidates, key=lambda candidate: candidate.elimination_rank)
        model_p_values = [candidate.mcs_p_value for candidate in by_rank]
        if model_p_values != sorted(model_p_values):
            raise McsInputError("MCS model p-values must be monotone")
        if by_rank[-1].mcs_p_value != 1.0:
            raise McsInputError("MCS singleton candidate must have p-value one")

        current = names
        running_p_value = 0.0
        for index, step in enumerate(self.steps):
            if step.current_candidates != current:
                raise McsInputError("MCS steps must form one nested candidate sequence")
            ranked_candidate = by_rank[index]
            if ranked_candidate.name != step.eliminated:
                raise McsInputError("MCS elimination order disagrees with candidate ranks")
            running_p_value = max(running_p_value, step.p_value)
            if ranked_candidate.mcs_p_value != running_p_value:
                raise McsInputError("MCS model p-value disagrees with running set p-values")
            current = tuple(name for name in current if name != step.eliminated)
        if current != (by_rank[-1].name,):
            raise McsInputError("MCS terminal candidate disagrees with the elimination path")
        if not self.surviving_candidates:
            raise McsInputError("MCS must retain at least one candidate")

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def elimination_order(self) -> tuple[str, ...]:
        return tuple(step.eliminated for step in self.steps)

    @property
    def surviving_candidates(self) -> tuple[str, ...]:
        return tuple(candidate.name for candidate in self.candidates if candidate.in_mcs)

    def candidate(self, name: str) -> McsCandidate:
        """Return one named candidate or fail on an unknown identity."""
        for candidate in self.candidates:
            if candidate.name == name:
                return candidate
        raise McsInputError(f"unknown MCS candidate {name!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": MCS_SCHEMA_VERSION,
            "method": MCS_METHOD,
            "loss": MCS_LOSS,
            "statistic": MCS_STATISTIC,
            "confidence": str(MCS_CONFIDENCE),
            "alpha": str(MCS_ALPHA),
            "block_length": self.block_length,
            "replications": self.replications,
            "seed": self.seed,
            "candidate_count": self.candidate_count,
            "observation_count": self.observation_count,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "steps": [step.to_dict() for step in self.steps],
            "elimination_order": list(self.elimination_order),
            "surviving_candidates": list(self.surviving_candidates),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> McsResult:
        try:
            if (
                isinstance(payload.get("schema"), bool)
                or payload.get("schema") != MCS_SCHEMA_VERSION
            ):
                raise McsInputError("unsupported MCS evidence schema")
            if payload.get("method") != MCS_METHOD:
                raise McsInputError("unsupported MCS method")
            if payload.get("loss") != MCS_LOSS:
                raise McsInputError("MCS loss must be negative daily net return")
            if payload.get("statistic") != MCS_STATISTIC:
                raise McsInputError("MCS evidence must use the range statistic")
            if payload.get("confidence") != str(MCS_CONFIDENCE):
                raise McsInputError("MCS confidence must be exactly 0.90")
            if payload.get("alpha") != str(MCS_ALPHA):
                raise McsInputError("MCS alpha must be exactly 0.10")
            candidates_raw = payload["candidates"]
            steps_raw = payload["steps"]
            if not isinstance(candidates_raw, list) or not all(
                isinstance(candidate, Mapping) for candidate in candidates_raw
            ):
                raise McsInputError("MCS candidates must be an object list")
            if not isinstance(steps_raw, list) or not all(
                isinstance(step, Mapping) for step in steps_raw
            ):
                raise McsInputError("MCS steps must be an object list")
            candidates = tuple(McsCandidate.from_dict(candidate) for candidate in candidates_raw)
            steps = tuple(McsStep.from_dict(step) for step in steps_raw)
            result = cls(
                candidates=candidates,
                steps=steps,
                block_length=_positive_integer(
                    payload["block_length"],
                    label="MCS block_length",
                ),
                replications=_positive_integer(
                    payload["replications"],
                    label="MCS replications",
                    minimum=2,
                ),
                seed=payload["seed"],
                observation_count=_positive_integer(
                    payload["observation_count"],
                    label="MCS observation_count",
                    minimum=MIN_OBSERVATIONS,
                ),
            )
            if not isinstance(result.seed, int) or isinstance(result.seed, bool):
                raise McsInputError("MCS seed must be an integer")
            candidate_count = _positive_integer(
                payload["candidate_count"],
                label="MCS candidate_count",
            )
        except KeyError as exc:
            raise McsInputError(f"MCS evidence is missing {exc.args[0]!r}") from exc
        if candidate_count != result.candidate_count:
            raise McsInputError("MCS candidate_count disagrees with its candidates")
        elimination_raw = payload.get("elimination_order")
        survivors_raw = payload.get("surviving_candidates")
        if (
            not isinstance(elimination_raw, list)
            or not all(isinstance(name, str) for name in elimination_raw)
            or tuple(elimination_raw) != result.elimination_order
        ):
            raise McsInputError("MCS elimination_order disagrees with its steps")
        if (
            not isinstance(survivors_raw, list)
            or not all(isinstance(name, str) for name in survivors_raw)
            or tuple(survivors_raw) != result.surviving_candidates
        ):
            raise McsInputError("MCS surviving_candidates disagree with model p-values")
        return result


def _range_decision(
    names: tuple[str, ...],
    observed_pair_scores: FloatArray,
    bootstrap_pair_scores: FloatArray,
    *,
    active: tuple[int, ...],
) -> RangeDecision:
    """Compute one range test and coherent elimination over exactly ``active``."""
    candidate_count = len(names)
    if observed_pair_scores.shape != (candidate_count, candidate_count):
        raise McsInputError("MCS observed pair scores have the wrong shape")
    if (
        bootstrap_pair_scores.ndim != 3
        or bootstrap_pair_scores.shape[1:] != (candidate_count, candidate_count)
        or len(bootstrap_pair_scores) < 2
    ):
        raise McsInputError("MCS bootstrap pair scores have the wrong shape")
    if len(active) < 2 or len(active) != len(set(active)):
        raise McsInputError("MCS range decision requires at least two unique candidates")
    if any(index < 0 or index >= candidate_count for index in active):
        raise McsInputError("MCS active candidate index is out of range")
    if not np.isfinite(observed_pair_scores).all() or not np.isfinite(bootstrap_pair_scores).all():
        raise McsInputError("MCS pair scores must be finite")

    active_array = np.asarray(active)
    observed = observed_pair_scores[np.ix_(active_array, active_array)]
    bootstrap = bootstrap_pair_scores[:, active_array][:, :, active_array]
    statistic = float(np.max(np.abs(observed)))
    bootstrap_statistics = np.max(np.abs(bootstrap), axis=(1, 2))
    p_value = _monte_carlo_p_value(bootstrap_statistics, statistic)

    elimination_scores = observed.max(axis=1)
    maximum_score = float(elimination_scores.max())
    tied_names = [
        names[active[index]]
        for index, score in enumerate(elimination_scores)
        if float(score) == maximum_score
    ]
    eliminated = min(tied_names)
    return RangeDecision(
        statistic=statistic,
        p_value=p_value,
        eliminated=eliminated,
        elimination_score=maximum_score,
    )


def _pairwise_scores(
    names: tuple[str, ...],
    losses: FloatArray,
    bootstrap_means: FloatArray,
    mean_block_length: int,
) -> tuple[FloatArray, FloatArray]:
    """Studentize observed and centered-bootstrap loss differences for every pair."""
    sample_size, candidate_count = losses.shape
    replications = len(bootstrap_means)
    observed_scores = np.zeros((candidate_count, candidate_count))
    bootstrap_scores = np.zeros((replications, candidate_count, candidate_count))
    pairs = tuple(
        (left, right)
        for left in range(candidate_count)
        for right in range(left + 1, candidate_count)
    )
    if not pairs:
        return observed_scores, bootstrap_scores

    differences = np.column_stack(
        tuple(losses[:, left] - losses[:, right] for left, right in pairs)
    )
    pair_means = differences.mean(axis=0)
    pair_variances = stationary_bootstrap_variances(differences, mean_block_length)
    centered = differences - pair_means
    variance_scale = np.maximum(1.0, np.max(centered * centered, axis=0))
    tolerance = np.finfo(np.float64).eps * variance_scale
    root_n = math.sqrt(sample_size)

    for pair_index, (left, right) in enumerate(pairs):
        variance = float(pair_variances[pair_index])
        if variance <= tolerance[pair_index]:
            if np.array_equal(losses[:, left], losses[:, right]):
                continue
            raise McsInputError(
                "MCS long-run variance is zero for unequal candidate pair "
                f"{names[left]!r}, {names[right]!r}"
            )
        standard_error_scale = math.sqrt(variance)
        observed = root_n * float(pair_means[pair_index]) / standard_error_scale
        bootstrap_pair_means = bootstrap_means[:, left] - bootstrap_means[:, right]
        bootstrap = root_n * (bootstrap_pair_means - pair_means[pair_index]) / standard_error_scale
        observed_scores[left, right] = observed
        observed_scores[right, left] = -observed
        bootstrap_scores[:, left, right] = bootstrap
        bootstrap_scores[:, right, left] = -bootstrap
    return observed_scores, bootstrap_scores


def mcs_test(
    candidate_returns: Mapping[str, npt.ArrayLike],
    *,
    mean_block_length: int,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> McsResult:
    """Compute the complete range-elimination path and exact 90% MCS membership."""
    try:
        raw_names, raw_matrix = _validated_matrix(candidate_returns)
    except SpaInputError as exc:
        raise McsInputError(str(exc).replace("SPA", "MCS")) from exc
    names = tuple(sorted(raw_names))
    order = tuple(raw_names.index(name) for name in names)
    returns = raw_matrix[:, order]
    block_length = _positive_integer(mean_block_length, label="MCS mean_block_length")
    repetitions = _positive_integer(replications, label="MCS replications", minimum=2)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise McsInputError("MCS seed must be an integer")

    observation_count = len(returns)
    losses = -returns
    indices = stationary_bootstrap_indices(
        observation_count,
        block_length,
        replications=repetitions,
        seed=seed,
    )
    bootstrap_means = np.column_stack(
        tuple(losses[indices, index].mean(axis=1) for index in range(losses.shape[1]))
    )
    observed_scores, bootstrap_scores = _pairwise_scores(
        names,
        losses,
        bootstrap_means,
        block_length,
    )

    active = tuple(range(len(names)))
    raw_steps: list[McsStep] = []
    running_p_value = 0.0
    model_p_values: dict[str, float] = {}
    elimination_ranks: dict[str, int] = {}
    while len(active) > 1:
        decision = _range_decision(
            names,
            observed_scores,
            bootstrap_scores,
            active=active,
        )
        current_names = tuple(names[index] for index in active)
        raw_steps.append(
            McsStep(
                current_candidates=current_names,
                statistic=decision.statistic,
                p_value=decision.p_value,
                eliminated=decision.eliminated,
                elimination_score=decision.elimination_score,
            )
        )
        running_p_value = max(running_p_value, decision.p_value)
        model_p_values[decision.eliminated] = running_p_value
        elimination_ranks[decision.eliminated] = len(raw_steps)
        active = tuple(index for index in active if names[index] != decision.eliminated)

    terminal = names[active[0]]
    model_p_values[terminal] = 1.0
    elimination_ranks[terminal] = len(names)
    candidates = tuple(
        McsCandidate(
            name=name,
            mean_loss=float(losses[:, index].mean()),
            elimination_rank=elimination_ranks[name],
            mcs_p_value=model_p_values[name],
        )
        for index, name in enumerate(names)
    )
    return McsResult(
        candidates=candidates,
        steps=tuple(raw_steps),
        block_length=block_length,
        replications=repetitions,
        seed=seed,
        observation_count=observation_count,
    )
