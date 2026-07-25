"""Stage 1 must select on one realized-at-close net-R stream."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from types import TracebackType
from typing import Any, Self

import numpy as np
import pandas as pd
import pytest
from core import broker as broker_module
from core.broker import TTP_MARKETS, BrokerProfile, SwapSpec, dump_swap_snapshot
from core.instruments import us30
from research.engine import characterize, continuous, recipe
from research.engine.montecarlo import equity_curve, max_drawdown
from research.engine.overfitting import sharpe_ratio
from research.engine.walkforward import (
    WalkForwardResult,
    WalkForwardWindow,
    calmar_score,
    normalized_wfe,
    walk_forward_efficiency,
)
from research.portfolio import trades
from research.stages import lineage

from tests.helpers.mt5_fixture import write_mt5_csv


def _ns(when: str) -> int:
    return int(pd.Timestamp(when, tz="UTC").value)


def _positions(
    *,
    opened: Sequence[str],
    closed: Sequence[str],
    side: str = "LONG",
    pnl: str = "1_000 USD",
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts_opened": [pd.Timestamp(value, tz="UTC") for value in opened],
            "ts_closed": [pd.Timestamp(value, tz="UTC") for value in closed],
            "realized_pnl": [pnl] * len(opened),
            "avg_px_open": [40_000.0] * len(opened),
            "avg_px_close": [40_100.0 if side == "LONG" else 39_900.0] * len(opened),
            "side": [side] * len(opened),
        }
    )


class _Recipe:
    INSTRUMENT = us30()
    start_balance = Decimal("100000")
    base_risk_frac = Decimal("0.01")

    def __init__(self, swap_spec: SwapSpec) -> None:
        self.broker = TTP_MARKETS.with_swaps({"US30": swap_spec})


def _negative_points_swap() -> SwapSpec:
    return SwapSpec(
        mode="POINTS",
        swap_long=-50.0,
        swap_short=-50.0,
        rollover_py=2,
        tick_value=1.0,
        tick_size=0.01,
    )


def test_equal_gross_candidates_rank_by_net_overnight_duration() -> None:
    """Holding longer cannot tie a same-gross candidate when carry is negative."""
    recipe_ = _Recipe(_negative_points_swap())
    opened = ["2024-01-08 12:00"] * 10
    short_holds = _positions(
        opened=opened,
        closed=["2024-01-08 16:00"] * 10,
    )
    long_holds = _positions(
        opened=opened,
        closed=["2024-01-15 16:00"] * 10,
    )

    short = continuous.stage1_trade_returns(short_holds, recipe_, 1.0)
    long = continuous.stage1_trade_returns(long_holds, recipe_, 1.0)

    assert short["r"].tolist() == long["r"].tolist() == [pytest.approx(1.0)] * 10
    assert (long["swap_r"] < short["swap_r"]).all()
    short_score = calmar_score(continuous.stage1_account_returns(short, recipe_), 1.0)
    long_score = calmar_score(continuous.stage1_account_returns(long, recipe_), 1.0)
    assert short_score > long_score


def test_positive_short_index_carry_is_a_credit() -> None:
    spec = SwapSpec(
        mode="INT_CURRENT",
        swap_long=-6.93,
        swap_short=2.68,
        rollover_py=4,
        tick_value=0.0087,
        tick_size=0.01,
    )
    frame = continuous.stage1_trade_returns(
        _positions(
            opened=["2024-01-08 12:00"],
            closed=["2024-01-09 12:00"],
            side="SHORT",
        ),
        _Recipe(spec),
        1.0,
    )

    assert frame.loc[0, "r"] == pytest.approx(1.0), "gross price R must remain unchanged"
    assert frame.loc[0, "swap_r"] > 0
    assert frame.loc[0, "net_r"] == pytest.approx(
        frame.loc[0, "r"] + frame.loc[0, "swap_r"]
    )
    assert frame.loc[0, "net_r"] > frame.loc[0, "r"]


def _window(test_start: str, test_end: str) -> WalkForwardWindow:
    start = pd.Timestamp(test_start, tz="UTC")
    end = pd.Timestamp(test_end, tz="UTC")
    return WalkForwardWindow(start - pd.DateOffset(months=12), start, start, end)


def test_swap_is_realized_once_in_the_close_owning_window() -> None:
    recipe_ = _Recipe(_negative_points_swap())
    frame = continuous.stage1_trade_returns(
        _positions(
            opened=["2024-01-10 12:00"],
            closed=["2024-07-10 12:00"],
        ),
        recipe_,
        1.0,
    )
    events = continuous.stage1_close_events(frame, recipe_)
    windows = [
        _window("2024-01-01", "2024-07-01"),
        _window("2024-07-01", "2025-01-01"),
    ]

    first, second = continuous.window_returns(events, windows, basis=1.0)

    assert first == (0.0, []), "neither gross return nor swap is marked while the trade is open"
    assert len(events) == len(frame) == len(second[1]) == 1
    assert second[1][0] == pytest.approx(
        float(frame.loc[0, "net_r"]) * float(recipe_.base_risk_frac)
    )


def test_one_net_fixture_feeds_every_stage_one_summary_and_ranking_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Window return, DD, WFE, Sharpe, and persisted ranking must not split gross/net."""
    recipe_ = _Recipe(_negative_points_swap())
    frame = continuous.stage1_trade_returns(
        _positions(
            opened=["2024-01-08 12:00", "2024-07-08 12:00"],
            closed=["2024-01-15 12:00", "2024-07-15 12:00"],
        ),
        recipe_,
        1.0,
    )
    windows = [
        _window("2024-01-01", "2024-07-01"),
        _window("2024-07-01", "2025-01-01"),
    ]
    attributed = continuous.window_returns(
        continuous.stage1_close_events(frame, recipe_),
        windows,
        basis=1.0,
    )
    results = [
        WalkForwardResult(
            window=window.label,
            best_params={"stop_loss_pct": 1.0},
            is_return=window_return * 2.0,
            oos_return=window_return,
            oos_trades=len(trade_returns),
            oos_max_dd=max_drawdown(equity_curve(trade_returns, 1.0)),
            oos_returns=trade_returns,
            oos_by_combo={"stop_loss_pct=1.0": window_return},
        )
        for window, (window_return, trade_returns) in zip(windows, attributed, strict=True)
    ]
    monkeypatch.setattr(characterize, "run_walkforward", lambda *_args, **_kwargs: results)

    row = characterize._run_task(
        us30,
        "unused.csv",
        15.0,
        {"stop_loss_pct": [1.0]},
        "baseline",
        {},
        "US30",
        12,
        6,
        6,
        None,
        0,
        0,
        100_000.0,
        recipe_.broker,
    )
    net_windows = [result.oos_return for result in results]
    expected_mean = sum(net_windows) / len(net_windows)
    expected_dd = sum(result.oos_max_dd for result in results) / len(results)

    assert row["window_oos"] == net_windows
    assert row["mean_oos_pct"] == round(expected_mean * 100, 2)
    assert row["oos_maxdd_pct"] == round(expected_dd * 100, 2)
    assert row["return_per_dd"] == round(expected_mean / max(expected_dd, 0.005), 3)
    assert row["wfe"] == round(walk_forward_efficiency(results), 3)
    assert row["wfe_norm"] == round(normalized_wfe(results, 12, 6), 3)
    assert list(row["combo_oos"].values())[0] == {
        result.window: result.oos_return for result in results
    }

    characterize._save_csv([row], tmp_path / "study.csv")
    monkeypatch.setattr(characterize, "_plot_heatmap", lambda *_args: None)
    characterize._write_reports([row], tmp_path, n_trials=1)
    study = pd.read_csv(tmp_path / "study.csv").iloc[0]
    ranking = pd.read_csv(tmp_path / "ranking.csv").iloc[0]

    assert float(study["mean_oos_pct"]) == pytest.approx(row["mean_oos_pct"])
    assert float(study["return_per_dd"]) == pytest.approx(row["return_per_dd"])
    assert float(ranking["oos_sharpe"]) == pytest.approx(sharpe_ratio(net_windows), abs=1e-4)


