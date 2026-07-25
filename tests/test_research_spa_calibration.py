"""Synthetic-null calibration for Hansen's SPA test.

These outer simulations run in normal CI. They are intentionally separate from the fast semantic
suite that Mutmut repeats once per generated mutant.
"""

from __future__ import annotations

import math

import numpy as np
from research.engine.spa import spa_test


def _assert_null_calibration(p_values: np.ndarray) -> None:
    rejection_rate = float(np.mean(p_values <= 0.05))
    assert 0.02 <= rejection_rate <= 0.08
    assert 0.42 <= float(p_values.mean()) <= 0.58
    q25, q75 = np.quantile(p_values, [0.25, 0.75])
    assert 0.15 <= q25 <= 0.35
    assert 0.65 <= q75 <= 0.85


def test_spa_null_calibration_is_uniform_and_rejects_near_five_percent() -> None:
    p_values: list[float] = []
    for index in range(200):
        generator = np.random.default_rng(10_000 + index)
        common = generator.normal(0.0, 1.0, 500)
        family = {
            f"candidate_{candidate}": math.sqrt(0.919) * common
            + math.sqrt(1.0 - 0.919) * generator.normal(0.0, 1.0, 500)
            for candidate in range(36)
        }
        p_values.append(
            spa_test(
                family,
                mean_block_length=5,
                replications=249,
                seed=20_000 + index,
            ).p_value
        )

    _assert_null_calibration(np.asarray(p_values))


def test_spa_independent_null_calibration_is_not_anti_conservative() -> None:
    p_values: list[float] = []
    for index in range(400):
        generator = np.random.default_rng(10_000 + index)
        family = {
            f"candidate_{candidate}": generator.normal(0.0, 1.0, 500) for candidate in range(8)
        }
        p_values.append(
            spa_test(
                family,
                mean_block_length=5,
                replications=249,
                seed=20_000 + index,
            ).p_value
        )

    _assert_null_calibration(np.asarray(p_values))
