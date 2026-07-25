"""Behavioural guards for one-sided Romano-Wolf max-t stepdown."""

from __future__ import annotations

import math
from decimal import Decimal

import numpy as np
import pytest
from research.engine import spa
from research.engine.romano_wolf import (
    ROMANO_WOLF_ALPHA,
    RomanoWolfAnalysis,
    RomanoWolfInputError,
    _stepdown_adjusted_p_values,
    romano_wolf_test,
)
from research.engine.spa import _monte_carlo_p_value, studentized_bootstrap_sample


def _symmetric_noise(days: int, candidates: int, *, seed: int) -> dict[str, np.ndarray]:
    generator = np.random.default_rng(seed)
    half = generator.normal(0.0, 1.0, (days // 2, candidates))
    matrix = np.vstack((half, -half))
    return {f"candidate_{index:02d}": matrix[:, index] for index in range(candidates)}


def test_adjusted_p_values_are_monotone_in_statistic_order() -> None:
    returns = {
        name: values + shift
        for (name, values), shift in zip(
            _symmetric_noise(240, 6, seed=101).items(),
            (0.20, 0.14, 0.08, 0.02, -0.02, -0.08),
            strict=True,
        )
    }

    result = romano_wolf_test(
        returns,
        mean_block_length=5,
        replications=499,
        seed=102,
    )

    statistics = [candidate.statistic for candidate in result.candidates]
    adjusted = [candidate.adjusted_p_value for candidate in result.candidates]
    assert statistics == sorted(statistics, reverse=True)
    assert adjusted == sorted(adjusted)


def test_equal_statistics_use_candidate_name_as_the_deterministic_tie_break() -> None:
    values = np.random.default_rng(151).normal(0.1, 1.0, 180)

    result = romano_wolf_test(
        {"z_candidate": values, "a_candidate": values.copy()},
        mean_block_length=5,
        replications=99,
        seed=152,
    )

    assert [candidate.name for candidate in result.candidates] == [
        "a_candidate",
        "z_candidate",
    ]


def test_stepdown_kernel_uses_only_the_remaining_candidates() -> None:
    observed = np.asarray([3.0, 2.0, 1.0])
    bootstrap_scores = np.asarray(
        [
            [4.0, 0.0, 0.0],
            [0.0, 2.5, 0.0],
            [0.0, 0.0, 1.5],
            [0.0, 0.0, 0.0],
        ]
    )

    raw, adjusted = _stepdown_adjusted_p_values(observed, bootstrap_scores)

    # Rank 1 sees all columns (one exceedance); rank 2 excludes column 1 (one exceedance);
    # rank 3 sees only column 3 (one exceedance). The finite add-one p-value is 2/5.
    np.testing.assert_array_equal(raw, [0.4, 0.4, 0.4])
    np.testing.assert_array_equal(adjusted, [0.4, 0.4, 0.4])


def test_adjusted_p_values_dominate_unadjusted_p_values() -> None:
    result = romano_wolf_test(
        _symmetric_noise(240, 8, seed=201),
        mean_block_length=5,
        replications=499,
        seed=202,
    )

    for candidate in result.candidates:
        assert candidate.adjusted_p_value >= candidate.unadjusted_p_value


def test_one_strong_candidate_is_the_only_eligible_hypothesis() -> None:
    returns = _symmetric_noise(300, 7, seed=301)
    returns["strong_edge"] = returns.pop("candidate_00") + 0.35

    result = romano_wolf_test(
        returns,
        mean_block_length=5,
        replications=999,
        seed=302,
    )

    assert result.eligible_candidates == ("strong_edge",)
    by_name = {candidate.name: candidate for candidate in result.candidates}
    assert by_name["strong_edge"].adjusted_p_value <= 0.05
    assert all(
        not candidate.eligible for name, candidate in by_name.items() if name != "strong_edge"
    )


def test_stepdown_finds_two_correlated_edges_that_single_step_misses() -> None:
    generator = np.random.default_rng(401)
    common = generator.normal(0.0, 1.0, 360)
    first = common + generator.normal(0.0, 0.55, 360) + 0.24
    second = common + generator.normal(0.0, 0.55, 360) + 0.18
    returns = {"strong": first, "moderate": second}

    result = romano_wolf_test(
        returns,
        mean_block_length=5,
        replications=1_999,
        seed=402,
    )
    sample = studentized_bootstrap_sample(
        returns,
        mean_block_length=5,
        replications=1_999,
        seed=402,
    )
    by_name = {candidate.name: candidate for candidate in result.candidates}
    moderate_index = sample.names.index("moderate")
    single_step_p = _monte_carlo_p_value(
        sample.bootstrap_scores.max(axis=1),
        sample.observed_scores[moderate_index],
    )

    assert np.corrcoef(first, second)[0, 1] > 0.5
    assert single_step_p > 0.05
    assert by_name["strong"].eligible
    assert by_name["moderate"].eligible


def test_romano_wolf_is_bit_for_bit_deterministic() -> None:
    returns = _symmetric_noise(240, 5, seed=501)
    returns["candidate_00"] += 0.18

    first = romano_wolf_test(
        returns,
        mean_block_length=10,
        replications=499,
        seed=502,
    )
    second = romano_wolf_test(
        returns,
        mean_block_length=10,
        replications=499,
        seed=502,
    )

    assert first == second
    assert first.to_dict() == second.to_dict()


def test_spa_and_romano_wolf_share_the_selected_bootstrap_draw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    returns = _symmetric_noise(180, 4, seed=601)
    draws: list[np.ndarray] = []
    original = spa.stationary_bootstrap_indices

    def capture_draw(
        sample_size: int,
        mean_block_length: int,
        *,
        replications: int,
        seed: int,
    ) -> np.ndarray:
        indices = original(
            sample_size,
            mean_block_length,
            replications=replications,
            seed=seed,
        )
        draws.append(indices.copy())
        return indices

    monkeypatch.setattr(spa, "stationary_bootstrap_indices", capture_draw)
    spa.spa_test(
        returns,
        mean_block_length=7,
        replications=99,
        seed=602,
    )
    result = romano_wolf_test(
        returns,
        mean_block_length=7,
        replications=99,
        seed=602,
    )

    assert len(draws) == 2
    np.testing.assert_array_equal(draws[0], draws[1])
    assert result.block_length == 7


def test_exact_decimal_boundary_controls_eligibility() -> None:
    payload = {
        "schema": 1,
        "method": "Romano-Wolf (2005) one-sided studentized max-t stepdown",
        "benchmark_return": "0",
        "alpha": "0.05",
        "tail": "one-sided positive",
        "block_length": 5,
        "replications": 10_000,
        "seed": 20260719,
        "candidate_count": 2,
        "observation_count": 300,
        "eligible_candidates": ["at_boundary"],
        "candidates": [
            {
                "rank": 1,
                "candidate": "at_boundary",
                "statistic": 2.0,
                "unadjusted_p_value": 0.01,
                "adjusted_p_value": 0.05,
                "eligible": True,
            },
            {
                "rank": 2,
                "candidate": "above_boundary",
                "statistic": 1.0,
                "unadjusted_p_value": 0.02,
                "adjusted_p_value": 0.0500000001,
                "eligible": False,
            },
        ],
    }

    result = RomanoWolfAnalysis.from_dict(payload)

    assert Decimal("0.05") == ROMANO_WOLF_ALPHA
    assert result.candidates[0].eligible
    assert not result.candidates[1].eligible


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("adjusted_p_value", math.nan),
        ("adjusted_p_value", -0.1),
        ("adjusted_p_value", 1.1),
        ("eligible", None),
    ),
)
def test_serialized_evidence_rejects_invalid_probability_or_flag(
    field: str,
    value: object,
) -> None:
    result = romano_wolf_test(
        _symmetric_noise(120, 3, seed=701),
        mean_block_length=5,
        replications=99,
        seed=702,
    )
    payload = result.to_dict()
    payload["candidates"][0][field] = (
        not payload["candidates"][0][field] if field == "eligible" else value
    )

    with pytest.raises(RomanoWolfInputError):
        RomanoWolfAnalysis.from_dict(payload)


