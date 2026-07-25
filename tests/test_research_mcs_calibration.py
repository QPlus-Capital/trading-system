"""Deterministic synthetic calibration for the 90% Model Confidence Set."""

from __future__ import annotations

import math

import numpy as np
from research.engine.mcs import mcs_test


def _correlated_returns(
    generator: np.random.Generator,
    *,
    means: np.ndarray,
    days: int,
    correlation: float = 0.919,
) -> dict[str, np.ndarray]:
    common = generator.normal(0.0, math.sqrt(correlation), days)
    residual_scale = math.sqrt(1.0 - correlation)
    return {
        f"candidate_{index}": common + generator.normal(0.0, residual_scale, days) + means[index]
        for index in range(len(means))
    }


def test_identical_distribution_candidates_remain_in_the_mcs() -> None:
    returns = _correlated_returns(
        np.random.default_rng(20260701),
        means=np.zeros(8),
        days=500,
    )

    result = mcs_test(
        returns,
        mean_block_length=5,
        replications=499,
        seed=20260702,
    )

    assert len(result.surviving_candidates) >= 7


def test_true_best_coverage_is_at_least_ninety_percent() -> None:
    retained = 0
    experiments = 100
    means = np.asarray([0.08, 0.0, -0.01, -0.02, -0.03, -0.04])
    for experiment in range(experiments):
        returns = _correlated_returns(
            np.random.default_rng(30_000 + experiment),
            means=means,
            days=300,
        )
        result = mcs_test(
            returns,
            mean_block_length=5,
            replications=199,
            seed=40_000 + experiment,
        )
        retained += "candidate_0" in result.surviving_candidates

    assert retained >= 90
