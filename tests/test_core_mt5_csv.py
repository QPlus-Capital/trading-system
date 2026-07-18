"""Tests for MT5 CSV timestamp semantics (#18).

The exported ``<DATE> <TIME>`` columns are the BROKER SERVER's wall clock, not UTC. Verified from
the data itself: the FX week starts Monday 00:00 and ends Friday 20:00 in these files, and the
week-start hour does not shift across the DST changeover -- in real UTC an EET server's week would
begin Sunday 21:00 in summer and 22:00 in winter.
"""

import pandas as pd
from core.data.mt5_csv import parse_mt5_timestamps


def test_timestamps_default_to_the_historical_utc_reading() -> None:
    """The default must NOT change silently: every number produced so far read these stamps as
    UTC, so flipping it would re-date the entire research history without anyone asking."""
    df = pd.DataFrame({"<DATE>": ["2024.07.01"], "<TIME>": ["00:00:00"]})
    assert parse_mt5_timestamps(df)[0] == pd.Timestamp("2024-07-01 00:00", tz="UTC")


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
