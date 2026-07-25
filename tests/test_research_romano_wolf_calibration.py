"""Deterministic synthetic-null calibration for Romano-Wolf familywise error."""

from __future__ import annotations

import numpy as np
from research.engine.romano_wolf import romano_wolf_test


def test_romano_wolf_global_null_controls_familywise_error() -> None:
    outer = np.random.default_rng(20260725)
    rejected = 0
    family_count = 200
    correlation = 0.919
    for family_index in range(family_count):
        common = outer.normal(0.0, 1.0, 500)
        independent = outer.normal(0.0, 1.0, (500, 36))
        matrix = np.sqrt(correlation) * common[:, None]
        matrix = matrix + np.sqrt(1.0 - correlation) * independent
        returns = {f"candidate_{index:02d}": matrix[:, index] for index in range(matrix.shape[1])}
        result = romano_wolf_test(
            returns,
            mean_block_length=5,
            replications=249,
            seed=20260800 + family_index,
        )
        rejected += bool(result.eligible_candidates)

    rejection_rate = rejected / family_count
    assert 0.02 <= rejection_rate <= 0.08
