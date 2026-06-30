"""Smoke tests verifying the package is importable and wired up correctly."""

import qplus


def test_package_imports() -> None:
    assert qplus.__version__
