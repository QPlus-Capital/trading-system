"""Tests for the pure parts of the MT5 bridge (symbol mapping). No terminal required."""

from qplus.live.mt5_bridge import base_symbol, match_terminal_symbol


def test_base_symbol_maps_ustec_to_broker_name() -> None:
    assert base_symbol("USTEC") == "UT100"


def test_base_symbol_passthrough_for_matching_names() -> None:
    assert base_symbol("EURUSD") == "EURUSD"
    assert base_symbol("XAUUSD") == "XAUUSD"


def test_match_terminal_symbol_exact() -> None:
    assert match_terminal_symbol("EURUSD", ["EURUSD", "GBPUSD"]) == "EURUSD"


def test_match_terminal_symbol_suffix() -> None:
    # Broker adds a suffix -> pick the shortest symbol that starts with the base.
    assert match_terminal_symbol("EURUSD", ["EURUSD.r", "EURUSD.raw", "GBPUSD.r"]) == "EURUSD.r"


def test_match_terminal_symbol_rejects_contains_only() -> None:
    # M1: "merely contains the base" no longer resolves (could pick the wrong instrument).
    assert match_terminal_symbol("US30", ["mUS30", "US500"]) is None


def test_match_terminal_symbol_none_when_absent() -> None:
    assert match_terminal_symbol("UT100", ["EURUSD", "US30"]) is None