class _ImmediateFuture:
    def __init__(self, function: Callable[..., Any], args: tuple[Any, ...]) -> None:
        try:
            self._result = function(*args)
            self._error: BaseException | None = None
        except BaseException as exc:  # production catches a worker's exception through result()
            self._result = None
            self._error = exc

    def result(self) -> Any:
        if self._error is not None:
            raise self._error
        return self._result


class _InlineExecutor:
    def __init__(self, *, max_workers: int) -> None:
        assert max_workers == 1

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    def submit(self, function: Callable[..., Any], *args: Any) -> _ImmediateFuture:
        return _ImmediateFuture(function, args)


class _Clock:
    values: Iterable[datetime] = iter(())

    @classmethod
    def now(cls) -> datetime:
        return next(iter(cls.values))


def _study_config(path: Path, csv: Path) -> Path:
    path.write_text(
        "\n".join(
            (
                "from core.instruments import us30",
                "from research.portfolio.risk import AccountProfile",
                f"INSTRUMENTS = [(us30, {str(csv)!r}, 15.0)]",
                "VARIATIONS = {'baseline': {}}",
                "PARAM_GRID = {'stop_loss_pct': [1.0], 'take_profit_pct': [2.0]}",
                "TRAIN_MONTHS = [12]",
                "TEST_MONTHS = 6",
                "STEP_MONTHS = 6",
                "HOLDOUT_MONTHS = 0",
                "EMBARGO_DAYS = 0",
                "MAX_WORKERS = 1",
                "ACCOUNT = AccountProfile(start_balance=100_000.0)",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _configure_inline_study(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, BrokerProfile]:
    monkeypatch.setattr(recipe, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(characterize, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(lineage, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(broker_module, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(characterize, "ProcessPoolExecutor", _InlineExecutor)
    monkeypatch.setattr(characterize, "as_completed", lambda futures: list(futures))
    monkeypatch.setattr(characterize, "_write_reports", lambda *_args: None)
    csv = write_mt5_csv(tmp_path / "data" / "SYN_H4.csv")
    cfg = _study_config(tmp_path / "study_config.py", csv)
    broker = TTP_MARKETS.with_swaps({"US30": _negative_points_swap()})
    monkeypatch.setattr(characterize, "standard_broker", lambda: broker, raising=False)
    return cfg, broker


def test_characterize_cli_study_csv_changes_under_large_swap(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The actual CLI/worker path must consume swap; a helper-only test cannot prove that."""
    cfg, _broker = _configure_inline_study(tmp_path, monkeypatch)
    _Clock.values = iter((datetime(2026, 1, 1, 0, 0), datetime(2026, 1, 1, 0, 1)))
    monkeypatch.setattr(characterize, "datetime", _Clock)

    monkeypatch.setattr(
        continuous,
        "swap_r_per_trade",
        lambda frame, spec: np.zeros(len(frame), dtype=float),
        raising=False,
    )
    characterize.main([str(cfg), "1"])
    gross = pd.read_csv(tmp_path / "reports/research/study_20260101_0000/study.csv")

    monkeypatch.setattr(
        continuous,
        "swap_r_per_trade",
        lambda frame, spec: np.full(len(frame), -0.50, dtype=float),
        raising=False,
    )
    characterize.main([str(cfg), "1"])
    net = pd.read_csv(tmp_path / "reports/research/study_20260101_0001/study.csv")

    assert not gross["mean_oos_pct"].equals(net["mean_oos_pct"])
    assert float(net.loc[0, "mean_oos_pct"]) < float(gross.loc[0, "mean_oos_pct"])
    assert float(net.loc[0, "return_per_dd"]) < float(gross.loc[0, "return_per_dd"])


def test_generated_study_lineage_hash_changes_with_swap_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg, broker = _configure_inline_study(tmp_path, monkeypatch)
    snapshot = tmp_path / "core/config/broker/ttp_markets_swaps.json"
    monkeypatch.setattr(lineage, "swap_snapshot_path", lambda _name: snapshot)
    monkeypatch.setattr(
        lineage,
        "catalog_inputs",
        lambda instruments=None: {
            "catalog_frame": {"path": "catalog/.timestamp_frame", "sha256": "fixture"},
            "catalog_sources": {"US30.SIM": "fixture"},
        },
    )
    monkeypatch.setattr(
        characterize,
        "seeded_instruments",
        lambda _catalog, sources: set(sources),
    )
    monkeypatch.setattr(
        characterize,
        "_run_task",
        lambda *_args: {
            "instrument": "US30",
            "variation": "baseline",
            "train_months": 12,
            "windows": 1,
            "mean_oos_pct": 1.0,
            "oos_maxdd_pct": 0.5,
            "return_per_dd": 2.0,
            "pct_profitable": 100.0,
            "wfe": 1.0,
            "wfe_norm": 2.0,
                "oos_trades": 10,
                "window_oos": [0.01],
                "combo_oos": {},
                "candidate_windows": [
                    {
                        "window": "2025-01..2025-07",
                        "test_start_ns": int(pd.Timestamp("2025-01-01", tz="UTC").value),
                        "test_end_ns": int(pd.Timestamp("2025-07-01", tz="UTC").value),
                        "net_r_events": [
                            (
                                int(pd.Timestamp("2025-03-01", tz="UTC").value),
                                1.0,
                            )
                        ],
                    }
                ],
            },
        )
    _Clock.values = iter((datetime(2026, 1, 2, 0, 0), datetime(2026, 1, 2, 0, 1)))
    monkeypatch.setattr(characterize, "datetime", _Clock)

    dump_swap_snapshot(dict(broker.swap_specs), snapshot)
    characterize.main([str(cfg), "1"])
    first = json.loads(
        (tmp_path / "reports/research/study_20260102_0000/_provenance.json").read_text(
            encoding="utf-8"
        )
    )

    changed = SwapSpec(
        mode="POINTS",
        swap_long=-51.0,
        swap_short=-50.0,
        rollover_py=2,
        tick_value=1.0,
        tick_size=0.01,
    )
    dump_swap_snapshot({"US30": changed}, snapshot)
    characterize.main([str(cfg), "1"])
    second = json.loads(
        (tmp_path / "reports/research/study_20260102_0001/_provenance.json").read_text(
            encoding="utf-8"
        )
    )

    key = "swap_snapshot:ttp_markets_swaps"
    assert first["inputs"][key]["sha256"] != second["inputs"][key]["sha256"]


def test_fixed_stage_three_bypasses_net_training_optimizer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """P-01 may change training selection but not the frozen Stage-3 trade stream."""

    class _FixedRecipe:
        CSV_PATH = "unused.csv"
        PARAM_GRID = {"stop_loss_pct": [1.0], "take_profit_pct": [2.0]}
        INSTRUMENT = us30()
        start_balance = 100_000.0
        base_risk_frac = 0.01
        base_config: Mapping[str, Any] = {}

    window = _window("2024-01-01", "2024-07-01")
    monkeypatch.setattr(trades, "_data_span", lambda _path: (window.train_start, window.test_end))
    monkeypatch.setattr(trades, "walk_forward_windows", lambda *_args, **_kwargs: [window])
    monkeypatch.setattr(
        trades,
        "_optimize",
        lambda *_args, **_kwargs: pytest.fail("fixed Stage 3 must not re-optimize"),
    )
    monkeypatch.setattr(
        trades,
        "run_continuous_oos",
        lambda *_args, **_kwargs: pd.DataFrame(
            columns=[
                "ts_opened",
                "ts_closed",
                "realized_pnl",
                "avg_px_open",
                "avg_px_close",
                "side",
            ]
        ),
    )

    result = trades.extract_market_trades(
        _FixedRecipe(),  # type: ignore[arg-type]
        train_months=12,
        test_months=6,
        step_months=6,
        fixed_params={"stop_loss_pct": 1.0, "take_profit_pct": 2.0},
    )

    assert list(result.columns) == list(trades._COLUMNS)
    assert "swap_r" not in result and "net_r" not in result
