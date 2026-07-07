"""Tests for the research-explorer data helpers."""

from pathlib import Path

import pandas as pd

from qplus.monitoring.research import METRICS, latest_study_csv, load_study, variant_ranking


def _study(tmp: Path) -> Path:
    df = pd.DataFrame(
        {
            "instrument": ["XAUUSD", "EURUSD", "XAUUSD", "EURUSD"],
            "variation": ["a", "a", "b", "b"],
            "train_months": [36, 36, 36, 36],
            "return_per_dd": [2.0, 1.0, 3.0, 3.0],
            "error": [None, None, None, "boom"],  # last row failed -> dropped
        }
    )
    p = tmp / "study.csv"
    df.to_csv(p, index=False)
    return p


def test_load_study_drops_errored_rows(tmp_path: Path) -> None:
    df = load_study(_study(tmp_path))
    assert len(df) == 3  # the errored row is gone
    assert "error" not in df.columns


def test_variant_ranking_orders_by_metric(tmp_path: Path) -> None:
    df = load_study(_study(tmp_path))
    rank = variant_ranking(df, train_months=36, metric_col="return_per_dd")
    # variation a: mean(2,1)=1.5; variation b: mean(3)=3.0 -> b first
    assert list(rank["variation"]) == ["b", "a"]
    assert abs(rank.iloc[0]["return_per_dd"] - 3.0) < 1e-9


def test_latest_study_csv_finds_the_run(tmp_path: Path) -> None:
    (tmp_path / "study" / "run_2026").mkdir(parents=True)
    csv = tmp_path / "study" / "run_2026" / "study.csv"
    csv.write_text("x\n")
    assert latest_study_csv(tmp_path) == csv
    assert latest_study_csv(tmp_path / "nope") is None


def test_metrics_reference_frozen_columns() -> None:
    # The metric columns the explorer offers must exist in the study output.
    assert METRICS["Return / drawdown"][0] == "return_per_dd"