def test_serialized_evidence_rejects_nonmonotone_or_underadjusted_p_values() -> None:
    result = romano_wolf_test(
        _symmetric_noise(120, 3, seed=801),
        mean_block_length=5,
        replications=99,
        seed=802,
    )

    nonmonotone = result.to_dict()
    nonmonotone["candidates"][0]["adjusted_p_value"] = 0.9
    with pytest.raises(RomanoWolfInputError):
        RomanoWolfAnalysis.from_dict(nonmonotone)

    underadjusted = result.to_dict()
    underadjusted["candidates"][-1]["unadjusted_p_value"] = 1.0
    underadjusted["candidates"][-1]["adjusted_p_value"] = 0.9
    with pytest.raises(RomanoWolfInputError):
        RomanoWolfAnalysis.from_dict(underadjusted)


@pytest.mark.parametrize(
    "damage",
    ("rank", "duplicate", "count", "order", "eligible_list", "seed_type"),
)
def test_serialized_evidence_rejects_identity_and_order_corruption(damage: str) -> None:
    result = romano_wolf_test(
        _symmetric_noise(120, 3, seed=901),
        mean_block_length=5,
        replications=99,
        seed=902,
    )
    payload = result.to_dict()
    if damage == "rank":
        payload["candidates"][0]["rank"] = 2
    elif damage == "duplicate":
        payload["candidates"][1]["candidate"] = payload["candidates"][0]["candidate"]
    elif damage == "count":
        payload["candidate_count"] = 2
    elif damage == "order":
        payload["candidates"][0], payload["candidates"][1] = (
            payload["candidates"][1],
            payload["candidates"][0],
        )
    elif damage == "eligible_list":
        payload["eligible_candidates"] = ["not-a-candidate"]
    else:
        payload["seed"] = "902"

    with pytest.raises(RomanoWolfInputError):
        RomanoWolfAnalysis.from_dict(payload)
