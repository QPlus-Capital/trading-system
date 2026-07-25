"""Hansen's studentized Superior Predictive Ability test for candidate families.

The test consumes the aligned daily net-return evidence persisted by P-03. Dependence is retained
by applying one P-04 stationary-bootstrap day-index path to every candidate. Hansen's consistent
recentering removes clearly inferior candidates from the least-favourable null without selecting
the best candidate before testing the family.
"""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from research.engine.candidate_returns import (
    CANDIDATE_DAILY_RETURNS,
    CANDIDATE_METADATA,
)
from research.portfolio.resample import (
    DEFAULT_REPLICATIONS,
    DEFAULT_SEED,
    SENSITIVITY_BLOCK_LENGTHS,
    select_block_length,
    stationary_bootstrap,
)

SPA_ALPHA = Decimal("0.05")
SPA_SCHEMA_VERSION = 1
BENCHMARK_RETURN = Decimal("0")
MIN_OBSERVATIONS = 3

FloatArray = npt.NDArray[np.float64]
HashPaths = Callable[[dict[str, str | Path]], dict[str, dict[str, str]]]


class SpaInputError(ValueError):
    """The family or serialized SPA evidence cannot support a fail-closed decision."""


@dataclass(frozen=True)
class CandidateFamily:
    """One common date grid and its ordered candidate daily-return streams."""

    dates: tuple[str, ...]
    returns: dict[str, FloatArray]


@dataclass(frozen=True)
class StudentizedBootstrapSample:
    """Shared paired resample and studentization inputs for family tests."""

    names: tuple[str, ...]
    means: FloatArray
    bootstrap_means: FloatArray
    variances: FloatArray
    observed_scores: FloatArray
    bootstrap_scores: FloatArray
    indices: npt.NDArray[np.int64]
    block_length: int
    replications: int
    seed: int
    observation_count: int


def _probability(value: object, *, label: str) -> float:
    if isinstance(value, bool):
        raise SpaInputError(f"{label} must be a finite probability")
    if not isinstance(value, (str, int, float, Decimal, np.integer, np.floating)):
        raise SpaInputError(f"{label} must be a finite probability")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise SpaInputError(f"{label} must be a finite probability") from exc
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise SpaInputError(f"{label} must be between zero and one")
    return result


