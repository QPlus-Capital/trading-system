"""Deterministic property settings and a fail-closed real-MT5 test boundary."""

import importlib
import importlib.util
import os
import subprocess
import tempfile
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn

import pytest
from hypothesis import settings
from hypothesis.configuration import set_hypothesis_home_dir

# Hypothesis caches scraped constants under `.hypothesis/` in the working directory. The example
# database is already off (see the profile below), so nothing here is load-bearing -- it is a cache
# that regenerates. Keeping it out of the repository root is purely so the checkout shows only
# things that belong to the project. Must run before Hypothesis first touches its storage.
set_hypothesis_home_dir(str(Path(tempfile.gettempdir()) / "qplus-hypothesis"))

_MT5_BOUNDARIES = (
    "initialize",
    "login",
    "shutdown",
    "account_info",
    "terminal_info",
    "symbols_get",
    "symbol_info",
    "symbol_info_tick",
    "copy_rates_from",
    "copy_rates_from_pos",
    "copy_rates_range",
    "copy_ticks_from",
    "copy_ticks_range",
    "positions_get",
    "orders_get",
    "history_orders_get",
    "history_deals_get",
    "order_check",
    "order_send",
)
_ALLOWED_TEST_PROGRAMS = frozenset({"git", "mutmut", "python", "uv"})
_REMOTE_GIT_SUBCOMMANDS = frozenset({"clone", "fetch", "ls-remote", "pull", "push", "remote"})
_REAL_SUBPROCESS_RUN = subprocess.run
_REAL_SUBPROCESS_POPEN = subprocess.Popen
_REAL_SUBPROCESS_CHECK_OUTPUT = subprocess.check_output

type _CommandPart = str | bytes | os.PathLike[str] | os.PathLike[bytes]
type _Command = _CommandPart | Sequence[_CommandPart]


def _command_parts(command: _Command) -> tuple[str, ...]:
    raw_parts = (command,) if isinstance(command, (str, bytes, os.PathLike)) else tuple(command)
    try:
        return tuple(os.fsdecode(part) for part in raw_parts)
    except TypeError as exc:
        raise AssertionError(
            f"tests refused process spawn with invalid command: {command!r}"
        ) from exc


def _program_name(program: str) -> str:
    filename = program.replace("\\", "/").rsplit("/", maxsplit=1)[-1]
    return filename.casefold().removesuffix(".exe")


def _assert_test_spawn_allowed(
    command: _Command,
    *,
    executable: _CommandPart | None = None,
    shell: bool = False,
) -> None:
    """Refuse a process command unless it is a known local test dependency."""

    parts = _command_parts(command)
    rendered = subprocess.list2cmdline(parts) if parts else "<empty command>"
    if shell:
        raise AssertionError(f"tests refused shell process spawn: {rendered}")
    if not parts:
        raise AssertionError("tests refused process spawn: <empty command>")

    program = os.fsdecode(executable) if executable is not None else parts[0]
    name = _program_name(program)
    if name not in _ALLOWED_TEST_PROGRAMS:
        raise AssertionError(f"tests refused process spawn: {rendered}")
    if name == "git" and any(part.casefold() in _REMOTE_GIT_SUBCOMMANDS for part in parts[1:]):
        raise AssertionError(f"tests refused remote git process spawn: {rendered}")


@pytest.fixture
def assert_test_spawn_allowed() -> Callable[[_Command], None]:
    """Expose the guard predicate without starting the allowed command."""

    return _assert_test_spawn_allowed


@pytest.fixture(autouse=True)
def _block_unlisted_process_spawns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail before an unlisted or remote-capable process can start from a test."""

    def guard(real_spawn: Callable[..., Any]) -> Callable[..., Any]:
        def guarded(command: _Command, *args: Any, **kwargs: Any) -> Any:
            _assert_test_spawn_allowed(
                command,
                executable=kwargs.get("executable"),
                shell=bool(kwargs.get("shell")),
            )
            return real_spawn(command, *args, **kwargs)

        return guarded

    monkeypatch.setattr(subprocess, "run", guard(_REAL_SUBPROCESS_RUN))
    monkeypatch.setattr(subprocess, "Popen", guard(_REAL_SUBPROCESS_POPEN))
    monkeypatch.setattr(subprocess, "check_output", guard(_REAL_SUBPROCESS_CHECK_OUTPUT))


def _mt5_available() -> bool:
    return importlib.util.find_spec("MetaTrader5") is not None


def _load_mt5_module() -> ModuleType | None:
    """Load the Windows-only bridge when available without breaking Linux test collection."""

    if not _mt5_available():
        return None
    return importlib.import_module("MetaTrader5")


@pytest.fixture(autouse=True)
def _block_real_mt5(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make an unmocked terminal/account call fail before it can reach MetaTrader 5."""

    mt5 = _load_mt5_module()
    if mt5 is None:
        return

    class BlockedMT5Boundary:
        __qplus_test_block__ = True

        def __call__(self, *_args: object, **_kwargs: object) -> NoReturn:
            raise AssertionError("tests must replace MT5 boundaries with explicit fakes")

    blocked = BlockedMT5Boundary()
    for name in _MT5_BOUNDARIES:
        monkeypatch.setattr(mt5, name, blocked)


settings.register_profile(
    "qplus",
    derandomize=True,
    database=None,
    deadline=None,
    max_examples=75,
    print_blob=True,
)
settings.load_profile("qplus")
