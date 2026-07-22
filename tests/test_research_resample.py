"""Behavioural and calibration tests for dependent daily-return resampling."""

from __future__ import annotations

import inspect
import math
from typing import cast

import numpy as np
import numpy.typing as npt
import pytest
from research.portfolio.resample import (
    DEFAULT_REPLICATIONS,
    DEFAULT_SEED,
    SENSITIVITY_BLOCK_LENGTHS,
    politis_white_block_length,
    select_block_length,
    stationary_bootstrap,
    stationary_bootstrap_sensitivity,
)

FloatArray = npt.NDArray[np.float64]


def _ar1(phi: float, innovations: FloatArray) -> FloatArray:
    values = np.empty_like(innovations)
    values[0] = innovations[0] / math.sqrt(1.0 - phi**2)
    for index in range(1, len(values)):
        values[index] = phi * values[index - 1] + innovations[index]
    return values


def test_politis_white_matches_the_corrected_ar1_reference() -> None:
    """The expected value was independently calculated from the published flat-top formula."""
    innovations = np.random.default_rng(731).normal(size=240)
    daily_returns = _ar1(0.35, innovations)

    estimate = politis_white_block_length(daily_returns)

    # k_n=5, m_hat=3, M=6, G=2.2409622705092853,
    # sigma_hat^2=3.0273982588793373, corrected D_SB=18.330280435731286.
    assert estimate == pytest.approx(5.085266752079944, rel=1e-12)


@pytest.mark.parametrize(
    ("daily_returns", "expected"),
    [
        (np.arange(2, dtype=np.float64), 1.0),
        ((-1.0) ** np.arange(3), 3.634241185664279),
        ((-1.0) ** np.arange(4), 1.587401051968198),
        (np.arange(5, dtype=np.float64), 1.3049558803896213),
        (np.arange(6, dtype=np.float64), 1.1447142425533319),
        (np.arange(6, dtype=np.float64) * 1e-8, 1.144714242553332),
    ],
)
def test_politis_white_matches_corrected_small_sample_references(
    daily_returns: FloatArray, expected: float
) -> None:
    """Pin bandwidth boundaries that a long AR(1) reference does not exercise."""
    assert politis_white_block_length(daily_returns) == pytest.approx(expected, rel=1e-12)


def test_politis_white_treats_near_zero_long_run_variance_as_unbounded() -> None:
    daily_returns = np.array([-100.0, 100.00000000000011, 0.0])
    assert math.isinf(politis_white_block_length(daily_returns))


def test_politis_white_returns_one_when_both_plugin_moments_vanish() -> None:
    daily_returns = np.array(
        [
            4.7453952939404387e-09,
            -1.8075136182508785e-08,
            1.5338231205719854e-08,
            -1.0096430548083076e-08,
            2.3998281111964333e-08,
        ]
    )
    assert politis_white_block_length(daily_returns) == 1.0


def test_white_noise_selects_a_block_length_near_one() -> None:
    white_noise = np.random.default_rng(55).normal(size=2_000)
    selected = select_block_length({"white-noise": white_noise})
    assert 1 <= selected <= 3


def test_selector_ceilings_the_maximum_and_keeps_minimum_one() -> None:
    innovations = np.random.default_rng(731).normal(size=240)
    ar1 = _ar1(0.35, innovations)
    assert select_block_length({"flat": np.zeros(240), "ar1": ar1}) == 6
    assert select_block_length({"flat": np.zeros(20)}) == 1


def test_selector_fails_closed_above_one_tenth_with_complete_diagnostic() -> None:
    with pytest.raises(ValueError) as raised:
        select_block_length({"trend-candidate": np.arange(100, dtype=np.float64)})
    assert str(raised.value) == (
        "Politis-White block length rejected: L=15 exceeds floor(T/10)=10 "
        "for candidate 'trend-candidate' (T=100)"
    )


def test_selector_fails_closed_on_an_infinite_estimate() -> None:
    with pytest.raises(ValueError) as raised:
        select_block_length({"zero-long-run-variance": np.array([-1.0, 1.0, 0.0])})
    assert str(raised.value) == (
        "Politis-White block length rejected: L=inf exceeds floor(T/10)=0 "
        "for candidate 'zero-long-run-variance' (T=3)"
    )


