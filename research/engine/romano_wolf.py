"""Romano-Wolf one-sided studentized max-t stepdown for candidate means.

The procedure consumes the same aligned P-03 daily net-R matrix as Hansen's SPA test and reuses
P-05's paired stationary-bootstrap draw, long-run variance, and studentization. It controls the
familywise error rate while identifying individual candidates whose mean daily net R exceeds zero.
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
    MIN_OBSERVATIONS,
    SpaInputError,
    _monte_carlo_p_value,
    studentized_bootstrap_sample,
)
from research.portfolio.resample import DEFAULT_REPLICATIONS, DEFAULT_SEED

ROMANO_WOLF_ALPHA = Decimal("0.05")
ROMANO_WOLF_SCHEMA_VERSION = 1
ROMANO_WOLF_ARTIFACT = "romano_wolf.json"
BENCHMARK_RETURN = Decimal("0")
METHOD = "Romano-Wolf (2005) one-sided studentized max-t stepdown"

FloatArray = npt.NDArray[np.float64]


class RomanoWolfInputError(ValueError):
    """The input family or serialized stepdown evidence is not decision-safe."""


def _probability(value: object, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(
        value,
        (str, int, float, Decimal, np.integer, np.floating),
    ):
        raise RomanoWolfInputError(f"{label} must be a finite probability")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise RomanoWolfInputError(f"{label} must be a finite probability") from exc
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise RomanoWolfInputError(f"{label} must be between zero and one")
    return result


def _positive_integer(value: object, *, label: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise RomanoWolfInputError(f"{label} must be an integer of at least {minimum}")
    result = int(value)
    if result < minimum:
        raise RomanoWolfInputError(f"{label} must be an integer of at least {minimum}")
    return result


@dataclass(frozen=True)
class RomanoWolfCandidate:
    """One ordered candidate hypothesis and its familywise inference."""

    rank: int
    name: str
    statistic: float
    unadjusted_p_value: float
    adjusted_p_value: float

    def __post_init__(self) -> None:
        _positive_integer(self.rank, label="Romano-Wolf rank")
        if not self.name:
            raise RomanoWolfInputError("Romano-Wolf candidate name must be non-empty")
        if not math.isfinite(float(self.statistic)):
            raise RomanoWolfInputError("Romano-Wolf statistic must be finite")
        unadjusted = _probability(
            self.unadjusted_p_value,
            label="Romano-Wolf unadjusted_p_value",
        )
        adjusted = _probability(
            self.adjusted_p_value,
            label="Romano-Wolf adjusted_p_value",
        )
        if adjusted < unadjusted:
            raise RomanoWolfInputError(
                "Romano-Wolf adjusted p-value must not be below its unadjusted p-value"
            )

    @property
    def eligible(self) -> bool:
        """Apply the exact familywise eligibility boundary."""
        return Decimal(str(self.adjusted_p_value)) <= ROMANO_WOLF_ALPHA

    def to_dict(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "candidate": self.name,
            "statistic": self.statistic,
            "unadjusted_p_value": self.unadjusted_p_value,
            "adjusted_p_value": self.adjusted_p_value,
            "eligible": self.eligible,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RomanoWolfCandidate:
        try:
            name = payload["candidate"]
            if not isinstance(name, str):
                raise RomanoWolfInputError("Romano-Wolf candidate name must be a string")
            candidate = cls(
                rank=_positive_integer(payload["rank"], label="Romano-Wolf rank"),
                name=name,
                statistic=float(payload["statistic"]),
                unadjusted_p_value=_probability(
                    payload["unadjusted_p_value"],
                    label="Romano-Wolf unadjusted_p_value",
                ),
                adjusted_p_value=_probability(
                    payload["adjusted_p_value"],
                    label="Romano-Wolf adjusted_p_value",
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, RomanoWolfInputError):
                raise
            raise RomanoWolfInputError("malformed Romano-Wolf candidate evidence") from exc
        recorded_eligible = payload.get("eligible")
        if not isinstance(recorded_eligible, bool) or recorded_eligible != candidate.eligible:
            raise RomanoWolfInputError(
                "Romano-Wolf recorded eligibility disagrees with adjusted p-value"
            )
        return candidate


@dataclass(frozen=True)
class RomanoWolfAnalysis:
    """Validated ordered stepdown evidence for one candidate family."""

    candidates: tuple[RomanoWolfCandidate, ...]
    block_length: int
    replications: int
    seed: int
    observation_count: int

    def __post_init__(self) -> None:
        _positive_integer(self.block_length, label="Romano-Wolf block_length")
        _positive_integer(
            self.replications,
            label="Romano-Wolf replications",
            minimum=2,
        )
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise RomanoWolfInputError("Romano-Wolf seed must be an integer")
        _positive_integer(
            self.observation_count,
            label="Romano-Wolf observation_count",
            minimum=MIN_OBSERVATIONS,
        )
        if not self.candidates:
            raise RomanoWolfInputError("Romano-Wolf evidence must contain candidates")
        names = [candidate.name for candidate in self.candidates]
        if len(names) != len(set(names)):
            raise RomanoWolfInputError("Romano-Wolf candidate names must be unique")
        for expected_rank, candidate in enumerate(self.candidates, start=1):
            if candidate.rank != expected_rank:
                raise RomanoWolfInputError("Romano-Wolf ranks must be consecutive from one")
        expected_order = sorted(
            self.candidates,
            key=lambda candidate: (-candidate.statistic, candidate.name),
        )
        if list(self.candidates) != expected_order:
            raise RomanoWolfInputError(
                "Romano-Wolf candidates must be ordered by statistic then name"
            )
        adjusted = [candidate.adjusted_p_value for candidate in self.candidates]
        if adjusted != sorted(adjusted):
            raise RomanoWolfInputError("Romano-Wolf adjusted p-values must be monotone")

    @property
    def eligible_candidates(self) -> tuple[str, ...]:
        return tuple(candidate.name for candidate in self.candidates if candidate.eligible)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": ROMANO_WOLF_SCHEMA_VERSION,
            "method": METHOD,
            "benchmark_return": str(BENCHMARK_RETURN),
            "alpha": str(ROMANO_WOLF_ALPHA),
            "tail": "one-sided positive",
            "block_length": self.block_length,
            "replications": self.replications,
            "seed": self.seed,
            "candidate_count": len(self.candidates),
            "observation_count": self.observation_count,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "eligible_candidates": list(self.eligible_candidates),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> RomanoWolfAnalysis:
        try:
            if payload.get("schema") != ROMANO_WOLF_SCHEMA_VERSION:
                raise RomanoWolfInputError("unsupported Romano-Wolf evidence schema")
            if payload.get("method") != METHOD:
                raise RomanoWolfInputError("unsupported Romano-Wolf method")
            if payload.get("benchmark_return") != str(BENCHMARK_RETURN):
                raise RomanoWolfInputError("Romano-Wolf benchmark must be zero")
            if payload.get("alpha") != str(ROMANO_WOLF_ALPHA):
                raise RomanoWolfInputError("Romano-Wolf alpha must be exactly 0.05")
            if payload.get("tail") != "one-sided positive":
                raise RomanoWolfInputError("Romano-Wolf evidence must use the positive tail")
            raw_candidates = payload["candidates"]
            if not isinstance(raw_candidates, list) or not all(
                isinstance(candidate, Mapping) for candidate in raw_candidates
            ):
                raise RomanoWolfInputError("Romano-Wolf candidates must be a list of objects")
            seed = payload["seed"]
            if isinstance(seed, bool) or not isinstance(seed, int):
                raise RomanoWolfInputError("Romano-Wolf seed must be an integer")
            candidates = tuple(
                RomanoWolfCandidate.from_dict(candidate) for candidate in raw_candidates
            )
            analysis = cls(
                candidates=candidates,
                block_length=_positive_integer(
                    payload["block_length"],
                    label="Romano-Wolf block_length",
                ),
                replications=_positive_integer(
                    payload["replications"],
                    label="Romano-Wolf replications",
                    minimum=2,
                ),
                seed=seed,
                observation_count=_positive_integer(
                    payload["observation_count"],
                    label="Romano-Wolf observation_count",
                    minimum=MIN_OBSERVATIONS,
                ),
            )
            candidate_count = _positive_integer(
                payload["candidate_count"],
                label="Romano-Wolf candidate_count",
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, RomanoWolfInputError):
                raise
            raise RomanoWolfInputError("malformed Romano-Wolf evidence") from exc
        if candidate_count != len(analysis.candidates):
            raise RomanoWolfInputError("Romano-Wolf candidate count disagrees with evidence")
        recorded_eligible = payload.get("eligible_candidates")
        if not isinstance(recorded_eligible, list) or recorded_eligible != list(
            analysis.eligible_candidates
        ):
            raise RomanoWolfInputError(
                "Romano-Wolf eligible-candidate list disagrees with adjusted p-values"
            )
        return analysis


def _stepdown_adjusted_p_values(
    ordered_statistics: FloatArray,
    ordered_bootstrap_scores: FloatArray,
) -> tuple[FloatArray, FloatArray]:
    """Return raw and monotone adjusted p-values over each remaining hypothesis set."""
    if ordered_statistics.ndim != 1 or ordered_bootstrap_scores.ndim != 2:
        raise RomanoWolfInputError("Romano-Wolf stepdown inputs have invalid dimensions")
    if ordered_bootstrap_scores.shape[1] != len(ordered_statistics):
        raise RomanoWolfInputError("Romano-Wolf stepdown candidate dimensions disagree")
    if len(ordered_statistics) == 0 or len(ordered_bootstrap_scores) < 2:
        raise RomanoWolfInputError("Romano-Wolf stepdown input is empty")
    if not np.isfinite(ordered_statistics).all() or not np.isfinite(ordered_bootstrap_scores).all():
        raise RomanoWolfInputError("Romano-Wolf stepdown input must be finite")

    return _stepdown_p_values_from_ordered_scores(
        ordered_statistics,
        ordered_bootstrap_scores,
    )


def _stepdown_p_values_from_ordered_scores(
    ordered_statistics: FloatArray,
    ordered_bootstrap_scores: FloatArray,
) -> tuple[FloatArray, FloatArray]:
    """Calculate remaining-family raw p-values and their monotone stepdown envelope."""
    raw = np.empty(len(ordered_statistics))
    adjusted = np.empty(len(ordered_statistics))
    previous = 0.0
    for rank in range(len(ordered_statistics)):
        remaining_maximum = ordered_bootstrap_scores[:, rank:].max(axis=1)
        raw[rank] = _monte_carlo_p_value(
            remaining_maximum,
            float(ordered_statistics[rank]),
        )
        previous = max(previous, float(raw[rank]))
        adjusted[rank] = previous
    return raw, adjusted


def romano_wolf_test(
    candidate_returns: Mapping[str, npt.ArrayLike],
    *,
    mean_block_length: int,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> RomanoWolfAnalysis:
    """Compute one-sided studentized familywise-adjusted candidate p-values."""
    try:
        sample = studentized_bootstrap_sample(
            candidate_returns,
            mean_block_length=mean_block_length,
            replications=replications,
            seed=seed,
        )
    except SpaInputError as exc:
        raise RomanoWolfInputError(str(exc)) from exc

    order = tuple(
        sorted(
            range(len(sample.names)),
            key=lambda index: (-float(sample.observed_scores[index]), sample.names[index]),
        )
    )
    ordered_indices = np.asarray(order)
    observed = sample.observed_scores[ordered_indices]
    bootstrap_scores = sample.bootstrap_scores[:, ordered_indices]
    _raw_step, adjusted = _stepdown_adjusted_p_values(observed, bootstrap_scores)
    unadjusted = np.asarray(
        [
            _monte_carlo_p_value(bootstrap_scores[:, rank], float(observed[rank]))
            for rank in range(len(order))
        ]
    )
    candidates = tuple(
        RomanoWolfCandidate(
            rank=rank + 1,
            name=sample.names[original_index],
            statistic=float(observed[rank]),
            unadjusted_p_value=float(unadjusted[rank]),
            adjusted_p_value=float(adjusted[rank]),
        )
        for rank, original_index in enumerate(order)
    )
    return RomanoWolfAnalysis(
        candidates=candidates,
        block_length=sample.block_length,
        replications=sample.replications,
        seed=sample.seed,
        observation_count=sample.observation_count,
    )
