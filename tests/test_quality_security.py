"""The security gate must detect real synthetic evidence without leaking it."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.quality.security import load_security_policy, main, scan_secret_paths

_ROOT = Path(__file__).resolve().parents[1]


def _fake_secret() -> str:
    return "AKIA" + "IOSFODNN7EXAMPLE"


def test_secret_scan_blocks_a_synthetic_fake_secret(tmp_path: Path) -> None:
    path = tmp_path / "credential.txt"
    secret = _fake_secret()
    path.write_text(f"access_key = {secret}\n", encoding="utf-8")
    result = scan_secret_paths([path], load_security_policy())
    assert not result.ok
    assert result.findings


def test_secret_scan_passes_clean_content(tmp_path: Path) -> None:
    path = tmp_path / "clean.py"
    path.write_text("placeholder = 'read-from-environment'\n", encoding="utf-8")
    assert scan_secret_paths([path], load_security_policy()).ok


def test_secret_scan_does_not_disclose_secret_value(tmp_path: Path) -> None:
    path = tmp_path / "credential.txt"
    secret = _fake_secret()
    path.write_text(secret, encoding="utf-8")
    rendered = scan_secret_paths([path], load_security_policy()).render()
    assert secret not in rendered
    assert str(path) in rendered


def test_secret_scan_cli_returns_nonzero_without_disclosing_value(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "credential.txt"
    secret = _fake_secret()
    path.write_text(secret, encoding="utf-8")
    assert main([str(path)]) == 1
    captured = capsys.readouterr()
    assert secret not in captured.out


def test_security_recipe_runs_all_three_security_classes() -> None:
    justfile = (_ROOT / "justfile").read_text(encoding="utf-8")
    recipe = justfile.split("check-security:", 1)[1].split("\n\n", 1)[0]
    assert "scripts.quality.security" in recipe
    assert "pip-audit" in recipe
    assert "ruff check" in recipe and "--select S" in recipe
    policy = load_security_policy()
    assert all(root in recipe for root in policy.static_roots)
    assert all(code in recipe for code in policy.static_ruff_ignores)
