"""Behavioural guards for the Hansen-Lunde-Nason Model Confidence Set."""

from __future__ import annotations

import copy
import math
from decimal import Decimal

import numpy as np
import pytest
import research.engine.spa as spa_module
from research.engine.mcs import (
    MCS_ALPHA,
    MCS_CONFIDENCE,
    MCS_SCHEMA_VERSION,
    McsCandidate,
    McsInputError,
    McsResult,
    _range_decision,
    mcs_test,
)
from research.engine.spa import spa_test
from research.portfolio.resample import DEFAULT_REPLICATIONS, DEFAULT_SEED
from research.portfolio.resample import stationary_bootstrap as p04_stationary_bootstrap


def _correlated_family(
    seed: int,
    *,
    days: int = 300,
    candidates: int = 6,
    correlation: float = 0.919,
) -> dict[str, np.ndarray]:
    generator = np.random.default_rng(seed)
    common = generator.normal(0.0, math.sqrt(correlation), days)
    residual_scale = math.sqrt(1.0 - correlation)
    return {
        f"candidate_{index}": common + generator.normal(0.0, residual_scale, days)
        for index in range(candidates)
    }


def test_single_candidate_returns_itself() -> None:
    result = mcs_test(
        {"only": np.asarray([0.1, -0.2, 0.3])},
        mean_block_length=2,
        replications=99,
        seed=11,
    )

    assert result.surviving_candidates == ("only",)
    assert result.elimination_order == ()
    assert result.steps == ()
    assert len(result.candidates) == 1
    assert result.candidates[0].name == "only"
    assert result.candidates[0].mean_loss == pytest.approx(-0.06666666666666667)
    assert result.candidates[0].elimination_rank == 1
    assert result.candidates[0].mcs_p_value == 1.0
    assert result.candidates[0].in_mcs


def test_range_decision_uses_only_the_current_set_and_signed_range_rule() -> None:
    names = ("worst", "middle", "best", "already_removed")
    observed = np.asarray(
        [
            [0.0, 2.0, 4.0, 100.0],
            [-2.0, 0.0, 1.0, 100.0],
            [-4.0, -1.0, 0.0, 100.0],
            [-100.0, -100.0, -100.0, 0.0],
        ]
    )
    bootstrap = np.zeros((3, 4, 4), dtype=np.float64)
    for replication, maximum in enumerate((1.0, 4.0, 5.0)):
        bootstrap[replication, 0, 2] = maximum
        bootstrap[replication, 2, 0] = -maximum
        bootstrap[replication, :, 3] = 1_000.0
        bootstrap[replication, 3, :] = -1_000.0
        bootstrap[replication, 3, 3] = 0.0

    decision = _range_decision(
        names,
        observed,
        bootstrap,
        active=(0, 1, 2),
    )

    assert decision.statistic == 4.0
    assert decision.p_value == 0.75
    assert decision.eliminated == "worst"
    assert decision.elimination_score == 4.0


def test_range_elimination_breaks_exact_ties_by_candidate_identifier() -> None:
    names = ("zeta", "alpha", "best")
    observed = np.asarray([[0.0, 0.0, 3.0], [0.0, 0.0, 3.0], [-3.0, -3.0, 0.0]])
    bootstrap = np.zeros((9, 3, 3), dtype=np.float64)

    decision = _range_decision(
        names,
        observed,
        bootstrap,
        active=(0, 1, 2),
    )

    assert decision.eliminated == "alpha"


def test_one_dominant_candidate_reduces_to_a_singleton() -> None:
    returns = _correlated_family(101, days=500, candidates=8)
    returns["candidate_0"] = returns["candidate_0"] + 0.30

    result = mcs_test(
        returns,
        mean_block_length=5,
        replications=999,
        seed=102,
    )

    assert result.surviving_candidates == ("candidate_0",)
    assert result.candidate("candidate_0").mcs_p_value >= 0.10
    assert all(
        candidate.mcs_p_value < 0.10
        for candidate in result.candidates
        if candidate.name != "candidate_0"
    )


def test_higher_return_has_lower_loss_and_survives() -> None:
    generator = np.random.default_rng(201)
    common = generator.normal(0.0, 0.2, 400)
    returns = {
        "higher_return": common + 0.20 + generator.normal(0.0, 0.05, 400),
        "lower_return": common + generator.normal(0.0, 0.05, 400),
    }

    result = mcs_test(returns, mean_block_length=5, replications=499, seed=202)

    assert result.candidate("higher_return").mean_loss < result.candidate("lower_return").mean_loss
    assert result.surviving_candidates == ("higher_return",)
    assert result.elimination_order == ("lower_return",)


def test_mcs_p_values_are_monotone_in_elimination_order() -> None:
    returns = _correlated_family(301, days=400, candidates=6)
    for index, name in enumerate(returns):
        returns[name] = returns[name] + 0.05 * index

    result = mcs_test(returns, mean_block_length=5, replications=499, seed=302)
    ordered = sorted(result.candidates, key=lambda candidate: candidate.elimination_rank)

    assert [candidate.elimination_rank for candidate in ordered] == list(range(1, 7))
    assert [candidate.mcs_p_value for candidate in ordered] == sorted(
        candidate.mcs_p_value for candidate in ordered
    )
    assert result.elimination_order == tuple(candidate.name for candidate in ordered[:-1])