def test_selector_requires_a_nonempty_common_daily_grid() -> None:
    with pytest.raises(ValueError) as empty:
        select_block_length({})
    assert str(empty.value) == "candidate_returns must contain at least one candidate"

    with pytest.raises(ValueError) as mismatched:
        select_block_length({"short": np.zeros(20), "long": np.zeros(21)})
    assert str(mismatched.value) == "candidate returns must share one common daily grid"

    assert select_block_length({"boundary": np.zeros(10)}) == 1

    with pytest.raises(ValueError) as invalid_candidate:
        select_block_length({"empty-candidate": np.array([], dtype=np.float64)})
    assert str(invalid_candidate.value) == "candidate 'empty-candidate' daily_returns must be non-empty"


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (np.array([], dtype=np.float64), "non-empty"),
        (np.zeros((2, 2)), "one-dimensional"),
        (np.array([0.0, np.nan]), "finite"),
        (np.array([0.0, np.inf]), "finite"),
    ],
)
def test_estimator_rejects_invalid_return_arrays(bad: FloatArray, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        politis_white_block_length(bad)


def test_estimator_validation_names_its_input() -> None:
    with pytest.raises(ValueError) as raised:
        politis_white_block_length(np.array([], dtype=np.float64))
    assert str(raised.value) == "daily_returns must be non-empty"


@pytest.mark.parametrize("mean_block_length", [0, -1, 0.5, np.nan, np.inf])
def test_stationary_bootstrap_rejects_invalid_block_lengths(mean_block_length: float) -> None:
    with pytest.raises(ValueError, match="mean_block_length"):
        stationary_bootstrap(np.arange(5, dtype=np.float64), mean_block_length)


@pytest.mark.parametrize("replications", [0, -1, 1.5, True])
def test_stationary_bootstrap_rejects_invalid_replications(replications: object) -> None:
    with pytest.raises(ValueError, match="replications"):
        stationary_bootstrap(
            np.arange(5, dtype=np.float64),
            2,
            replications=cast(int, replications),
        )


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        (np.array([], dtype=np.float64), "non-empty"),
        (np.zeros((2, 2)), "one-dimensional"),
        (np.array([0.0, np.nan]), "finite"),
    ],
)
def test_stationary_bootstrap_rejects_invalid_return_arrays(bad: FloatArray, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        stationary_bootstrap(bad, 2)


def test_geometric_blocks_have_the_requested_mean_and_wrap_circularly() -> None:
    sample_size = 5_000
    samples = stationary_bootstrap(
        np.arange(sample_size, dtype=np.float64),
        10,
        replications=200,
        seed=401,
    )
    previous = samples[:, :-1]
    current = samples[:, 1:]
    continues = current == (previous + 1) % sample_size
    observed_mean = 1.0 / (1.0 - float(continues.mean()))

    assert observed_mean == pytest.approx(10.0, rel=0.02)
    assert np.any((previous == sample_size - 1) & (current == 0))


def test_circular_stationary_bootstrap_has_uniform_marginal_weights() -> None:
    daily_returns = np.arange(7, dtype=np.float64)
    samples = stationary_bootstrap(daily_returns, 60, replications=20_000, seed=924)
    counts = np.bincount(samples.astype(np.int64).ravel(), minlength=len(daily_returns))
    expected = samples.size / len(daily_returns)
    assert np.max(np.abs(counts - expected)) / expected < 0.03


def test_seed_is_bit_for_bit_reproducible_and_input_is_not_mutated() -> None:
    daily_returns = np.array([0.0, 1.5, -0.5, 0.0, 2.0])
    original = daily_returns.copy()
    default_a = stationary_bootstrap(daily_returns, 3, replications=25)
    default_b = stationary_bootstrap(daily_returns, 3, replications=25)
    explicit_a = stationary_bootstrap(daily_returns, 3, replications=25, seed=17)
    explicit_b = stationary_bootstrap(daily_returns, 3, replications=25, seed=17)

    assert np.array_equal(default_a, default_b)
    assert np.array_equal(explicit_a, explicit_b)
    assert not np.array_equal(default_a, explicit_a)
    assert np.array_equal(daily_returns, original)


def test_seed_pins_independent_restart_draws_and_uniform_zero_starts() -> None:
    samples = stationary_bootstrap(
        np.arange(2, dtype=np.float64),
        1,
        replications=3,
        seed=0,
    )
    assert np.array_equal(samples, np.array([[1.0, 0.0], [1.0, 1.0], [1.0, 1.0]]))


def test_bootstrap_validation_names_its_input() -> None:
    with pytest.raises(ValueError) as raised:
        stationary_bootstrap(np.array([], dtype=np.float64), 2)
    assert str(raised.value) == "daily_returns must be non-empty"


def test_sensitivity_and_public_defaults_are_fixed() -> None:
    daily_returns = np.arange(8, dtype=np.float64)
    sensitivity = stationary_bootstrap_sensitivity(daily_returns, replications=12, seed=99)

    assert tuple(sensitivity) == (5, 10, 20, 60)
    assert SENSITIVITY_BLOCK_LENGTHS == (5, 10, 20, 60)
    assert all(samples.shape == (12, 8) for samples in sensitivity.values())
    for block_length, samples in sensitivity.items():
        expected = stationary_bootstrap(daily_returns, block_length, replications=12, seed=99)
        assert np.array_equal(samples, expected)
    assert DEFAULT_REPLICATIONS == 10_000
    assert DEFAULT_SEED == 20260719
    parameters = inspect.signature(stationary_bootstrap).parameters
    assert parameters["replications"].default == 10_000
    assert parameters["seed"].default == 20260719
