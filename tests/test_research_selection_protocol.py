"""Behavioural guards for the P-08 family-evidence selection protocol."""

from __future__ import annotations

import json
from collections.abc import Mapping
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import numpy as np
import pandas as pd
import pytest
from numpy.typing import NDArray
from research.engine import overfitting
from research.engine.characterize import (
    effective_trial_count,
    synchronized_overfitting_diagnostics,
)
from research.engine.mcs import McsCandidate, McsResult
from research.engine.overfitting import (
    deflated_sharpe_ratio,
    expected_max_sharpe,
    pbo,
    sharpe_ratio,
)
from research.engine.romano_wolf import RomanoWolfAnalysis, RomanoWolfCandidate
from research.engine.spa import SpaAnalysis, SpaResult
from research.portfolio.resample import SENSITIVITY_BLOCK_LENGTHS
from research.stages import _runbook as rb
from research.stages.select import (
    AutomaticCandidate,
    NoAutomaticSelection,
    SelectionEvidence,
    _load_selection_evidence,
    _validated_complexity_scores,
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


class _ArtifactRun:
    def __init__(self, paths: dict[str, Path]) -> None:
        self.paths = paths

    def require(self, name: str, produced_by: str) -> Path:
        assert produced_by == "edge"
        return self.paths[name]


def _family_payloads(name: str = "candidate__train_36m") -> dict[str, dict[str, Any]]:
    statistics = {name: 2.0}
    spa = SpaAnalysis(
        selected=SpaResult(1, 2.0, 0.01, statistics),
        sensitivity={
            block_length: SpaResult(block_length, 2.0, 0.01, statistics)
            for block_length in SENSITIVITY_BLOCK_LENGTHS
        },
        replications=99,
        seed=20260719,
        candidate_count=1,
        observation_count=120,
    )
    romano_wolf = RomanoWolfAnalysis(
        candidates=(RomanoWolfCandidate(1, name, 2.0, 0.01, 0.01),),
        block_length=1,
        replications=99,
        seed=20260719,
        observation_count=120,
    )
    mcs = McsResult(
        candidates=(McsCandidate(name, -0.1, 1, 1.0),),
        steps=(),
        block_length=1,
        replications=99,
        seed=20260719,
        observation_count=120,
    )
    return {
        "spa.json": spa.to_dict(),
        "romano_wolf.json": romano_wolf.to_dict(),
        "mcs.json": mcs.to_dict(),
    }


def _write_family_payloads(
    tmp_path: Path,
    payloads: Mapping[str, object],
) -> _ArtifactRun:
    paths: dict[str, Path] = {}
    for name, payload in payloads.items():
        path = tmp_path / name
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = path
    return _ArtifactRun(paths)


def test_effective_trial_count_is_capped_and_monotone() -> None:
    values = [effective_trial_count(Decimal(str(rho))) for rho in (0, 0.25, 0.5, 0.75, 1)]

    assert values == [
        Decimal("41"),
        Decimal("32.25"),
        Decimal("23.5"),
        Decimal("14.75"),
        Decimal("6"),
    ]
    assert all(left >= right for left, right in zip(values, values[1:], strict=False))
    assert all(value <= Decimal("41") for value in values)


@pytest.mark.parametrize(
    ("value", "error", "message"),
    [
        (0.5, TypeError, "rho_bar must be Decimal"),
        (Decimal("-0.1"), ValueError, "rho_bar must be finite and between zero and one"),
        (Decimal("1.1"), ValueError, "rho_bar must be finite and between zero and one"),
        (Decimal("NaN"), ValueError, "rho_bar must be finite and between zero and one"),
    ],
)
def test_effective_trial_count_rejects_invalid_inputs_exactly(
    value: object,
    error: type[Exception],
    message: str,
) -> None:
    with pytest.raises(error) as raised:
        effective_trial_count(value)  # type: ignore[arg-type]

    assert str(raised.value) == message


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

    assert result["status"] == "available", result
    assert result["role"] == "diagnostic_only"
    assert result["candidate_count"] == 36
    assert result["manual_trial_count"] == 5
    assert result["nominal_trial_count"] == 41
    assert result["pbo_split_count"] == 8
    assert len(result["candidates"]) == 36
    assert all(candidate["sample_count"] == 8 for candidate in result["candidates"].values())
    assert Decimal("6") <= Decimal(str(result["effective_trial_count"])) <= Decimal("41")
    assert result["benchmark_effective"] <= result["benchmark_nominal"]
    assert set(result) == {
        "benchmark_effective",
        "benchmark_nominal",
        "candidate_count",
        "candidates",
        "dsr_by_candidate",
        "dsr_nominal_by_candidate",
        "dsr_threshold",
        "effective_trial_count",
        "manual_trial_count",
        "nominal_trial_count",
        "pbo",
        "pbo_diagnostic_ok",
        "pbo_split_count",
        "pbo_threshold",
        "rho_bar",
        "role",
        "sample_count",
        "sharpe_variance",
        "source",
        "status",
    }

    matrix: NDArray[np.float64] = np.column_stack(
        [np.asarray(frame[name], dtype=np.float64) for name in names]
    )
    correlations: NDArray[np.float64] = np.asarray(
        np.corrcoef(matrix, rowvar=False),
        dtype=np.float64,
    )
    upper = correlations[np.triu_indices(36, k=1)]
    rho_bar = float(np.clip(upper.mean(), 0.0, 1.0))
    n_eff = float(effective_trial_count(Decimal(str(rho_bar))))
    sharpes = np.asarray(
        [sharpe_ratio(matrix[:, index].tolist()) for index in range(matrix.shape[1])],
        dtype=float,
    )
    sharpe_variance = float(np.var(sharpes.tolist(), ddof=1))

    assert result["dsr_threshold"] == 0.90
    assert result["pbo_threshold"] == 0.20
    assert result["source"] == "candidate_window_returns.csv"
    assert result["rho_bar"] == pytest.approx(rho_bar)
    assert result["effective_trial_count"] == pytest.approx(n_eff)
    assert result["sharpe_variance"] == pytest.approx(sharpe_variance)
    assert result["benchmark_effective"] == pytest.approx(
        expected_max_sharpe(n_eff, sharpe_variance)
    )
    assert result["benchmark_nominal"] == pytest.approx(expected_max_sharpe(41.0, sharpe_variance))
    assert result["pbo"] == pytest.approx(pbo(matrix.tolist(), n_splits=8))
    assert result["pbo_diagnostic_ok"] == (Decimal(str(result["pbo"])) <= Decimal("0.20"))

    first_values = matrix[:, 0]
    standardized = (first_values - first_values.mean()) / first_values.std(ddof=1)
    first = result["candidates"][names[0]]
    expected_effective = deflated_sharpe_ratio(first_values.tolist(), n_eff, sharpe_variance)
    expected_nominal = deflated_sharpe_ratio(first_values.tolist(), 41.0, sharpe_variance)
    assert set(first) == {
        "dsr_diagnostic_ok",
        "dsr_effective",
        "dsr_nominal",
        "kurtosis",
        "sample_count",
        "sharpe",
        "skew",
    }
    assert first["sharpe"] == pytest.approx(sharpes[0])
    assert first["dsr_effective"] == pytest.approx(expected_effective)
    assert first["dsr_nominal"] == pytest.approx(expected_nominal)
    assert first["dsr_diagnostic_ok"] == (Decimal(str(expected_effective)) >= Decimal("0.90"))
    assert first["skew"] == pytest.approx(float((standardized**3).mean()))
    assert first["kurtosis"] == pytest.approx(float((standardized**4).mean()))
    assert result["dsr_by_candidate"][names[0]] == pytest.approx(expected_effective)
    assert result["dsr_nominal_by_candidate"][names[0]] == pytest.approx(expected_nominal)


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

    assert result == {
        "role": "diagnostic_only",
        "status": "unavailable",
        "dsr_threshold": 0.90,
        "pbo_threshold": 0.20,
        "source": "candidate_window_returns.csv",
        "reason": "DSR/PBO diagnostics require 36 formal and five manual trials",
        "pbo": None,
        "candidates": {},
    }


@pytest.mark.parametrize(
    ("defect", "reason"),
    [
        ("metadata_object", "candidate metadata must be an object"),
        ("metadata_shape", "candidate metadata is incomplete"),
        ("formal_type", "candidate metadata is incomplete"),
        ("persisted_type", "candidate metadata is incomplete"),
        ("trials_type", "candidate metadata is incomplete"),
        ("manual_missing", "DSR/PBO diagnostics require 36 formal and five manual trials"),
        (
            "persisted_family",
            "all 36 formal candidates must share the synchronized window grid",
        ),
        ("columns", "candidate window columns disagree with the formal family"),
        ("duplicate_windows", "candidate window labels must be unique"),
        ("short_matrix", "candidate window matrix is too short or non-finite"),
        ("non_finite", "candidate window matrix is too short or non-finite"),
        ("undefined_correlation", "candidate correlations are undefined"),
        (
            "zero_sharpe_variance",
            "candidate Sharpe variance must be positive and finite",
        ),
    ],
)
def test_each_synchronized_diagnostic_guard_reports_its_exact_reason(
    tmp_path: Path,
    defect: str,
    reason: str,
) -> None:
    names = [f"v{index:02d}__train_36m" for index in range(36)]
    generator = np.random.default_rng(2026072601)
    common = generator.normal(0.2, 0.4, 8)
    frame: dict[str, object] = {"window": [f"w{index}" for index in range(8)]}
    for index, name in enumerate(names):
        frame[name] = common + generator.normal(0.0, 0.05 + index * 0.002, 8)
    metadata: object = {
        "formal_candidates": [{"candidate": name} for name in names],
        "persisted_candidates": names,
        "trial_counts": {"formal": 36, "manual": 5, "total": 41},
    }

    if defect == "metadata_object":
        metadata = []
    elif defect == "metadata_shape":
        metadata = {"formal_candidates": []}
    elif defect == "formal_type":
        cast(dict[str, Any], metadata)["formal_candidates"] = None
    elif defect == "persisted_type":
        cast(dict[str, Any], metadata)["persisted_candidates"] = None
    elif defect == "trials_type":
        cast(dict[str, Any], metadata)["trial_counts"] = None
    elif defect == "manual_missing":
        cast(dict[str, Any], metadata)["trial_counts"] = {"formal": 36}
    elif defect == "persisted_family":
        cast(dict[str, Any], metadata)["persisted_candidates"] = names[:-1]
    elif defect == "columns":
        frame.pop(names[-1])
    elif defect == "duplicate_windows":
        frame["window"] = ["w0", "w0", "w2", "w3", "w4", "w5", "w6", "w7"]
    elif defect == "short_matrix":
        frame = {key: cast(list[object], value)[:3] for key, value in frame.items()}
    elif defect == "non_finite":
        cast(NDArray[np.float64], frame[names[0]])[0] = np.nan
    elif defect == "undefined_correlation":
        frame[names[0]] = np.ones(8)
    elif defect == "zero_sharpe_variance":
        common = np.asarray([-1.0, 1.0, -2.0, 2.0, -3.0, 3.0, -4.0, 4.0])
        for name in names:
            frame[name] = common.copy()

    pd.DataFrame(frame).to_csv(tmp_path / "candidate_window_returns.csv", index=False)
    (tmp_path / "candidate_metadata.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    with np.errstate(divide="ignore", invalid="ignore"):
        result = synchronized_overfitting_diagnostics(tmp_path)

    assert result["status"] == "unavailable"
    assert result["reason"] == reason


def test_diagnostic_threshold_labels_are_inclusive(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    names = [f"v{index:02d}__train_36m" for index in range(36)]
    generator = np.random.default_rng(2026072602)
    frame: dict[str, object] = {"window": [f"w{index}" for index in range(8)]}
    for index, name in enumerate(names):
        frame[name] = generator.normal(0.1 + index * 0.001, 0.5, 8)
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
    monkeypatch.setattr(overfitting, "deflated_sharpe_ratio", lambda *_args: 0.90)
    monkeypatch.setattr(overfitting, "pbo", lambda *_args, **_kwargs: 0.20)

    result = synchronized_overfitting_diagnostics(tmp_path)

    assert result["status"] == "available"
    assert result["pbo_diagnostic_ok"] is True
    assert all(
        candidate["dsr_diagnostic_ok"] is True for candidate in result["candidates"].values()
    )


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

    assert result["status"] == "available", result
    assert result["pbo_split_count"] == expected_splits


def test_family_evidence_loader_requires_edge_lineage_and_shared_identity(
    tmp_path: Path,
) -> None:
    run = _write_family_payloads(tmp_path, _family_payloads())

    evidence, spa, romano_wolf, mcs = _load_selection_evidence(cast(rb.RunDir, run))

    assert evidence == SelectionEvidence(
        family=frozenset({"candidate__train_36m"}),
        spa_passes=True,
        romano_wolf_eligible=frozenset({"candidate__train_36m"}),
        mcs_members=frozenset({"candidate__train_36m"}),
    )
    assert spa.selected.block_length == romano_wolf.block_length == mcs.block_length == 1
    assert spa.replications == romano_wolf.replications == mcs.replications == 99
    assert spa.seed == romano_wolf.seed == mcs.seed == 20260719
    assert spa.observation_count == romano_wolf.observation_count == mcs.observation_count == 120


@pytest.mark.parametrize(
    ("artifact", "payload", "message"),
    [
        ("spa.json", [], "family evidence is invalid: SPA evidence must be an object"),
        (
            "romano_wolf.json",
            [],
            "family evidence is invalid: Romano-Wolf evidence must be an object",
        ),
        ("mcs.json", [], "family evidence is invalid: MCS evidence must be an object"),
    ],
)
def test_family_evidence_loader_rejects_non_objects_with_exact_reason(
    tmp_path: Path,
    artifact: str,
    payload: object,
    message: str,
) -> None:
    payloads: dict[str, object] = dict(_family_payloads())
    payloads[artifact] = payload
    run = _write_family_payloads(tmp_path, payloads)

    with pytest.raises(NoAutomaticSelection) as raised:
        _load_selection_evidence(cast(rb.RunDir, run))

    assert str(raised.value) == message


@pytest.mark.parametrize("mismatched_artifact", ["romano_wolf.json", "mcs.json"])
def test_family_evidence_loader_rejects_each_candidate_family_mismatch(
    tmp_path: Path,
    mismatched_artifact: str,
) -> None:
    payloads = _family_payloads()
    payloads[mismatched_artifact] = _family_payloads("other__train_36m")[mismatched_artifact]
    run = _write_family_payloads(tmp_path, payloads)

    with pytest.raises(NoAutomaticSelection) as raised:
        _load_selection_evidence(cast(rb.RunDir, run))

    assert (
        str(raised.value)
        == "SPA, Romano-Wolf, and MCS candidate families must be complete and identical"
    )


@pytest.mark.parametrize("defect", ["candidate_count", "sensitivity_family", "empty_family"])
def test_family_evidence_loader_rejects_each_spa_completeness_defect(
    tmp_path: Path,
    defect: str,
) -> None:
    payloads = _family_payloads()
    spa = payloads["spa.json"]
    if defect == "candidate_count":
        spa["candidate_count"] = 2
    elif defect == "sensitivity_family":
        sensitivity = cast(dict[str, dict[str, Any]], spa["sensitivity"])
        sensitivity["5"]["candidate_statistics"] = {"other__train_36m": 2.0}
    else:
        selected = cast(dict[str, Any], spa["selected"])
        selected["candidate_statistics"] = {}
        sensitivity = cast(dict[str, dict[str, Any]], spa["sensitivity"])
        for result in sensitivity.values():
            result["candidate_statistics"] = {}
    run = _write_family_payloads(tmp_path, payloads)

    with pytest.raises(NoAutomaticSelection) as raised:
        _load_selection_evidence(cast(rb.RunDir, run))

    assert (
        str(raised.value)
        == "SPA, Romano-Wolf, and MCS candidate families must be complete and identical"
    )


@pytest.mark.parametrize("mismatched_artifact", ["romano_wolf.json", "mcs.json"])
def test_family_evidence_loader_rejects_each_resampling_identity_mismatch(
    tmp_path: Path,
    mismatched_artifact: str,
) -> None:
    payloads = _family_payloads()
    payloads[mismatched_artifact]["block_length"] = 2
    run = _write_family_payloads(tmp_path, payloads)

    with pytest.raises(NoAutomaticSelection) as raised:
        _load_selection_evidence(cast(rb.RunDir, run))

    assert str(raised.value) == "SPA, Romano-Wolf, and MCS resampling identities must agree"


def test_spa_failure_blocks_selection_despite_diagnostics_and_returns() -> None:
    rows = [("baseline", 36, 100.0, 10.0, True)]

    with pytest.raises(NoAutomaticSelection) as raised:
        choose_automatic_candidate(
            _ranking(rows),
            evidence=_evidence(rows, spa_passes=False),
            complexity_scores={"baseline": 3},
        )

    assert str(raised.value) == "SPA family gate failed at p > 0.05"


@pytest.mark.parametrize(
    ("romano_wolf", "mcs", "complete", "frac_positive", "mean_rpd", "criterion"),
    [
        (
            set(),
            None,
            True,
            1.0,
            1.0,
            "automatic eligibility is empty after criterion: Romano-Wolf adjusted p <= 0.05",
        ),
        (
            None,
            set(),
            True,
            1.0,
            1.0,
            "automatic eligibility is empty after criterion: 90% MCS membership",
        ),
        (
            None,
            None,
            False,
            1.0,
            1.0,
            "automatic eligibility is empty after criterion: completeness",
        ),
        (
            None,
            None,
            True,
            0.89,
            1.0,
            "automatic eligibility is empty after criterion: positive-market fraction >= 90%",
        ),
        (
            None,
            None,
            True,
            1.0,
            0.84,
            "automatic eligibility is empty after criterion: mean return/drawdown >= 85% of best",
        ),
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
    if "return/drawdown" in criterion:
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

    with pytest.raises(NoAutomaticSelection) as raised:
        choose_automatic_candidate(
            ranking,
            evidence=evidence,
            complexity_scores=(
                {"baseline": 3, "no_confirms": 0}
                if "no_confirms" in set(ranking["variation"])
                else {"baseline": 3}
            ),
        )

    assert str(raised.value) == criterion


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


@pytest.mark.parametrize(
    ("raw", "variations", "message"),
    [
        (
            {"baseline": 3},
            {"baseline", "no_confirms"},
            "complexity configuration must match the candidate variations exactly "
            "(missing=['no_confirms'], extra=[])",
        ),
        (
            {"baseline": 3, "unused": 0},
            {"baseline"},
            "complexity configuration must match the candidate variations exactly "
            "(missing=[], extra=['unused'])",
        ),
        (
            {"baseline": True},
            {"baseline"},
            "complexity score for 'baseline' must be a non-negative integer",
        ),
        (
            {"baseline": "3"},
            {"baseline"},
            "complexity score for 'baseline' must be a non-negative integer",
        ),
        (
            {"baseline": -1},
            {"baseline"},
            "complexity score for 'baseline' must be a non-negative integer",
        ),
    ],
)
def test_complexity_configuration_fails_closed_with_exact_reason(
    raw: dict[str, object],
    variations: set[str],
    message: str,
) -> None:
    with pytest.raises(NoAutomaticSelection) as raised:
        _validated_complexity_scores(raw, variations)

    assert str(raised.value) == message


def test_selection_rejects_missing_columns_with_exact_reason() -> None:
    rows = [("baseline", 36, 1.0, 1.0, True)]
    ranking = _ranking(rows).drop(columns=["mean_ret"])

    with pytest.raises(NoAutomaticSelection) as raised:
        choose_automatic_candidate(
            ranking,
            evidence=_evidence(rows),
            complexity_scores={"baseline": 3},
        )

    assert str(raised.value) == "ranking is missing columns: ['mean_ret']"


def test_selection_rejects_an_empty_ranking_with_exact_reason() -> None:
    ranking = _ranking([("baseline", 36, 1.0, 1.0, True)]).iloc[0:0]

    with pytest.raises(NoAutomaticSelection) as raised:
        choose_automatic_candidate(
            ranking,
            evidence=SelectionEvidence(frozenset(), True, frozenset(), frozenset()),
            complexity_scores={},
        )

    assert str(raised.value) == "ranking contains no candidates"


def test_selection_rejects_malformed_candidate_identity_with_exact_reason() -> None:
    rows = [("baseline", 36, 1.0, 1.0, True)]
    ranking = _ranking(rows)
    ranking["train_months"] = pd.Series(["not-an-integer"], dtype=object)

    with pytest.raises(NoAutomaticSelection) as raised:
        choose_automatic_candidate(
            ranking,
            evidence=_evidence(rows),
            complexity_scores={"baseline": 3},
        )

    assert str(raised.value) == "ranking candidate identities are malformed"


def test_selection_rejects_duplicate_candidate_identity_with_exact_reason() -> None:
    rows = [
        ("baseline", 36, 1.0, 1.0, True),
        ("baseline", 36, 2.0, 1.0, True),
    ]

    with pytest.raises(NoAutomaticSelection) as raised:
        choose_automatic_candidate(
            _ranking(rows),
            evidence=_evidence(rows),
            complexity_scores={"baseline": 3},
        )

    assert str(raised.value) == "ranking candidate identities must be unique"


@pytest.mark.parametrize(
    ("evidence", "message"),
    [
        (
            SelectionEvidence(
                family=frozenset({_candidate("no_confirms", 36)}),
                spa_passes=True,
                romano_wolf_eligible=frozenset(),
                mcs_members=frozenset(),
            ),
            "ranking and statistical evidence candidate families disagree",
        ),
        (
            SelectionEvidence(
                family=frozenset({_candidate("baseline", 36)}),
                spa_passes=True,
                romano_wolf_eligible=frozenset({"unknown"}),
                mcs_members=frozenset(),
            ),
            "Romano-Wolf evidence contains an unknown candidate",
        ),
        (
            SelectionEvidence(
                family=frozenset({_candidate("baseline", 36)}),
                spa_passes=True,
                romano_wolf_eligible=frozenset(),
                mcs_members=frozenset({"unknown"}),
            ),
            "MCS evidence contains an unknown candidate",
        ),
    ],
)
def test_selection_rejects_invalid_family_evidence_with_exact_reason(
    evidence: SelectionEvidence,
    message: str,
) -> None:
    with pytest.raises(NoAutomaticSelection) as raised:
        choose_automatic_candidate(
            _ranking([("baseline", 36, 1.0, 1.0, True)]),
            evidence=evidence,
            complexity_scores={"baseline": 3},
        )

    assert str(raised.value) == message


def test_selection_rejects_non_boolean_completeness_with_exact_reason() -> None:
    rows = [("baseline", 36, 1.0, 1.0, True)]
    ranking = _ranking(rows)
    ranking["complete"] = pd.Series([1], dtype=object)

    with pytest.raises(NoAutomaticSelection) as raised:
        choose_automatic_candidate(
            ranking,
            evidence=_evidence(rows),
            complexity_scores={"baseline": 3},
        )

    assert str(raised.value) == "ranking completeness flags must be boolean"


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        (
            "frac_positive",
            True,
            "positive-market fraction must be a finite decimal",
        ),
        (
            "mean_rpd",
            "not-a-decimal",
            "mean return/drawdown must be a finite decimal",
        ),
        (
            "mean_ret",
            "not-a-decimal",
            "mean net return must be a finite decimal",
        ),
    ],
)
def test_selection_rejects_invalid_decimal_inputs_with_exact_reason(
    column: str,
    value: object,
    message: str,
) -> None:
    rows = [("baseline", 36, 1.0, 1.0, True)]
    ranking = _ranking(rows)
    ranking[column] = pd.Series([value], dtype=object)

    with pytest.raises(NoAutomaticSelection) as raised:
        choose_automatic_candidate(
            ranking,
            evidence=_evidence(rows),
            complexity_scores={"baseline": 3},
        )

    assert str(raised.value) == message


def test_selection_rejects_unsupported_training_length_with_exact_reason() -> None:
    rows = [("baseline", 12, 1.0, 1.0, True)]

    with pytest.raises(NoAutomaticSelection) as raised:
        choose_automatic_candidate(
            _ranking(rows),
            evidence=_evidence(rows),
            complexity_scores={"baseline": 3},
        )

    assert str(raised.value) == "unsupported training length 12; expected 36, 24, or 18"


def test_return_drawdown_floor_is_multiplicative_and_uses_all_candidates() -> None:
    rows = [
        ("baseline", 36, 1.0, 1.0, True),
        ("no_confirms", 36, 2.0, 2.0, True),
    ]
    eligible = {_candidate("baseline", 36)}

    with pytest.raises(NoAutomaticSelection) as raised:
        choose_automatic_candidate(
            _ranking(rows),
            evidence=_evidence(rows, romano_wolf=eligible, mcs=eligible),
            complexity_scores={"baseline": 3, "no_confirms": 0},
        )

    assert (
        str(raised.value) == "automatic eligibility is empty after criterion: "
        "mean return/drawdown >= 85% of best"
    )


def test_selected_candidate_records_the_complete_identity() -> None:
    rows = [("no_confirms", 36, 1.0, 1.0, True)]

    selected = choose_automatic_candidate(
        _ranking(rows),
        evidence=_evidence(rows),
        complexity_scores={"no_confirms": 0},
    )

    assert selected == AutomaticCandidate(
        variation="no_confirms",
        train_months=36,
        candidate_id="no_confirms__train_36m",
        complexity=0,
    )
