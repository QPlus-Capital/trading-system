"""Behavioural guards for the P-08 family-evidence selection protocol."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from research.engine.characterize import (
    effective_trial_count,
    synchronized_overfitting_diagnostics,
)
from research.stages.select import (
    NoAutomaticSelection,
    SelectionEvidence,
    choose_automatic_candidate,
)


def _ranking(rows: list[tuple[str, int, float, float, bool]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "variation": variation,
                "train_months": train_months,
                "mean_ret": mean_ret,
                "mean_rpd": mean_rpd,
                "frac_positive": 1.0,
                "complete": complete,
                "dsr": 0.01,
                "dsr_ok": False,
            }
            for variation, train_months, mean_ret, mean_rpd, complete in rows
        ]
    )


def _candidate(variation: str, train_months: int) -> str:
    return f"{variation}__train_{train_months}m"


def _evidence(
    rows: list[tuple[str, int, float, float, bool]],
    *,
    spa_passes: bool = True,
    romano_wolf: set[str] | None = None,
    mcs: set[str] | None = None,
) -> SelectionEvidence:
    family = frozenset(_candidate(row[0], row[1]) for row in rows)
    return SelectionEvidence(
        family=family,
        spa_passes=spa_passes,
        romano_wolf_eligible=frozenset(family if romano_wolf is None else romano_wolf),
        mcs_members=frozenset(family if mcs is None else mcs),
    )


def test_effective_trial_count_is_capped_and_monotone() -> None:
    values = [effective_trial_count(Decimal(str(rho))) for rho in (0, 0.25, 0.5, 0.75, 1)]

    assert values[0] == Decimal("41")
    assert values[-1] == Decimal("6")
    assert all(left >= right for left, right in zip(values, values[1:], strict=False))
    assert all(value <= Decimal("41") for value in values)


def test_synchronized_diagnostics_use_one_36_candidate_window_matrix(tmp_path: Path) -> None:
    names = [f"v{index:02d}__train_36m" for index in range(36)]
    generator = np.random.default_rng(20260726)
    common = generator.normal(0.2, 0.4, 8)
    frame: dict[str, object] = {"window": [f"w{index}" for index in range(8)]}
    for index, name in enumerate(names):
        frame[name] = common + generator.normal(0.0, 0.05 + index * 0.002, 8)
    pd.DataFrame(frame).to_csv(tmp_path / "candidate_window_returns.csv", index=False)
    (tmp_path / "candidate_metadata.json").write_text(
        json.dumps(
            {
                "formal_candidates": [{"candidate": name} for name in names],
                "persisted_candidates": names,
                "trial_counts": {"formal": 36, "manual": 5, "total": 41},
            }
        ),
        encoding="utf-8",
    )

    result = synchronized_overfitting_diagnostics(tmp_path)

    assert result["status"] == "available"
    assert result["role"] == "diagnostic_only"
    assert result["candidate_count"] == 36
    assert result["manual_trial_count"] == 5
    assert result["nominal_trial_count"] == 41
    assert result["pbo_split_count"] == 8
    assert len(result["candidates"]) == 36
    assert all(candidate["sample_count"] == 8 for candidate in result["candidates"].values())
    assert Decimal("6") <= Decimal(str(result["effective_trial_count"])) <= Decimal("41")
    assert result["benchmark_effective"] <= result["benchmark_nominal"]


def test_unusable_synchronized_diagnostics_are_labelled_not_zero_filled(
    tmp_path: Path,
) -> None:
    names = [f"v{index:02d}__train_36m" for index in range(35)]
    pd.DataFrame({"window": ["w0", "w1"], **{name: [0.1, 0.2] for name in names}}).to_csv(
        tmp_path / "candidate_window_returns.csv",
        index=False,
    )
    (tmp_path / "candidate_metadata.json").write_text(
        json.dumps(
            {
                "formal_candidates": [{"candidate": name} for name in names],
                "persisted_candidates": names,
                "trial_counts": {"formal": 35, "manual": 5, "total": 40},
            }
        ),
        encoding="utf-8",
    )

    result = synchronized_overfitting_diagnostics(tmp_path)

    assert result["status"] == "unavailable"
    assert result["pbo"] is None
    assert "36 formal" in result["reason"]


@pytest.mark.parametrize(
    ("window_count", "expected_splits"),
    [(8, 8), (9, 8), (10, 10), (11, 10)],
)
def test_pbo_uses_the_largest_permitted_even_split_count(
    tmp_path: Path,
    window_count: int,
    expected_splits: int,
) -> None:
    names = [f"v{index:02d}__train_36m" for index in range(36)]
    generator = np.random.default_rng(20260726 + window_count)
    frame: dict[str, object] = {"window": [f"w{index}" for index in range(window_count)]}
    for index, name in enumerate(names):
        frame[name] = generator.normal(0.1 + index * 0.001, 0.5, window_count)
    pd.DataFrame(frame).to_csv(tmp_path / "candidate_window_returns.csv", index=False)
    (tmp_path / "candidate_metadata.json").write_text(
        json.dumps(
            {
                "formal_candidates": [{"candidate": name} for name in names],
                "persisted_candidates": names,
                "trial_counts": {"formal": 36, "manual": 5, "total": 41},
            }
        ),
        encoding="utf-8",
    )

    result = synchronized_overfitting_diagnostics(tmp_path)

    assert result["status"] == "available"
    assert result["pbo_split_count"] == expected_splits


def test_spa_failure_blocks_selection_despite_diagnostics_and_returns() -> None:
    rows = [("baseline", 36, 100.0, 10.0, True)]

    with pytest.raises(NoAutomaticSelection, match="SPA"):
        choose_automatic_candidate(
            _ranking(rows),
            evidence=_evidence(rows, spa_passes=False),
            complexity_scores={"baseline": 3},
        )


@pytest.mark.parametrize(
    ("romano_wolf", "mcs", "complete", "frac_positive", "mean_rpd", "criterion"),
    [
        (set(), None, True, 1.0, 1.0, "Romano-Wolf"),
        (None, set(), True, 1.0, 1.0, "MCS"),
        (None, None, False, 1.0, 1.0, "completeness"),
        (None, None, True, 0.89, 1.0, "positive-market"),
        (None, None, True, 1.0, 0.84, "return/drawdown"),
    ],
)
def test_empty_intersection_names_the_criterion(
    romano_wolf: set[str] | None,
    mcs: set[str] | None,
    complete: bool,
    frac_positive: float,
    mean_rpd: float,
    criterion: str,
) -> None:
    rows = [("baseline", 36, 10.0, mean_rpd, complete)]
    ranking = _ranking(rows)
    ranking.loc[0, "frac_positive"] = frac_positive
    if criterion == "return/drawdown":
        ranking = pd.concat(
            [
                ranking,
                _ranking([("no_confirms", 36, 9.0, 1.0, True)]),
            ],
            ignore_index=True,
        )
        evidence_rows = [
            ("baseline", 36, 10.0, mean_rpd, complete),
            ("no_confirms", 36, 9.0, 1.0, True),
        ]
        evidence = _evidence(
            evidence_rows,
            romano_wolf={_candidate("baseline", 36)},
            mcs={_candidate("baseline", 36)},
        )
    else:
        evidence = _evidence(rows, romano_wolf=romano_wolf, mcs=mcs)

    with pytest.raises(NoAutomaticSelection, match=criterion):
        choose_automatic_candidate(
            ranking,
            evidence=evidence,
            complexity_scores=(
                {"baseline": 3, "no_confirms": 0}
                if "no_confirms" in set(ranking["variation"])
                else {"baseline": 3}
            ),
        )


def test_tie_break_order_is_complexity_then_return_then_train_then_name() -> None:
    rows = [
        ("baseline", 36, 99.0, 1.0, True),
        ("no_bb", 24, 10.0, 1.0, True),
        ("no_wpr", 18, 20.0, 1.0, True),
        ("no_rsi", 24, 20.0, 1.0, True),
        ("no_rsi", 36, 20.0, 1.0, True),
        ("no_bb", 36, 20.0, 1.0, True),
    ]
    scores = {"baseline": 3, "no_bb": 2, "no_wpr": 2, "no_rsi": 2}
    evidence = _evidence(rows)

    selected = choose_automatic_candidate(
        _ranking(rows),
        evidence=evidence,
        complexity_scores=scores,
    )

    assert selected.variation == "no_bb"
    assert selected.train_months == 36
    assert selected.complexity == 2


def test_automatic_selection_is_deterministic_under_input_row_permutation() -> None:
    rows = [
        ("no_wpr", 36, 20.0, 1.0, True),
        ("no_bb", 36, 20.0, 1.0, True),
        ("baseline", 36, 100.0, 1.0, True),
    ]
    scores = {"no_wpr": 2, "no_bb": 2, "baseline": 3}
    evidence = _evidence(rows)

    forward = choose_automatic_candidate(
        _ranking(rows),
        evidence=evidence,
        complexity_scores=scores,
    )
    reverse = choose_automatic_candidate(
        _ranking(list(reversed(rows))),
        evidence=evidence,
        complexity_scores=scores,
    )

    assert forward == reverse
    assert forward.variation == "no_bb"


def test_dsr_and_pbo_are_not_selection_inputs() -> None:
    rows = [("no_confirms", 36, 10.0, 1.0, True)]
    ranking = _ranking(rows)
    ranking["pbo"] = 1.0

    selected = choose_automatic_candidate(
        ranking,
        evidence=_evidence(rows),
        complexity_scores={"no_confirms": 0},
    )

    assert selected.variation == "no_confirms"


def test_structure_decimal_boundaries_are_inclusive() -> None:
    rows = [
        ("baseline", 36, 10.0, 0.85, True),
        ("no_confirms", 36, 9.0, 1.0, True),
    ]
    ranking = _ranking(rows)
    ranking.loc[ranking["variation"] == "baseline", "frac_positive"] = 0.90
    evidence = _evidence(
        rows,
        romano_wolf={_candidate("baseline", 36)},
    )

    selected = choose_automatic_candidate(
        ranking,
        evidence=evidence,
        complexity_scores={"baseline": 3, "no_confirms": 0},
    )

    assert selected.variation == "baseline"
