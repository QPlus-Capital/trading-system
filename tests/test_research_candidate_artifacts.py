"""Canonical pre-filter candidate-return artifacts for P-03 / issue #45."""

from __future__ import annotations

import csv
import importlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
from research.config import robustness
from research.engine import characterize, continuous
from research.engine.walkforward import WalkForwardWindow
from research.portfolio.resample import select_block_length
from research.stages import lineage


def _candidate_module() -> Any:
    return importlib.import_module("research.engine.candidate_returns")


def _ns(value: str) -> int:
    return int(pd.Timestamp(value, tz="UTC").value)


def _window(
    label: str,
    start: str,
    end: str,
    events: list[tuple[str, str]],
) -> dict[str, Any]:
    return {
        "window": label,
        "test_start_ns": _ns(start),
        "test_end_ns": _ns(end),
        "net_r_events": [(_ns(timestamp), value) for timestamp, value in events],
    }


def _row(
    market: str,
    variation: str,
    train_months: int,
    windows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "instrument": market,
        "variation": variation,
        "train_months": train_months,
        "mean_oos_pct": 1.0,
        "oos_maxdd_pct": 0.5,
        "return_per_dd": 2.0,
        "pct_profitable": 100.0,
        "wfe_norm": 1.0,
        "oos_trades": sum(len(window["net_r_events"]) for window in windows),
        "window_oos": [0.01 for _ in windows],
        "combo_oos": {},
        "candidate_windows": windows,
    }


def _fixture_rows(*, omit_beta_m2: bool = False) -> list[dict[str, Any]]:
    first = _window(
        "2026-07..2026-08",
        "2026-07-01 00:00",
        "2026-08-01 00:00",
        [
            ("2026-07-01 21:14", "1.0"),
            ("2026-07-01 21:16", "-0.25"),
            ("2026-07-12 12:00", "0.125"),
        ],
    )
    second = _window(
        "2026-08..2026-09",
        "2026-08-01 00:00",
        "2026-09-01 00:00",
        [
            ("2026-08-03 12:00", "0.3333333333333333"),
            ("2026-08-17 12:00", "-0.1"),
        ],
    )
    rows: list[dict[str, Any]] = []
    for variation in ("alpha", "beta"):
        for market in ("M1", "M2"):
            if omit_beta_m2 and variation == "beta" and market == "M2":
                continue
            multiplier = Decimal("1") if market == "M1" else Decimal("0.5")
            if variation == "beta":
                multiplier *= Decimal("-0.25")
            windows = []
            for source in (first, second):
                windows.append(
                    {
                        **source,
                        "net_r_events": [
                            (timestamp, str(Decimal(value) * multiplier))
                            for timestamp, value in source["net_r_events"]
                        ],
                    }
                )
            rows.append(_row(market, variation, 18, windows))
    return rows


def _write(
    tmp_path: Path,
    rows: list[dict[str, Any]],
    *,
    variations: tuple[str, ...] = ("alpha", "beta"),
) -> dict[str, Any]:
    module = _candidate_module()
    result = module.write_candidate_artifacts(
        rows,
        tmp_path,
        variations=variations,
        train_months=(18,),
        markets=("M1", "M2"),
        manual_trials=("manual-one", "manual-two"),
        source_inputs={"config": {"path": "config.py", "sha256": "sha256:abc"}},
        hash_paths=lineage.hash_paths,
    )
    assert isinstance(result, dict)
    return dict(result)


def _wide_decimal(path: Path, index: str) -> tuple[list[str], dict[str, list[Decimal]]]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    columns = [name for name in rows[0] if name != index]
    return columns, {column: [Decimal(row[column]) for row in rows] for column in columns}


def test_production_config_defines_36_unique_formal_candidates_and_five_manual_trials() -> None:
    module = _candidate_module()

    candidates = module.candidate_definitions(
        robustness.VARIATIONS,
        robustness.TRAIN_MONTHS,
    )

    assert len(candidates) == len({candidate.candidate_id for candidate in candidates}) == 36
    assert len(robustness.MANUAL_TRIALS) == 5
    assert all(
        candidate.variation in robustness.VARIATIONS
        and candidate.train_months in robustness.TRAIN_MONTHS
        for candidate in candidates
    )


