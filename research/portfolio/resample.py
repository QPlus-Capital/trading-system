"""Pure dependent-bootstrap utilities for aligned daily net-return series.

The block-length estimator implements the Politis-White (2004) flat-top plug-in for the
stationary bootstrap with the Patton-Politis-White (2009) correction ``D_SB = 2*g(0)^2``. The
resampler implements the Politis-Romano (1994) stationary bootstrap: geometrically distributed
block lengths, uniform starts, and circular continuation. Callers remain responsible for building
the common daily grid, including zero-return days.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np
import numpy.typing as npt

DEFAULT_SEED = 20260719
DEFAULT_REPLICATIONS = 10_000
SENSITIVITY_BLOCK_LENGTHS = (5, 10, 20, 60)

FloatArray = npt.NDArray[np.float64]


def _validated_returns(daily_returns: npt.ArrayLike, *, label: str) -> FloatArray:
    values = np.asarray(daily_returns, dtype=np.float64)
    if values.ndim != 1:
        raise ValueError(f"{label} must be one-dimensional")
    if values.size == 0:
        raise ValueError(f"{label} must be non-empty")
    if not np.isfinite(values).all():
        raise ValueError(f"{label} must contain only finite values")
    return values


def _flat_top_weights(bandwidth: int) -> FloatArray:
    lags = np.arange(1, bandwidth + 1, dtype=np.float64)
    scaled = lags / bandwidth
    return np.where(scaled <= 0.5, 1.0, 2.0 * (1.0 - scaled))


def politis_white_block_length(daily_returns: npt.ArrayLike) -> float:
    """Estimate the corrected optimal mean block length for one daily return stream.

    Autocovariances use the paper's biased full-sample denominator. The automatic bandwidth uses
    the first run of insignificant autocorrelations and the trapezoidal flat-top lag window. No
    upper cap is applied here; :func:`select_block_length` owns the explicit fail-closed ``T/10``
    policy for production candidate sets.
    """
    values = _validated_returns(daily_returns, label="daily_returns")
    sample_size = len(values)
    centered = values - values.mean()
    variance_scale = max(1.0, float(np.max(centered * centered)))
    gamma_zero = float(centered @ centered / sample_size)
    if gamma_zero <= np.finfo(np.float64).eps * variance_scale:
        return 1.0

    consecutive_lags = max(5, int(math.log10(sample_size)))
    max_bandwidth = min(
        math.ceil(math.sqrt(sample_size)) + consecutive_lags,
        sample_size - 1,
    )
    threshold = 2.0 * math.sqrt(math.log10(sample_size) / sample_size)
    autocovariances = np.empty(max_bandwidth + 1, dtype=np.float64)
    autocovariances[0] = gamma_zero
    for lag in range(1, max_bandwidth + 1):
        autocovariances[lag] = centered[lag:] @ centered[:-lag] / sample_size
    autocorrelations = autocovariances / gamma_zero

    first_negligible_lag: int | None = None
    final_start = max_bandwidth - consecutive_lags + 1
    for lag in range(1, final_start + 1):
        window = autocorrelations[lag : lag + consecutive_lags]
        if np.all(np.abs(window) < threshold):
            first_negligible_lag = lag
            break

    bandwidth = (
        max_bandwidth
        if first_negligible_lag is None
        else min(2 * max(first_negligible_lag, 1), max_bandwidth)
    )
    weights = _flat_top_weights(bandwidth)
    lags = np.arange(1, bandwidth + 1, dtype=np.float64)
    weighted_autocovariances = weights * autocovariances[1 : bandwidth + 1]
    g_hat = float(2.0 * np.sum(lags * weighted_autocovariances))
    long_run_variance = float(gamma_zero + 2.0 * np.sum(weighted_autocovariances))

    tolerance = np.finfo(np.float64).eps * variance_scale
    if abs(long_run_variance) <= tolerance:
        return 1.0 if abs(g_hat) <= tolerance else math.inf
    corrected_d_sb = 2.0 * long_run_variance**2
    estimate = np.cbrt((2.0 * g_hat**2 / corrected_d_sb) * sample_size)
    return max(1.0, float(estimate))


def select_block_length(candidate_returns: Mapping[str, npt.ArrayLike]) -> int:
    """Select ``ceil(max(candidate estimates))`` and reject insufficient effective history.

    Candidate arrays must already share the common daily grid including zero days. An estimate
    above one tenth of that history raises instead of being clamped, and the diagnostic identifies
    the candidate that determined the rejected production length.
    """
    if not candidate_returns:
        raise ValueError("candidate_returns must contain at least one candidate")

    estimates: list[tuple[str, float]] = []
    sample_size: int | None = None
    for candidate, daily_returns in candidate_returns.items():
        values = _validated_returns(
            daily_returns,
            label=f"candidate {candidate!r} daily_returns",
        )
        if sample_size is None:
            sample_size = len(values)
        elif len(values) != sample_size:
            raise ValueError("candidate returns must share one common daily grid")
        estimates.append((candidate, politis_white_block_length(values)))

    assert sample_size is not None
    limiting_candidate, maximum_estimate = max(estimates, key=lambda item: item[1])
    if math.isfinite(maximum_estimate):
        block_length: int | float = max(1, math.ceil(maximum_estimate))
    else:
        block_length = math.inf
    limit = sample_size // 10
    if block_length > limit:
        label = "inf" if not math.isfinite(block_length) else str(int(block_length))
        raise ValueError(
            "Politis-White block length rejected: "
            f"L={label} exceeds floor(T/10)={limit} for candidate {limiting_candidate!r} "
            f"(T={sample_size})"
        )
    return int(block_length)


def _validated_replications(replications: int) -> int:
    if isinstance(replications, bool) or not isinstance(replications, (int, np.integer)):
        raise ValueError("replications must be a positive integer")
    if replications <= 0:
        raise ValueError("replications must be a positive integer")
    return int(replications)


def _validated_mean_block_length(mean_block_length: float) -> float:
    if isinstance(mean_block_length, bool) or not isinstance(
        mean_block_length, (int, float, np.integer, np.floating)
    ):
        raise ValueError("mean_block_length must be finite and at least 1")
    value = float(mean_block_length)
    if not math.isfinite(value) or value < 1.0:
        raise ValueError("mean_block_length must be finite and at least 1")
    return value


def stationary_bootstrap(
    daily_returns: npt.ArrayLike,
    mean_block_length: float,
    *,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> FloatArray:
    """Return Politis-Romano stationary-bootstrap samples with shape ``(replications, T)``.

    Each path starts at a uniform source index. At every subsequent observation a new uniform
    block starts with probability ``1 / mean_block_length``; otherwise the prior source index
    advances by one with circular wrapping. Consequently block lengths are geometric with the
    requested mean and every source observation has equal marginal inclusion probability.
    """
    values = _validated_returns(daily_returns, label="daily_returns")
    block_length = _validated_mean_block_length(mean_block_length)
    repetitions = _validated_replications(replications)
    generator = np.random.default_rng(seed)
    sample_size = len(values)
    indices = np.empty((repetitions, sample_size), dtype=np.int64)
    indices[:, 0] = generator.integers(0, sample_size, size=repetitions)
    restart_probability = 1.0 / block_length

    for position in range(1, sample_size):
        restart = generator.random(repetitions) < restart_probability
        fresh_start = generator.integers(sample_size, size=repetitions)
        continuation = (indices[:, position - 1] + 1) % sample_size
        indices[:, position] = np.where(restart, fresh_start, continuation)
    return values[indices]


def stationary_bootstrap_sensitivity(
    daily_returns: npt.ArrayLike,
    *,
    replications: int = DEFAULT_REPLICATIONS,
    seed: int = DEFAULT_SEED,
) -> dict[int, FloatArray]:
    """Return paired stationary resamples at the fixed 5/10/20/60-day sensitivity lengths."""
    return {
        block_length: stationary_bootstrap(
            daily_returns,
            block_length,
            replications=replications,
            seed=seed,
        )
        for block_length in SENSITIVITY_BLOCK_LENGTHS
    }
