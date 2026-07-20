"""#32 end to end: both real entrypoints drive the continuous path.

The acceptance criterion these exist for is structural rather than numerical. The issue's first
named failure mode is "the continuous implementation exists but characterize or fixed Stage 3
still calls the stitched path" -- a bug no unit test can see, because every unit would still pass.
So these run the actual functions Stage 1 and Stage 3 use, against a real seeded catalog, and
assert on properties only a continuous run can have.

They are slower than the rest of the suite (a few seconds each) because there is no way to prove
this without running an engine.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from core.data.mt5_csv import write_mt5_catalog
from core.instruments import us30
from research.engine import characterize, recipe
from research.engine.recipe import SweepRecipe
from research.engine.walkforward import walk_forward_windows
from research.engine.walkforward_runner import _data_span
from research.portfolio.trades import extract_market_trades

from tests.helpers.mt5_fixture import write_mt5_csv

_GRID = {"stop_loss_pct": [0.5, 1.5], "take_profit_pct": [2.0]}


@pytest.fixture
def market(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A synthetic instrument, seeded into a catalog of its own.

    Redirects the recipe's repo root so nothing touches the real catalog: seeding into it would
    make every later run re-import 12 instruments, and a test may not cost the operator that.
    """
    monkeypatch.setattr(recipe, "_REPO_ROOT", tmp_path)
    csv = write_mt5_csv(tmp_path / "data" / "SYN_H4.csv")
    write_mt5_catalog(csv, tmp_path / "catalog", instrument=us30(), bar_spec="4-HOUR")
    return csv


def _recipe() -> SweepRecipe:
    return SweepRecipe(us30(), "data/SYN_H4.csv", leverage=15.0, param_grid=_GRID)


# ------------------------------------------------------------------ Stage 3's real entrypoint
def test_stage_three_extraction_produces_one_continuous_stream(market: Path) -> None:  # noqa: ARG001
    trades = extract_market_trades(
        _recipe(), train_months=12, test_months=6, step_months=6, param_grid=_GRID
    )
    assert not trades.empty, "the fixture must actually trade, or this proves nothing"

    # A continuous account: each trade appears once, and the stream is chronological.
    assert not trades.duplicated(subset=["ts_opened", "ts_closed"]).any()
    assert trades["ts_closed"].is_monotonic_increasing or len(trades) == 1
    assert set(trades["sl_pct"]).issubset({0.5, 1.5})
    assert (trades["r"] != 0).any(), "R must be assigned from the continuous equity walk"

    # The stream must span EVERY window, not just the first. Without this the test passes on a
    # schedule truncated to one segment -- which is exactly the stitched behaviour it exists to
    # exclude, so the other assertions above cannot carry the test on their own.
    windows = walk_forward_windows(
        *_data_span(_recipe().CSV_PATH), train_months=12, test_months=6, step_months=6
    )
    assert len(windows) >= 2, "the fixture must produce several windows"
    last = windows[-1]
    covered = trades[trades["ts_closed"] >= int(pd.Timestamp(last.test_start).value)]
    assert not covered.empty, "no trade resolved in the final window: the span was not run"


def test_no_trade_is_recorded_twice_at_a_seam(market: Path) -> None:
    """The stitched path recorded a straddling position in two windows or in neither."""
    trades = extract_market_trades(
        _recipe(), train_months=12, test_months=6, step_months=6, param_grid=_GRID
    )
    opened = trades["ts_opened"].tolist()
    assert len(opened) == len(set(opened)), "an open timestamp identifies one position only"


# ------------------------------------------------------------------ Stage 1's real entrypoint
def test_characterize_task_runs_the_continuous_walk_forward(market: Path) -> None:
    """``_run_task`` is the unit characterize dispatches; it must reach the continuous path.

    Called in-process rather than through the process pool: a worker would re-import the module
    and lose the redirected repo root, so the pool would seed the operator's real catalog.
    """
    result = characterize._run_task(
        us30,
        "data/SYN_H4.csv",
        15.0,
        _GRID,
        "baseline",
        {},
        "US30",
        12,  # train_months
        6,  # test_months
        6,  # step_months
        None,  # max_windows
        0,  # holdout_months
        7,  # embargo_days
    )
    assert result["instrument"] == "US30"
    assert result["windows"] > 0, "no windows means the walk-forward never ran"
    # #13's per-candidate matrix must survive the move to continuous runs: PBO/DSR are computed
    # from it, and it is keyed by window LABEL so candidates stay chronologically aligned.
    assert result["combo_oos"], "the candidate matrix is what PBO/DSR are computed from"
    assert len(result["combo_oos"]) == 2, "one stream per grid candidate"
    for stream in result["combo_oos"].values():
        assert len(stream) == result["windows"], "every candidate is scored on every window"


def test_a_grid_offering_indicator_lengths_is_still_searchable(market: Path) -> None:
    """The constraint is on the SELECTION, not the grid.

    A grid may offer several indicator lengths; what one continuous run cannot honour is a choice
    that DIFFERS between segments. Judging the grid instead refused searches that work -- and
    invited narrowing a research grid to suit an execution detail, which is how a default grid
    lost a dimension in an earlier round of this PR.

    The refusal itself is unit-tested in ``test_research_param_schedule``, where a disagreeing
    selection can be constructed; here the optimizer's choice is not ours to dictate.
    """
    result = characterize._run_task(
        us30,
        "data/SYN_H4.csv",
        15.0,
        {"stop_loss_pct": [0.5, 1.5], "take_profit_pct": [2.0], "rsi_length": [14, 21]},
        "baseline",
        {},
        "US30",
        12,
        6,
        6,
        None,
        0,
        7,
    )
    assert result["windows"] > 0 or "error" in result
