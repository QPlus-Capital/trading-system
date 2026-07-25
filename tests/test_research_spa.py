"""Behavioural and calibration guards for Hansen's SPA family test."""

from __future__ import annotations

import csv
import json
import math
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest
from research.engine.spa import (
    SPA_ALPHA,
    SpaAnalysis,
    SpaInputError,
    SpaResult,
    _bootstrap_indices,
    _consistent_recentering,
    _monte_carlo_p_value,
    _stationary_bootstrap_variances,
    _studentized_spa_statistics,
    analyze_spa,
    load_candidate_family,
    spa_test,
)
from research.portfolio.resample import (
    DEFAULT_REPLICATIONS,
    DEFAULT_SEED,
    SENSITIVITY_BLOCK_LENGTHS,
    stationary_bootstrap,
)


def _noise_family(seed: int, *, days: int = 180, candidates: int = 8) -> dict[str, np.ndarray]:
    generator = np.random.default_rng(seed)
    return {
        f"candidate_{index}": generator.normal(0.0, 1.0, days)
        for index in range(candidates)
    }


def _least_favourable_reality_check_p_value(
    returns: Mapping[str, np.ndarray],
    *,
    mean_block_length: int,
    replications: int,
    seed: int,
) -> float:
    """Small test oracle for White's unstudentized, least-favourable null."""
    matrix = np.column_stack(tuple(returns.values()))
    sample_size = len(matrix)
    indices = stationary_bootstrap(
        np.arange(sample_size, dtype=np.float64),
        mean_block_length,
        replications=replications,
        seed=seed,
    ).astype(np.int64)
    observed = max(0.0, float(np.sqrt(sample_size) * matrix.mean(axis=0).max()))
    bootstrap_means = np.column_stack(
        tuple(matrix[indices, index].mean(axis=1) for index in range(matrix.shape[1]))
    )
    centered = bootstrap_means - matrix.mean(axis=0)
    bootstrap_statistics = np.maximum(
        0.0,
        np.sqrt(sample_size) * centered.max(axis=1),
    )
    return float(np.mean(bootstrap_statistics > observed))


def test_spa_detects_one_positive_candidate_among_noise() -> None:
    returns = _noise_family(101, days=300)
    returns["real_edge"] = np.random.default_rng(102).normal(0.24, 1.0, 300)

    result = spa_test(returns, mean_block_length=5, replications=999, seed=103)

    assert result.p_value <= 0.05
    assert result.passes


def test_consistent_recentering_ignores_strongly_inferior_candidate() -> None:
    generator = np.random.default_rng(201)
    base = {
        "good": generator.normal(0.20, 1.0, 300),
        "noise": generator.normal(0.0, 1.0, 300),
    }
    contaminated = {
        **base,
        "strongly_inferior": generator.normal(-100.0, 10.0, 300),
    }

    clean_spa = spa_test(base, mean_block_length=5, replications=999, seed=202)
    contaminated_spa = spa_test(
        contaminated,
        mean_block_length=5,
        replications=999,
        seed=202,
    )
    clean_reality_check = _least_favourable_reality_check_p_value(
        base,
        mean_block_length=5,
        replications=999,
        seed=202,
    )
    contaminated_reality_check = _least_favourable_reality_check_p_value(
        contaminated,
        mean_block_length=5,
        replications=999,
        seed=202,
    )

    assert contaminated_spa.p_value == clean_spa.p_value
    assert contaminated_reality_check > clean_reality_check


def test_studentization_is_invariant_to_positive_candidate_rescaling() -> None:
    returns = _noise_family(301, days=240, candidates=4)
    returns["candidate_0"] += 0.18
    scaled = dict(returns)
    scaled["candidate_0"] = returns["candidate_0"] * 17.0

    original = spa_test(returns, mean_block_length=5, replications=999, seed=302)
    transformed = spa_test(scaled, mean_block_length=5, replications=999, seed=302)

    assert transformed.statistic == pytest.approx(original.statistic, rel=1e-12, abs=1e-12)
    assert transformed.p_value == original.p_value


def test_spa_is_bit_for_bit_deterministic() -> None:
    returns = _noise_family(401, days=240, candidates=4)

    first = spa_test(returns, mean_block_length=10, replications=499, seed=402)
    second = spa_test(returns, mean_block_length=10, replications=499, seed=402)

    assert first == second
    assert first.to_dict() == second.to_dict()


