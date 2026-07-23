"""Synthetic-null calibration for the stationary bootstrap."""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import numpy.typing as npt
import pytest
from research.portfolio.resample import stationary_bootstrap

FloatArray = npt.NDArray[np.float64]
CALIBRATION_EXPERIMENTS = 1_000
CALIBRATION_REPLICATIONS = 299


def _ar1(phi: float, innovations: FloatArray) -> FloatArray:
    values = np.empty_like(innovations)
    values[0] = innovations[0] / math.sqrt(1.0 - phi**2)
    for index in range(1, len(values)):
        values[index] = phi * values[index - 1] + innovations[index]
    return values


def _ordinary_standard_error(values: FloatArray) -> FloatArray:
    return np.asarray(values.std(axis=-1, ddof=1) / math.sqrt(values.shape[-1]))


def _bartlett_hac_standard_error(values: FloatArray, max_lag: int = 10) -> FloatArray:
    centered = values - values.mean(axis=-1, keepdims=True)
    sample_size = values.shape[-1]
    long_run_variance = np.mean(centered * centered, axis=-1)
    for lag in range(1, max_lag + 1):
        weight = 1.0 - lag / (max_lag + 1.0)
        autocovariance = np.mean(centered[..., lag:] * centered[..., :-lag], axis=-1)
        long_run_variance = long_run_variance + 2.0 * weight * autocovariance
    return np.asarray(np.sqrt(np.maximum(long_run_variance, 1e-15) / sample_size))


def _percentile_t_covers_zero(
    sample: FloatArray,
    bootstrap_samples: FloatArray,
    standard_error: Callable[[FloatArray], FloatArray],
) -> bool:
    sample_mean = float(sample.mean())
    sample_error = float(standard_error(sample))
    bootstrap_errors = standard_error(bootstrap_samples)
    pivots = (bootstrap_samples.mean(axis=1) - sample_mean) / bootstrap_errors
    low_quantile, high_quantile = np.quantile(pivots, [0.025, 0.975])
    lower = sample_mean - high_quantile * sample_error
    upper = sample_mean - low_quantile * sample_error
    return bool(lower <= 0.0 <= upper)


def test_iid_gaussian_mean_interval_has_nominal_coverage() -> None:
    sample_rng = np.random.default_rng(11_008)
    seed_rng = np.random.default_rng(11_009)
    covered = 0
    for _ in range(CALIBRATION_EXPERIMENTS):
        sample = sample_rng.normal(size=128)
        bootstrap = stationary_bootstrap(
            sample,
            1,
            replications=CALIBRATION_REPLICATIONS,
            seed=int(seed_rng.integers(0, np.iinfo(np.int64).max)),
        )
        covered += _percentile_t_covers_zero(sample, bootstrap, _ordinary_standard_error)

    coverage = covered / CALIBRATION_EXPERIMENTS
    assert coverage == pytest.approx(0.95, abs=0.015)


def test_stationary_ar1_coverage_and_iid_negative_control() -> None:
    sample_rng = np.random.default_rng(33)
    seed_rng = np.random.default_rng(34)
    iid_rng = np.random.default_rng(35)
    stationary_covered = 0
    iid_covered = 0
    for _ in range(CALIBRATION_EXPERIMENTS):
        sample = _ar1(0.5, sample_rng.normal(size=512))
        stationary_samples = stationary_bootstrap(
            sample,
            10,
            replications=CALIBRATION_REPLICATIONS,
            seed=int(seed_rng.integers(0, np.iinfo(np.int64).max)),
        )
        stationary_covered += _percentile_t_covers_zero(
            sample, stationary_samples, _bartlett_hac_standard_error
        )

        iid_indices = iid_rng.integers(0, len(sample), size=(CALIBRATION_REPLICATIONS, len(sample)))
        iid_samples = sample[iid_indices]
        iid_covered += _percentile_t_covers_zero(sample, iid_samples, _ordinary_standard_error)

    stationary_coverage = stationary_covered / CALIBRATION_EXPERIMENTS
    iid_coverage = iid_covered / CALIBRATION_EXPERIMENTS
    assert stationary_coverage == pytest.approx(0.95, abs=0.02)
    assert iid_coverage < 0.90
    assert stationary_coverage - iid_coverage > 0.10