def _positive_integer(value: object, *, label: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise SpaInputError(f"{label} must be an integer of at least {minimum}")
    result = int(value)
    if result < minimum:
        raise SpaInputError(f"{label} must be an integer of at least {minimum}")
    return result


@dataclass(frozen=True)
class SpaResult:
    """One block-length SPA result."""

    block_length: int
    statistic: float
    p_value: float
    candidate_statistics: dict[str, float] | None = None
    recentered_candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _positive_integer(self.block_length, label="SPA block_length")
        if not math.isfinite(float(self.statistic)) or self.statistic < 0.0:
            raise SpaInputError("SPA statistic must be finite and non-negative")
        _probability(self.p_value, label="SPA p_value")
        statistics = self.candidate_statistics or {}
        if any(not name for name in statistics):
            raise SpaInputError("SPA candidate names must be non-empty")
        if any(not math.isfinite(float(value)) for value in statistics.values()):
            raise SpaInputError("SPA candidate statistics must be finite")
        if len(self.recentered_candidates) != len(set(self.recentered_candidates)):
            raise SpaInputError("SPA recentered candidate names must be unique")

    @property
    def passes(self) -> bool:
        """Use an exact decimal boundary for the deployment gate."""
        return Decimal(str(self.p_value)) <= SPA_ALPHA

    def to_dict(self) -> dict[str, Any]:
        return {
            "block_length": self.block_length,
            "statistic": self.statistic,
            "p_value": self.p_value,
            "passes": self.passes,
            "candidate_statistics": dict(sorted((self.candidate_statistics or {}).items())),
            "recentered_candidates": list(self.recentered_candidates),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SpaResult:
        try:
            statistics_raw = payload.get("candidate_statistics", {})
            if not isinstance(statistics_raw, Mapping):
                raise SpaInputError("SPA candidate_statistics must be an object")
            recentered_raw = payload.get("recentered_candidates", [])
            if not isinstance(recentered_raw, list) or not all(
                isinstance(item, str) for item in recentered_raw
            ):
                raise SpaInputError("SPA recentered_candidates must be a string list")
            statistic = float(payload["statistic"])
            result = cls(
                block_length=_positive_integer(
                    payload["block_length"],
                    label="SPA block_length",
                ),
                statistic=statistic,
                p_value=_probability(payload["p_value"], label="SPA p_value"),
                candidate_statistics={
                    str(name): float(value) for name, value in statistics_raw.items()
                },
                recentered_candidates=tuple(recentered_raw),
            )
        except KeyError as exc:
            raise SpaInputError(f"SPA result is missing {exc.args[0]!r}") from exc
        recorded_pass = payload.get("passes")
        if recorded_pass is not None and (
            not isinstance(recorded_pass, bool) or recorded_pass != result.passes
        ):
            raise SpaInputError("SPA recorded pass flag disagrees with its p-value")
        return result


@dataclass(frozen=True)
class SpaAnalysis:
    """Selected block result plus the mandatory fixed-length sensitivity."""

    selected: SpaResult
    sensitivity: dict[int, SpaResult]
    replications: int
    seed: int
    candidate_count: int
    observation_count: int

    def __post_init__(self) -> None:
        _positive_integer(self.replications, label="SPA replications", minimum=2)
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            raise SpaInputError("SPA seed must be an integer")
        _positive_integer(self.candidate_count, label="SPA candidate_count")
        _positive_integer(
            self.observation_count,
            label="SPA observation_count",
            minimum=MIN_OBSERVATIONS,
        )
        if set(self.sensitivity) != set(SENSITIVITY_BLOCK_LENGTHS):
            raise SpaInputError("SPA sensitivity must contain block lengths 5, 10, 20, and 60")
        for block_length, result in self.sensitivity.items():
            if result.block_length != block_length:
                raise SpaInputError("SPA sensitivity key disagrees with result block length")

    @property
    def selected_block_length(self) -> int:
        return self.selected.block_length

    @property
    def passes(self) -> bool:
        return self.selected.passes and all(result.passes for result in self.sensitivity.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SPA_SCHEMA_VERSION,
            "method": "Hansen (2005) studentized SPA with consistent recentering",
            "benchmark_return": str(BENCHMARK_RETURN),
            "alpha": str(SPA_ALPHA),
            "tail": "one-sided positive",
            "replications": self.replications,
            "seed": self.seed,
            "candidate_count": self.candidate_count,
            "observation_count": self.observation_count,
            "selected": self.selected.to_dict(),
            "sensitivity": {
                str(block_length): self.sensitivity[block_length].to_dict()
                for block_length in SENSITIVITY_BLOCK_LENGTHS
            },
            "passes": self.passes,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> SpaAnalysis:
        try:
            if payload.get("schema") != SPA_SCHEMA_VERSION:
                raise SpaInputError("unsupported SPA evidence schema")
            if payload.get("benchmark_return") != str(BENCHMARK_RETURN):
                raise SpaInputError("SPA benchmark must be zero")
            if payload.get("alpha") != str(SPA_ALPHA):
                raise SpaInputError("SPA alpha must be exactly 0.05")
            if payload.get("tail") != "one-sided positive":
                raise SpaInputError("SPA evidence must use the positive one-sided tail")
            sensitivity_raw = payload["sensitivity"]
            if not isinstance(sensitivity_raw, Mapping):
                raise SpaInputError("SPA sensitivity must be an object")
            sensitivity = {
                int(block_length): SpaResult.from_dict(result)
                for block_length, result in sensitivity_raw.items()
                if isinstance(result, Mapping)
            }
            if len(sensitivity) != len(sensitivity_raw):
                raise SpaInputError("SPA sensitivity entries must be objects")
            selected_raw = payload["selected"]
            if not isinstance(selected_raw, Mapping):
                raise SpaInputError("SPA selected result must be an object")
            analysis = cls(
                selected=SpaResult.from_dict(selected_raw),
                sensitivity=sensitivity,
                replications=_positive_integer(
                    payload["replications"],
                    label="SPA replications",
                    minimum=2,
                ),
                seed=int(payload["seed"]),
                candidate_count=_positive_integer(
                    payload["candidate_count"],
                    label="SPA candidate_count",
                ),
                observation_count=_positive_integer(
                    payload["observation_count"],
                    label="SPA observation_count",
                    minimum=MIN_OBSERVATIONS,
                ),
            )
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, SpaInputError):
                raise
            raise SpaInputError("malformed SPA evidence") from exc
        recorded_pass = payload.get("passes")
        if not isinstance(recorded_pass, bool) or recorded_pass != analysis.passes:
            raise SpaInputError("SPA family pass flag disagrees with its p-values")
        return analysis


def _validated_matrix(
    candidate_returns: Mapping[str, npt.ArrayLike],
) -> tuple[tuple[str, ...], FloatArray]:
    if not candidate_returns:
        raise SpaInputError("SPA requires at least one candidate")
    names = tuple(candidate_returns)
    if any(not isinstance(name, str) or not name for name in names):
        raise SpaInputError("SPA candidate names must be non-empty strings")
    if len(names) != len(set(names)):
        raise SpaInputError("SPA candidate names must be unique")

    columns: list[FloatArray] = []
    sample_size: int | None = None
    for name in names:
        values = np.asarray(candidate_returns[name], dtype=np.float64)
        if values.ndim != 1:
            raise SpaInputError(f"SPA candidate {name!r} must be one-dimensional")
        if sample_size is None:
            sample_size = len(values)
        elif len(values) != sample_size:
            raise SpaInputError("SPA candidates must share one common daily grid")
        if not np.isfinite(values).all():
            raise SpaInputError(f"SPA candidate {name!r} contains a non-finite return")
        columns.append(values)
    assert sample_size is not None
    if sample_size < MIN_OBSERVATIONS:
        raise SpaInputError(f"SPA requires at least {MIN_OBSERVATIONS} daily observations")
    return names, np.column_stack(columns)


def _bootstrap_indices(
    sample_size: int,
    mean_block_length: int,
    *,
    replications: int,
    seed: int,
) -> npt.NDArray[np.int64]:
    sampled = stationary_bootstrap(
        np.arange(sample_size),
        mean_block_length,
        replications=replications,
        seed=seed,
    )
    return sampled.astype(np.int64)


def stationary_bootstrap_indices(
    sample_size: int,
    mean_block_length: int,
    *,
    replications: int,
    seed: int,
) -> npt.NDArray[np.int64]:
    """Expose P-05's P-04-backed paired day-index draw for coherent family tests."""
    return _bootstrap_indices(
        sample_size,
        mean_block_length,
        replications=replications,
        seed=seed,
    )


def _stationary_bootstrap_variances(
    matrix: FloatArray,
    mean_block_length: int,
) -> FloatArray:
    """Estimate ``Var(sqrt(n) * mean)`` with stationary-bootstrap covariance weights."""
    sample_size = len(matrix)
    demeaned = matrix - matrix.mean(axis=0)
    restart_probability = 1.0 / mean_block_length
    continuation_probability = 1.0 - restart_probability
    variances = np.sum(demeaned * demeaned, axis=0) / sample_size
    for lag in range(1, sample_size):
        weight = (1.0 - lag / sample_size) * continuation_probability**lag
        weight += (lag / sample_size) * continuation_probability ** (sample_size - lag)
        covariance = np.sum(demeaned[:-lag] * demeaned[lag:], axis=0) / sample_size
        variances += 2.0 * weight * covariance
    return variances


def stationary_bootstrap_variances(
    matrix: FloatArray,
    mean_block_length: int,
) -> FloatArray:
    """Expose P-05's stationary-bootstrap long-run variance estimator."""
    return _stationary_bootstrap_variances(matrix, mean_block_length)


def studentized_candidate_scores(
    means: FloatArray,
    bootstrap_means: FloatArray,
    variances: FloatArray,
    sample_size: int,
) -> tuple[FloatArray, FloatArray]:
    """Return observed and zero-centered bootstrap scores under the shared variance."""
    root_n = math.sqrt(sample_size)
    standard_errors = np.sqrt(variances)
    observed_scores = root_n * means / standard_errors
    bootstrap_scores = root_n * (bootstrap_means - means) / standard_errors
    return observed_scores, bootstrap_scores


def studentized_bootstrap_sample(
    candidate_returns: Mapping[str, npt.ArrayLike],
    *,
    mean_block_length: int,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> StudentizedBootstrapSample:
    """Build the shared paired draw and zero-centered studentized candidate scores."""
    names, matrix = _validated_matrix(candidate_returns)
    block_length = _positive_integer(mean_block_length, label="SPA mean_block_length")
    repetitions = _positive_integer(replications, label="SPA replications", minimum=2)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise SpaInputError("SPA seed must be an integer")

    sample_size = matrix.shape[0]
    indices = stationary_bootstrap_indices(
        sample_size,
        block_length,
        replications=repetitions,
        seed=seed,
    )
    means = matrix.mean(axis=0)
    bootstrap_means = np.column_stack(
        tuple(matrix[indices, index].mean(axis=1) for index in range(matrix.shape[1]))
    )
    variances = stationary_bootstrap_variances(matrix, block_length)
    centered = matrix - means
    variance_scale = np.maximum(1.0, np.max(centered * centered, axis=0))
    degenerate = variances <= np.finfo(np.float64).eps * variance_scale
    if np.any(degenerate):
        names_text = ", ".join(names[index] for index in np.flatnonzero(degenerate))
        raise SpaInputError(f"SPA long-run variance is zero for candidate(s): {names_text}")

    observed_scores, bootstrap_scores = studentized_candidate_scores(
        means,
        bootstrap_means,
        variances,
        sample_size,
    )
    return StudentizedBootstrapSample(
        names=names,
        means=means,
        bootstrap_means=bootstrap_means,
        variances=variances,
        observed_scores=observed_scores,
        bootstrap_scores=bootstrap_scores,
        indices=indices,
        block_length=block_length,
        replications=repetitions,
        seed=seed,
        observation_count=sample_size,
    )


def _consistent_recentering(
    means: FloatArray,
    variances: FloatArray,
    sample_size: int,
) -> tuple[FloatArray, npt.NDArray[np.bool_]]:
    """Return Hansen's sample-dependent null means and inferior-candidate mask."""
    cutoff_scale = math.sqrt(2.0 * math.log(math.log(sample_size)))
    raw_cutoffs = -(np.sqrt(variances) / math.sqrt(sample_size)) * cutoff_scale
    retain_negative = means <= raw_cutoffs
    return np.where(retain_negative, means, 0.0), retain_negative


def _studentized_spa_statistics(
    means: FloatArray,
    bootstrap_means: FloatArray,
    variances: FloatArray,
    sample_size: int,
) -> tuple[FloatArray, float, FloatArray, npt.NDArray[np.bool_]]:
    """Return candidate scores, observed maximum, bootstrap maxima, and recentering mask."""
    root_n = math.sqrt(sample_size)
    standard_errors = np.sqrt(variances)
    observed_scores = root_n * means / standard_errors
    observed_statistic = max(0.0, float(observed_scores.max()))
    recentered_means, retain_negative = _consistent_recentering(
        means,
        variances,
        sample_size,
    )
    bootstrap_null_means = bootstrap_means - means + recentered_means
    bootstrap_scores = root_n * bootstrap_null_means / standard_errors
    bootstrap_statistics = np.maximum(0.0, bootstrap_scores.max(axis=1))
    return observed_scores, observed_statistic, bootstrap_statistics, retain_negative


def _monte_carlo_p_value(
    bootstrap_statistics: FloatArray,
    observed_statistic: float,
) -> float:
    """Return the conservative finite Monte Carlo p-value, including ties."""
    exceedances = int(np.count_nonzero(bootstrap_statistics >= observed_statistic))
    return (exceedances + 1) / (len(bootstrap_statistics) + 1)


def spa_test(
    candidate_returns: Mapping[str, npt.ArrayLike],
    *,
    mean_block_length: int,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> SpaResult:
    """Compute the one-sided studentized SPA p-value for one dependence length."""
    sample = studentized_bootstrap_sample(
        candidate_returns,
        mean_block_length=mean_block_length,
        replications=replications,
        seed=seed,
    )
    observed_scores, observed_statistic, bootstrap_statistics, retain_negative = (
        _studentized_spa_statistics(
            sample.means,
            sample.bootstrap_means,
            sample.variances,
            sample.observation_count,
        )
    )
    p_value = _monte_carlo_p_value(bootstrap_statistics, observed_statistic)

    return SpaResult(
        block_length=sample.block_length,
        statistic=observed_statistic,
        p_value=p_value,
        candidate_statistics={
            name: float(observed_scores[index]) for index, name in enumerate(sample.names)
        },
        recentered_candidates=tuple(
            name for index, name in enumerate(sample.names) if retain_negative[index]
        ),
    )


def analyze_spa(
    candidate_returns: Mapping[str, npt.ArrayLike],
    *,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> SpaAnalysis:
    """Select P-04's production length and compute the mandatory fixed sensitivity."""
    names, matrix = _validated_matrix(candidate_returns)
    canonical = {name: matrix[:, index] for index, name in enumerate(names)}
    selected_block_length = select_block_length(canonical)
    by_length: dict[int, SpaResult] = {}
    for block_length in (selected_block_length, *SENSITIVITY_BLOCK_LENGTHS):
        if block_length not in by_length:
            by_length[block_length] = spa_test(
                canonical,
                mean_block_length=block_length,
                replications=replications,
                seed=seed,
            )
    return SpaAnalysis(
        selected=by_length[selected_block_length],
        sensitivity={
            block_length: by_length[block_length] for block_length in SENSITIVITY_BLOCK_LENGTHS
        },
        replications=replications,
        seed=seed,
        candidate_count=len(names),
        observation_count=len(matrix),
    )


def _metadata(directory: Path) -> Mapping[str, Any]:
    path = directory / CANDIDATE_METADATA
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SpaInputError(f"cannot read {CANDIDATE_METADATA}") from exc
    if not isinstance(payload, Mapping):
        raise SpaInputError(f"{CANDIDATE_METADATA} must contain an object")
    return payload


def _verify_daily_hash(
    directory: Path,
    metadata: Mapping[str, Any],
    hash_paths: HashPaths | None,
) -> None:
    if hash_paths is None:
        return
    artifacts = metadata.get("artifacts")
    if not isinstance(artifacts, Mapping):
        raise SpaInputError("candidate metadata has no artifact hashes")
    recorded = artifacts.get(CANDIDATE_DAILY_RETURNS)
    if not isinstance(recorded, Mapping) or not isinstance(recorded.get("sha256"), str):
        raise SpaInputError("candidate metadata has no daily-return content hash")
    actual = hash_paths({CANDIDATE_DAILY_RETURNS: directory / CANDIDATE_DAILY_RETURNS})[
        CANDIDATE_DAILY_RETURNS
    ]["sha256"]
    if recorded["sha256"] != actual:
        raise SpaInputError("candidate daily-return content hash does not match metadata")


def load_candidate_family(
    directory: Path,
    *,
    expected_candidates: set[str],
    hash_paths: HashPaths | None = None,
) -> CandidateFamily:
    """Strictly load one complete P-03 family without deriving or filling returns."""
    metadata = _metadata(directory)
    _verify_daily_hash(directory, metadata, hash_paths)
    path = directory / CANDIDATE_DAILY_RETURNS
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.reader(handle))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise SpaInputError(f"cannot read {CANDIDATE_DAILY_RETURNS}") from exc
    if not rows or len(rows[0]) < 2 or rows[0][0] != "loss_day":
        raise SpaInputError("candidate daily returns have an invalid header")
    names = tuple(rows[0][1:])
    if any(not name for name in names) or len(names) != len(set(names)):
        raise SpaInputError("candidate daily-return names must be unique and non-empty")
    if set(names) != expected_candidates:
        raise SpaInputError("candidate daily-return family does not match the formal study family")

    persisted = metadata.get("persisted_candidates")
    persisted_count = metadata.get("persisted_candidate_count")
    trial_counts = metadata.get("trial_counts")
    if (
        not isinstance(persisted, list)
        or not all(isinstance(item, str) for item in persisted)
        or tuple(persisted) != names
        or persisted_count != len(names)
        or not isinstance(trial_counts, Mapping)
        or trial_counts.get("formal") != len(names)
    ):
        raise SpaInputError("candidate metadata does not declare the complete serialized family")

    dates: list[str] = []
    values: dict[str, list[float]] = {name: [] for name in names}
    previous_day: date | None = None
    for row_number, row in enumerate(rows[1:], start=2):
        if len(row) != len(names) + 1:
            raise SpaInputError(f"candidate daily row {row_number} has the wrong width")
        try:
            current_day = date.fromisoformat(row[0])
        except ValueError as exc:
            raise SpaInputError(f"candidate daily row {row_number} has an invalid date") from exc
        if previous_day is not None and current_day != previous_day + timedelta(days=1):
            raise SpaInputError("candidate daily returns must use one consecutive common date grid")
        previous_day = current_day
        dates.append(row[0])
        for name, raw_value in zip(names, row[1:], strict=True):
            try:
                value = Decimal(raw_value)
            except InvalidOperation as exc:
                raise SpaInputError(
                    f"candidate {name!r} row {row_number} has an invalid return"
                ) from exc
            if not value.is_finite():
                raise SpaInputError(f"candidate {name!r} row {row_number} has a non-finite return")
            values[name].append(float(value))
    if len(dates) < MIN_OBSERVATIONS:
        raise SpaInputError(f"SPA requires at least {MIN_OBSERVATIONS} daily observations")
    returns = {name: np.asarray(values[name], dtype=np.float64) for name in names}
    _validated_matrix(returns)
    return CandidateFamily(dates=tuple(dates), returns=returns)