def test_spa_analysis_uses_p04_selector_and_reports_all_sensitivities(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    returns = _noise_family(501, days=700, candidates=3)
    selected: list[Mapping[str, np.ndarray]] = []
    spa_calls: list[tuple[int, int, int]] = []
    spa_inputs: list[Mapping[str, np.ndarray]] = []

    def fake_select(candidate_returns: Mapping[str, np.ndarray]) -> int:
        selected.append(candidate_returns)
        return 7

    def fake_spa(
        _candidate_returns: Mapping[str, np.ndarray],
        *,
        mean_block_length: int,
        replications: int,
        seed: int,
    ) -> SpaResult:
        spa_inputs.append(_candidate_returns)
        spa_calls.append((mean_block_length, replications, seed))
        return SpaResult(block_length=mean_block_length, statistic=1.0, p_value=0.01)

    monkeypatch.setattr("research.engine.spa.select_block_length", fake_select)
    monkeypatch.setattr("research.engine.spa.spa_test", fake_spa)
    analysis = analyze_spa(returns, replications=99, seed=502)

    assert len(selected) == 1
    assert set(selected[0]) == set(returns)
    assert len(spa_inputs) == 5
    assert all(set(candidate_returns) == set(returns) for candidate_returns in spa_inputs)
    assert analysis.selected_block_length == 7
    assert set(analysis.sensitivity) == set(SENSITIVITY_BLOCK_LENGTHS)
    assert analysis.replications == 99
    assert analysis.seed == 502
    assert spa_calls == [
        (7, 99, 502),
        (5, 99, 502),
        (10, 99, 502),
        (20, 99, 502),
        (60, 99, 502),
    ]
    assert DEFAULT_REPLICATIONS == 10_000
    assert DEFAULT_SEED == 20260719


def test_family_gate_requires_selected_and_every_sensitivity() -> None:
    passing = SpaResult(block_length=7, statistic=2.0, p_value=0.05)
    failing = SpaResult(block_length=20, statistic=1.0, p_value=0.0501)
    sensitivity = {
        5: SpaResult(block_length=5, statistic=2.0, p_value=0.05),
        10: SpaResult(block_length=10, statistic=2.0, p_value=0.05),
        20: failing,
        60: SpaResult(block_length=60, statistic=2.0, p_value=0.05),
    }
    analysis = SpaAnalysis(
        selected=passing,
        sensitivity=sensitivity,
        replications=10_000,
        seed=20260719,
        candidate_count=36,
        observation_count=500,
    )

    assert passing.passes
    assert Decimal(str(passing.p_value)) == SPA_ALPHA
    assert not failing.passes
    assert not analysis.passes


def test_paired_stationary_bootstrap_preserves_identical_candidate_paths() -> None:
    values = np.random.default_rng(601).normal(0.1, 1.0, 240)
    result = spa_test(
        {"first": values, "second": values.copy()},
        mean_block_length=10,
        replications=499,
        seed=602,
    )

    assert result.candidate_statistics is not None
    assert result.candidate_statistics["first"] == result.candidate_statistics["second"]
    assert result.recentered_candidates == ()


def test_bootstrap_indices_forward_all_p04_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[np.ndarray, int, int, int]] = []

    def fake_bootstrap(
        values: np.ndarray,
        mean_block_length: int,
        *,
        replications: int,
        seed: int,
    ) -> np.ndarray:
        calls.append((values, mean_block_length, replications, seed))
        return np.asarray([[2.0, 1.0, 0.0], [1.0, 2.0, 0.0]])

    monkeypatch.setattr("research.engine.spa.stationary_bootstrap", fake_bootstrap)

    indices = _bootstrap_indices(3, 7, replications=2, seed=11)

    assert len(calls) == 1
    np.testing.assert_array_equal(calls[0][0], np.arange(3))
    assert calls[0][1:] == (7, 2, 11)
    assert indices.dtype == np.int64
    np.testing.assert_array_equal(indices, [[2, 1, 0], [1, 2, 0]])


def test_stationary_bootstrap_variance_matches_the_kernel_oracle() -> None:
    matrix = np.asarray(
        [
            [1.0, 2.0],
            [2.0, -1.0],
            [4.0, 3.0],
            [0.0, -2.0],
            [3.0, 1.0],
        ]
    )

    np.testing.assert_allclose(
        _stationary_bootstrap_variances(matrix, 2),
        [1.005, 1.6640000000000004],
        rtol=0.0,
        atol=1e-14,
    )
    np.testing.assert_allclose(
        _stationary_bootstrap_variances(matrix, 3),
        [0.7041975308641972, 1.1541728395061734],
        rtol=0.0,
        atol=1e-14,
    )