def test_daily_stream_uses_chicago_reset_and_includes_every_zero_day(tmp_path: Path) -> None:
    metadata = _write(tmp_path, _fixture_rows())
    daily = pd.read_csv(tmp_path / "candidate_daily_returns.csv", dtype=str)
    alpha = "alpha__train_18m"

    by_day = dict(zip(daily["loss_day"], daily[alpha], strict=True))

    assert Decimal(by_day["2026-07-01"]) == Decimal("1.5") * Decimal("0.0018")
    assert Decimal(by_day["2026-07-02"]) == Decimal("-0.375") * Decimal("0.0018")
    assert Decimal(by_day["2026-07-03"]) == 0
    assert metadata["loss_day_axis"] == "16:15 America/Chicago"
    expected = pd.date_range(
        metadata["common_dates"]["first"],
        metadata["common_dates"]["last"],
        freq="D",
    )
    assert len(daily) == len(expected)
    assert daily["loss_day"].tolist() == [str(value.date()) for value in expected]


def test_daily_window_and_market_window_aggregates_are_exact(tmp_path: Path) -> None:
    _write(tmp_path, _fixture_rows())
    daily_columns, daily = _wide_decimal(tmp_path / "candidate_daily_returns.csv", "loss_day")
    window_columns, windows = _wide_decimal(
        tmp_path / "candidate_window_returns.csv",
        "window",
    )
    market = list(
        csv.DictReader(
            (tmp_path / "candidate_market_window_returns.csv").open(
                newline="",
                encoding="utf-8",
            )
        )
    )

    assert daily_columns == window_columns
    for candidate in daily_columns:
        assert sum(daily[candidate], Decimal(0)) == sum(windows[candidate], Decimal(0))
        for window_index, label in enumerate(
            pd.read_csv(tmp_path / "candidate_window_returns.csv", dtype=str)["window"]
        ):
            selected = [
                row for row in market if row["candidate"] == candidate and row["window"] == label
            ]
            assert {row["market"] for row in selected} == {"M1", "M2"}
            assert (
                sum(Decimal(row["return"]) for row in selected) == windows[candidate][window_index]
            )
            assert (
                sum(Decimal(row["net_r"]) for row in selected) * Decimal("0.0018")
                == windows[candidate][window_index]
            )
            assert sum(int(row["trades"]) for row in selected) > 0


def test_incomplete_candidate_is_absent_everywhere_not_zero_filled(tmp_path: Path) -> None:
    metadata = _write(tmp_path, _fixture_rows(omit_beta_m2=True))
    beta = "beta__train_18m"

    daily = pd.read_csv(tmp_path / "candidate_daily_returns.csv", dtype=str)
    windows = pd.read_csv(tmp_path / "candidate_window_returns.csv", dtype=str)
    market = pd.read_csv(tmp_path / "candidate_market_window_returns.csv", dtype=str)

    assert beta not in daily.columns
    assert beta not in windows.columns
    assert beta not in set(market["candidate"])
    assert metadata["trial_counts"] == {
        "formal": 2,
        "manual": 2,
        "total": 4,
    }
    assert metadata["persisted_candidate_count"] == 1
    assert metadata["excluded_candidates"] == [
        {
            "candidate": beta,
            "missing_markets": ["M2"],
        }
    ]


def test_daily_csv_is_direct_input_to_p04_block_length_selection(tmp_path: Path) -> None:
    _write(tmp_path, _fixture_rows())
    daily = pd.read_csv(tmp_path / "candidate_daily_returns.csv")
    arrays = {
        column: daily[column].to_numpy(dtype=float)
        for column in daily.columns
        if column != "loss_day"
    }

    block_length = select_block_length(arrays)

    assert isinstance(block_length, int)
    assert block_length >= 1
    assert len({len(values) for values in arrays.values()}) == 1


