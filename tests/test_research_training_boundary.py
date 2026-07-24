"""Training-window configs must not realize an artificial engine-stop exit."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from decimal import Decimal
from typing import Any, cast

import pandas as pd
import pytest
from research.engine import walkforward_runner
from research.engine.recipe import SweepRecipe
from research.engine.walkforward import WalkForwardResult, WalkForwardWindow
from research.portfolio import trades


class _CapturingRecipe:
    CSV_PATH = "unused.csv"
    PARAM_GRID = {"candidate": [1, 2]}
    start_balance = Decimal("100000")

    def __init__(self) -> None:
        self.training_params: list[dict[str, Any]] = []

    def build_run_config(
        self,
        params: dict[str, Any],
        *,
        start: str | None = None,
        end: str | None = None,
        trade_from: str | None = None,
    ) -> object:
        assert start is not None
        assert end is not None
        assert trade_from is not None
        self.training_params.append(dict(params))
        return object()


def _window() -> WalkForwardWindow:
    return WalkForwardWindow(
        train_start=pd.Timestamp("2020-01-01", tz="UTC"),
        train_end=pd.Timestamp("2021-01-01", tz="UTC"),
        test_start=pd.Timestamp("2021-01-08", tz="UTC"),
        test_end=pd.Timestamp("2021-07-08", tz="UTC"),
    )


def _successful_training_run(
    _config: object,
    *,
    closed_from: pd.Timestamp | None = None,
) -> tuple[list[float], float]:
    assert closed_from == _window().train_start
    return [100.0], 100_000.0


def test_portfolio_training_configs_do_not_flatten_on_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recipe = _CapturingRecipe()
    monkeypatch.setattr(trades, "extract_trade_pnls", _successful_training_run)

    trades._optimize(
        cast(SweepRecipe, recipe),
        [{"candidate": 1}, {"candidate": 2}],
        _window(),
    )

    assert len(recipe.training_params) == 2
    assert all(params["flatten_on_stop"] is False for params in recipe.training_params)


def test_walkforward_training_configs_do_not_flatten_on_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recipe = _CapturingRecipe()
    window = _window()
    monkeypatch.setattr(
        walkforward_runner,
        "_data_span",
        lambda _path: (window.train_start, window.test_end),
    )
    monkeypatch.setattr(
        walkforward_runner,
        "walk_forward_windows",
        lambda *_args, **_kwargs: [window],
    )
    monkeypatch.setattr(
        walkforward_runner,
        "split_windows",
        lambda windows, _end, _holdout_months: (windows, []),
    )
    monkeypatch.setattr(walkforward_runner, "extract_trade_pnls", _successful_training_run)

    def exercise_training_optimizer(
        _recipe: Any,
        windows: Sequence[WalkForwardWindow],
        _combos: Sequence[Mapping[str, Any]],
        optimize: Callable[[WalkForwardWindow], tuple[dict[str, Any], float]],
        *,
        collect_matrix: bool = False,
    ) -> list[WalkForwardResult]:
        assert not collect_matrix
        for item in windows:
            optimize(item)
        return []

    monkeypatch.setattr(
        walkforward_runner,
        "continuous_walk_forward",
        exercise_training_optimizer,
    )

    assert walkforward_runner.run_walkforward(recipe) == []
    assert len(recipe.training_params) == 2
    assert all(params["flatten_on_stop"] is False for params in recipe.training_params)