def test_exact_identical_streams_have_zero_pair_score_and_remain_together() -> None:
    values = np.random.default_rng(401).normal(0.0, 1.0, 300)

    result = mcs_test(
        {"first": values, "second": values.copy()},
        mean_block_length=5,
        replications=499,
        seed=402,
    )

    assert result.surviving_candidates == ("first", "second")
    assert result.steps[0].statistic == 0.0
    assert result.steps[0].p_value == 1.0


def test_unequal_zero_variance_pair_fails_closed_with_candidate_names() -> None:
    with pytest.raises(McsInputError, match="better.*worse|worse.*better"):
        mcs_test(
            {
                "better": np.full(100, 1.0),
                "worse": np.full(100, 0.0),
            },
            mean_block_length=5,
            replications=99,
            seed=501,
        )


def test_mcs_is_bit_for_bit_deterministic() -> None:
    returns = _correlated_family(601, days=300, candidates=5)

    first = mcs_test(returns, mean_block_length=10, replications=499, seed=602)
    second = mcs_test(returns, mean_block_length=10, replications=499, seed=602)

    assert first == second
    assert first.to_dict() == second.to_dict()


def test_spa_and_mcs_share_stationary_bootstrap_indices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    returns = _correlated_family(651, days=180, candidates=4)
    sampled_indices: list[np.ndarray] = []

    def capture_bootstrap(
        values: np.ndarray,
        mean_block_length: float,
        *,
        replications: int,
        seed: int,
    ) -> np.ndarray:
        sampled = p04_stationary_bootstrap(
            values,
            mean_block_length,
            replications=replications,
            seed=seed,
        )
        sampled_indices.append(sampled.astype(np.int64))
        return sampled

    monkeypatch.setattr(spa_module, "stationary_bootstrap", capture_bootstrap)

    spa_test(returns, mean_block_length=5, replications=99, seed=652)
    mcs_test(returns, mean_block_length=5, replications=99, seed=652)

    assert len(sampled_indices) == 2
    np.testing.assert_array_equal(sampled_indices[0], sampled_indices[1])


def test_mcs_uses_production_defaults_and_exact_membership_boundary() -> None:
    assert DEFAULT_REPLICATIONS == 10_000
    assert DEFAULT_SEED == 20260719
    assert Decimal("0.10") == MCS_ALPHA
    assert Decimal("0.90") == MCS_CONFIDENCE

    at_boundary = McsCandidate(
        name="at",
        mean_loss=0.0,
        elimination_rank=1,
        mcs_p_value=0.10,
    )
    below_boundary = McsCandidate(
        name="below",
        mean_loss=0.0,
        elimination_rank=1,
        mcs_p_value=0.09999999999999999,
    )

    assert at_boundary.in_mcs
    assert not below_boundary.in_mcs


def _valid_payload() -> dict[str, object]:
    returns = _correlated_family(701, days=200, candidates=3)
    return mcs_test(
        returns,
        mean_block_length=5,
        replications=99,
        seed=702,
    ).to_dict()


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("schema",), MCS_SCHEMA_VERSION + 1),
        (("schema",), True),
        (("loss",), "daily net return"),
        (("alpha",), "0.11"),
        (("confidence",), "0.89"),
        (("candidate_count",), 4),
        (("observation_count",), 2),
        (("seed",), "702"),
        (("replications",), 1),
        (("candidates", 0, "mcs_p_value"), math.nan),
        (("candidates", 0, "mcs_p_value"), "0.10"),
        (("candidates", 0, "in_mcs"), "yes"),
        (("candidates", 0, "elimination_rank"), 99),
        (("steps", 0, "p_value"), -0.01),
        (("steps", 0, "current_candidates"), ["unknown"]),
        (("steps", 0, "eliminated"), "unknown"),
        (("surviving_candidates",), []),
        (("elimination_order",), []),
    ],
)
def test_mcs_result_rejects_corrupt_serialized_evidence(
    path: tuple[str | int, ...],
    value: object,
) -> None:
    payload = copy.deepcopy(_valid_payload())
    target: object = payload
    for key in path[:-1]:
        assert isinstance(target, (dict, list))
        target = target[key]  # type: ignore[index]
    assert isinstance(target, (dict, list))
    target[path[-1]] = value  # type: ignore[index]

    with pytest.raises(McsInputError):
        McsResult.from_dict(payload)


def test_mcs_result_rejects_non_monotone_model_p_values() -> None:
    payload = _valid_payload()
    candidates = payload["candidates"]
    assert isinstance(candidates, list)
    ranked = sorted(candidates, key=lambda candidate: candidate["elimination_rank"])
    ranked[0]["mcs_p_value"] = 0.9
    ranked[0]["in_mcs"] = True

    with pytest.raises(McsInputError, match="monotone"):
        McsResult.from_dict(payload)