def test_metadata_uses_lineage_hashes_and_detects_artifact_drift(tmp_path: Path) -> None:
    metadata = _write(tmp_path, _fixture_rows())
    daily = tmp_path / "candidate_daily_returns.csv"
    recorded = metadata["artifacts"]["candidate_daily_returns.csv"]

    assert recorded["sha256"] == lineage.sha256_file(daily)
    daily.write_text(daily.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    assert recorded["sha256"] != lineage.sha256_file(daily)


def test_chosen_walkforward_payload_is_the_same_p01_net_trade_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    frame = pd.DataFrame(
        {
            "ts_closed": [_ns("2026-07-02 12:00"), _ns("2026-07-03 12:00")],
            "net_r": [Decimal("1.25"), Decimal("-0.5")],
        }
    )
    monkeypatch.setattr(
        continuous,
        "closed_stage1_trade_returns",
        lambda *_args, **_kwargs: frame,
    )
    window = WalkForwardWindow(
        pd.Timestamp("2025-01-01", tz="UTC"),
        pd.Timestamp("2026-01-01", tz="UTC"),
        pd.Timestamp("2026-07-01", tz="UTC"),
        pd.Timestamp("2026-08-01", tz="UTC"),
    )
    params = {"stop_loss_pct": 1.0, "take_profit_pct": 2.0}
    recipe = SimpleNamespace(base_config=params, base_risk_frac=0.01)

    result = continuous.continuous_walk_forward(
        recipe,
        [window],
        [params],
        lambda _window: (params, 0.0),
    )[0]

    assert result.oos_net_r_events == [
        (_ns("2026-07-02 12:00"), 1.25),
        (_ns("2026-07-03 12:00"), -0.5),
    ]
    assert result.oos_return == pytest.approx((1.25 - 0.5) * 0.01)
    assert result.test_start_ns == int(window.test_start.value)
    assert result.test_end_ns == int(window.test_end.value)


def test_persistence_cannot_rewrite_existing_study_metrics(tmp_path: Path) -> None:
    rows = _fixture_rows()
    characterize._save_csv(rows, tmp_path / "study.csv")
    characterize._write_reports(rows, tmp_path, n_trials=41)
    existing = {
        name: (tmp_path / name).read_bytes()
        for name in ("study.csv", "ranking.csv", "overfitting.json")
    }

    _write(tmp_path, rows)

    assert {name: (tmp_path / name).read_bytes() for name in existing} == existing


def test_new_study_provenance_binds_candidate_artifacts_and_old_records_remain_readable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("study.csv", "ranking.csv", "overfitting.json"):
        (tmp_path / name).write_text(f"{name}\n", encoding="utf-8")
    _write(tmp_path, _fixture_rows())
    monkeypatch.setattr(
        lineage,
        "git_state",
        lambda: {"commit": "abc123", "dirty": "clean"},
    )

    lineage.write_provenance(tmp_path, {"config": {"path": "x", "sha256": "sha256:y"}})
    payload = json.loads((tmp_path / "_provenance.json").read_text(encoding="utf-8"))

    assert set(payload["artifacts"]) >= {
        "candidate_daily_returns.csv",
        "candidate_window_returns.csv",
        "candidate_market_window_returns.csv",
        "candidate_metadata.json",
    }
    (tmp_path / "candidate_window_returns.csv").write_text(
        "window,changed\n",
        encoding="utf-8",
    )
    with pytest.raises(lineage.ProvenanceMismatch):
        lineage.read_provenance(tmp_path)


def test_candidate_artifact_timestamps_are_finite_utc_instants() -> None:
    module = _candidate_module()
    event = module.CandidateEvent(
        timestamp_ns=_ns("2026-07-01 12:00"),
        net_r=Decimal("0.1"),
    )

    assert datetime.fromtimestamp(event.timestamp_ns / 1_000_000_000, tz=UTC).tzinfo is UTC
    with pytest.raises(ValueError, match="finite"):
        module.CandidateEvent(timestamp_ns=event.timestamp_ns, net_r=Decimal("NaN"))
