"""Small semantic assertions for recurring trading-system test obligations."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from decimal import Decimal


def assert_reconciles[T, K](
    expected: Sequence[T],
    buckets: Mapping[str, Sequence[T]],
    *,
    key: Callable[[T], K],
) -> None:
    """Assert every expected record lands in exactly one bucket, with no extra records."""
    expected_keys = Counter(key(item) for item in expected)
    actual_keys = Counter(key(item) for items in buckets.values() for item in items)
    assert actual_keys == expected_keys, (
        "records must reconcile exactly once across buckets; "
        f"expected {expected_keys}, observed {actual_keys}"
    )


def assert_aggregate_equals_parts(parts: Iterable[Decimal], aggregate: Decimal) -> None:
    """Assert a reported Decimal aggregate equals the exact sum of its component buckets."""
    expected = sum(parts, start=Decimal(0))
    assert aggregate == expected, f"aggregate {aggregate} does not equal component sum {expected}"


def assert_selection_execution_parity(
    selected: Mapping[str, object],
    executed: Mapping[str, object],
    fields: Iterable[str],
) -> None:
    """Assert execution receives the exact selected value for every named configuration field."""
    for field in fields:
        assert field in selected, f"selection did not define required field {field!r}"
        assert field in executed, f"execution dropped selected field {field!r}"
        assert executed[field] == selected[field], (
            f"selection/execution mismatch for {field!r}: "
            f"selected {selected[field]!r}, executed {executed[field]!r}"
        )


def assert_config_propagates[V](cases: Mapping[str, V], execute: Callable[[V], V]) -> None:
    """Assert omitted/default/non-default/varying cases survive a configuration path unchanged."""
    for name, value in cases.items():
        observed = execute(value)
        assert observed == value, (
            f"config case {name!r} propagated {observed!r}, expected {value!r}"
        )


def assert_temporal_ownership[T, R](
    points: Mapping[str, T],
    expected: Mapping[str, R],
    owner: Callable[[T], R],
) -> None:
    """Assert named boundary instants map to the specified temporal owner."""
    assert points.keys() == expected.keys(), (
        "temporal cases and expectations must name the same rows"
    )
    for name, point in points.items():
        observed = owner(point)
        assert observed == expected[name], (
            f"temporal case {name!r} resolved to {observed!r}, expected {expected[name]!r}"
        )


def assert_numeric_cases[T, R](
    cases: Mapping[str, T],
    expected: Mapping[str, R],
    evaluate: Callable[[T], R],
) -> None:
    """Assert named zero/sign/rounding/threshold cases have their specified outcomes."""
    assert cases.keys() == expected.keys(), "numeric cases and expectations must name the same rows"
    for name, value in cases.items():
        observed = evaluate(value)
        assert observed == expected[name], (
            f"numeric case {name!r} produced {observed!r}, expected {expected[name]!r}"
        )


def assert_limit_monotonicity[T](
    samples: Iterable[T],
    *,
    weaker: Callable[[T], bool],
    stronger: Callable[[T], bool],
) -> None:
    """Assert a stronger limit never admits an input that the weaker limit blocks."""
    for sample in samples:
        weak_allowed = weaker(sample)
        strong_allowed = stronger(sample)
        assert not strong_allowed or weak_allowed, (
            f"stronger limit admitted a case blocked by the weaker limit: sample={sample!r}"
        )
