"""Tests for MT5 CSV timestamp semantics (#18).

The exported ``<DATE> <TIME>`` columns are the BROKER SERVER's wall clock, not UTC. Verified from
the data itself: the FX week starts Monday 00:00 and ends Friday 20:00 in these files, and the
week-start hour does not shift across the DST changeover -- in real UTC an EET server's week would
begin Sunday 21:00 in summer and 22:00 in winter.
"""

from pathlib import Path

import pandas as pd
import pytest
from core.data.mt5_csv import parse_mt5_timestamps


def test_the_default_converts_from_the_verified_server_zone() -> None:
    """Confirmed against the live terminal: the last tick before the weekend is Friday 23:56:59
    server time while the market closes 17:00 New York = 21:00 UTC, so 24:00 server = 21:00 UTC
    -> UTC+3 in July. With the CSV week structure that pins EET/EEST."""
    df = pd.DataFrame({"<DATE>": ["2024.07.01"], "<TIME>": ["03:00:00"]})
    assert parse_mt5_timestamps(df)[0] == pd.Timestamp("2024-07-01 00:00", tz="UTC")


def test_the_old_utc_reading_is_still_reachable_explicitly() -> None:
    # Every number produced BEFORE this fix read the stamps as UTC; keep that reproducible so an
    # old result can be recomputed and compared rather than merely disbelieved.
    df = pd.DataFrame({"<DATE>": ["2024.07.01"], "<TIME>": ["00:00:00"]})
    assert parse_mt5_timestamps(df, server_tz=None)[0] == pd.Timestamp("2024-07-01", tz="UTC")


def test_an_iana_zone_converts_dst_aware() -> None:
    # Europe/Athens is UTC+3 in July and UTC+2 in January -- a fixed hour offset cannot express
    # both, which is why the legacy server_tz_offset_hours could never have been correct.
    df = pd.DataFrame(
        {"<DATE>": ["2024.07.01", "2024.01.15"], "<TIME>": ["00:00:00", "00:00:00"]}
    )
    out = parse_mt5_timestamps(df, server_tz="Europe/Athens")
    assert out[0] == pd.Timestamp("2024-06-30 21:00", tz="UTC")  # summer: -3h
    assert out[1] == pd.Timestamp("2024-01-14 22:00", tz="UTC")  # winter: -2h


def test_the_legacy_fixed_offset_still_works() -> None:
    df = pd.DataFrame({"<DATE>": ["2024.07.01"], "<TIME>": ["03:00:00"]})
    assert parse_mt5_timestamps(df, offset_hours=3)[0] == pd.Timestamp("2024-07-01", tz="UTC")


def test_every_loader_defaults_to_the_same_frame() -> None:
    """Codex P1: the catalog seeder had its own server_tz=None default, which overrode the module
    default. Bars were then imported in the server frame while _data_span and the daily curves
    converted -- two frames in one pipeline, which drifts trades against day buckets around
    server midnight. Mixed frames are worse than no conversion, so pin the defaults together.
    """
    import inspect

    from core.data.mt5_csv import (
        MT5_SERVER_TZ,
        load_mt5_bid_ask_bars,
        parse_mt5_timestamps,
        write_mt5_catalog,
    )

    for fn in (parse_mt5_timestamps, load_mt5_bid_ask_bars, write_mt5_catalog):
        default = inspect.signature(fn).parameters["server_tz"].default
        assert default == MT5_SERVER_TZ, f"{fn.__name__} would import in a different frame"


def test_the_presence_check_itself_discards_a_stale_catalog(tmp_path: Path) -> None:
    """Codex round-5 P1: the staleness check lived only in the WRITE funnel, but the seeding
    CLIs skip the write entirely when the instrument is already present -- which it is, in
    exactly the stale case. The presence check must therefore be the gate."""
    from core.data.mt5_csv import seeded_instruments

    cat = tmp_path / "catalog"
    cat.mkdir()
    (cat / "old_frame.parquet").write_text("x", encoding="utf-8")  # unmarked -> stale
    assert seeded_instruments(cat) == set()  # nothing usable in a stale catalog
    assert not cat.exists()  # ...and it is GONE, so every caller re-seeds through the funnel
    assert seeded_instruments(cat) == set()  # absent catalog: empty, no crash


def test_build_run_config_fails_closed_on_a_stale_catalog(tmp_path: Path) -> None:
    """Stage 3 reads the catalog without ever seeding, so it never passes the write funnel.
    The backtest-config builder is the one road every engine run takes -- it must refuse."""
    from core.instruments import xauusd
    from research.engine.recipe import SweepRecipe

    stale = tmp_path / "catalog"
    stale.mkdir()
    (stale / "bars.parquet").write_text("x", encoding="utf-8")  # unmarked -> old frame
    recipe = SweepRecipe(xauusd(), "data/dummy.csv", leverage=100)
    recipe.CATALOG_PATH = stale  # point the recipe at the stale catalog
    with pytest.raises(RuntimeError, match="timestamp frame"):
        recipe.build_run_config({"stop_loss_pct": 1.0, "take_profit_pct": 3.0})