def test_consistent_recentering_uses_hansens_exact_threshold() -> None:
    sample_size = 100
    boundary = -math.sqrt(2.0 * math.log(math.log(sample_size))) / math.sqrt(sample_size)
    means = np.asarray([-0.2, boundary, -0.15, -0.01, 0.1])
    variances = np.ones(5)

    recentered, retained = _consistent_recentering(means, variances, sample_size)

    np.testing.assert_array_equal(retained, [True, True, False, False, False])
    np.testing.assert_array_equal(recentered, [-0.2, boundary, 0.0, 0.0, 0.0])


def test_studentized_spa_statistic_uses_the_recentered_family_maximum() -> None:
    candidate_scores, observed, bootstrap, retained = _studentized_spa_statistics(
        np.asarray([0.1, -0.5]),
        np.asarray([[0.2, -0.1], [0.0, -0.3]]),
        np.asarray([1.0, 4.0]),
        100,
    )

    np.testing.assert_allclose(candidate_scores, [1.0, -2.5])
    assert observed == 1.0
    np.testing.assert_allclose(bootstrap, [1.0, 0.0])
    np.testing.assert_array_equal(retained, [False, True])


def test_monte_carlo_p_value_counts_ties_and_adds_one() -> None:
    assert _monte_carlo_p_value(np.asarray([0.0, 1.0, 2.0]), 1.0) == 0.75


def test_negative_only_family_cannot_pass_positive_edge_gate() -> None:
    generator = np.random.default_rng(701)
    returns = {
        "negative_a": generator.normal(-0.5, 1.0, 240),
        "negative_b": generator.normal(-1.0, 2.0, 240),
    }

    result = spa_test(returns, mean_block_length=5, replications=499, seed=702)

    assert result.statistic == 0.0
    assert not result.passes


def _write_family(directory: Path, *, candidate_count: int = 3) -> dict[str, np.ndarray]:
    directory.mkdir()
    names = [f"v{index}__24m" for index in range(candidate_count)]
    rows = [
        ("2026-01-01", *("0.1" for _ in names)),
        ("2026-01-02", *("-0.2" for _ in names)),
        ("2026-01-03", *("0.0" for _ in names)),
    ]
    with (directory / "candidate_daily_returns.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("loss_day", *names))
        writer.writerows(rows)
    metadata = {
        "persisted_candidates": names,
        "persisted_candidate_count": candidate_count,
        "trial_counts": {"formal": candidate_count, "manual": 5, "total": candidate_count + 5},
    }
    (directory / "candidate_metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )
    return {name: np.asarray([0.1, -0.2, 0.0]) for name in names}


def test_spa_loader_reads_persisted_matrix_without_recomputation(tmp_path: Path) -> None:
    expected = _write_family(tmp_path / "family")

    loaded = load_candidate_family(
        tmp_path / "family",
        expected_candidates=set(expected),
    )

    assert loaded.dates == ("2026-01-01", "2026-01-02", "2026-01-03")
    assert set(loaded.returns) == set(expected)
    for candidate, values in expected.items():
        np.testing.assert_array_equal(loaded.returns[candidate], values)


@pytest.mark.parametrize(
    "damage",
    ("missing", "unreadable", "non_finite", "metadata_mismatch", "expected_mismatch"),
)
def test_spa_loader_fails_closed_on_missing_corrupt_or_incomplete_family(
    tmp_path: Path,
    damage: str,
) -> None:
    directory = tmp_path / damage
    expected = _write_family(directory)
    expected_names = set(expected)
    daily_path = directory / "candidate_daily_returns.csv"
    metadata_path = directory / "candidate_metadata.json"
    if damage == "missing":
        daily_path.unlink()
    elif damage == "unreadable":
        daily_path.write_bytes(b"\xff\xfe")
    elif damage == "non_finite":
        text = daily_path.read_text(encoding="utf-8").replace("0.1", "NaN", 1)
        daily_path.write_text(text, encoding="utf-8")
    elif damage == "metadata_mismatch":
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata["persisted_candidate_count"] = 2
        metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    else:
        expected_names.add("absent__36m")

    with pytest.raises(SpaInputError):
        load_candidate_family(directory, expected_candidates=expected_names)


def test_spa_result_rejects_invalid_serialized_evidence() -> None:
    valid = SpaResult(block_length=5, statistic=1.0, p_value=0.25).to_dict()
    for key, value in (
        ("p_value", math.nan),
        ("p_value", -0.1),
        ("p_value", 1.1),
        ("block_length", 0),
    ):
        damaged = dict(valid)
        damaged[key] = value
        with pytest.raises(SpaInputError):
            SpaResult.from_dict(damaged)
