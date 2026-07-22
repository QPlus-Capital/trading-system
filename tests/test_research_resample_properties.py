"""Deterministic properties for the stationary bootstrap's pure-array contract."""

from __future__ import annotations

import numpy as np
from hypothesis import given
from hypothesis import strategies as st
from research.portfolio.resample import stationary_bootstrap


@given(
    values=st.lists(
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        min_size=1,
        max_size=30,
    ),
    block_length=st.integers(min_value=1, max_value=60),
    replications=st.integers(min_value=1, max_value=20),
    seed=st.integers(min_value=0, max_value=2**32 - 1),
)
def test_resamples_have_exact_shape_domain_and_determinism(
    values: list[float], block_length: int, replications: int, seed: int
) -> None:
    daily_returns = np.asarray(values, dtype=np.float64)
    original = daily_returns.copy()

    first = stationary_bootstrap(daily_returns, block_length, replications=replications, seed=seed)
    second = stationary_bootstrap(daily_returns, block_length, replications=replications, seed=seed)

    assert first.shape == (replications, len(daily_returns))
    assert np.array_equal(first, second)
    assert np.isin(first, daily_returns).all()
    assert np.array_equal(daily_returns, original)


@given(
    value=st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
    sample_size=st.integers(min_value=1, max_value=30),
    block_length=st.integers(min_value=1, max_value=60),
)
def test_constant_series_remains_constant(
    value: float, sample_size: int, block_length: int
) -> None:
    daily_returns = np.full(sample_size, value)
    samples = stationary_bootstrap(daily_returns, block_length, replications=20, seed=7)
    assert np.all(samples == value)
