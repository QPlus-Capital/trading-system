"""Deterministic property settings and a fail-closed real-MT5 test boundary."""

import importlib
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, NoReturn

import pytest
from hypothesis import settings
from hypothesis.configuration import set_hypothesis_home_dir
from workflow import orchestrate as workflow_orchestrate
from workflow import watch as workflow_watch

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
_TESTS_ROOT = Path(__file__).resolve().parent
_SHARED_GIT_DIRECTORY = workflow_orchestrate.events_path(0).parent
_WORKFLOW_STATE_PATTERNS = (
    "qplus-events-*.jsonl",
    "qplus-cycle-*.json",
    "qplus-cycle-*.lock",
)
_ORIGINAL_WORKFLOW_PATH_HELPERS = (
    workflow_orchestrate.events_path,
    workflow_orchestrate.liveness_path,
    workflow_orchestrate._lock_path,
)

type _CommandPart = str | bytes | os.PathLike[str] | os.PathLike[bytes]
type _Command = _CommandPart | Sequence[_CommandPart]
type _RuntimePathHelper = Callable[[int], Path]
type _RuntimePathBinding = tuple[ModuleType, str, int]

_DIRECT_WORKFLOW_PATH_BINDINGS: tuple[_RuntimePathBinding, ...] = (
    (workflow_orchestrate, "events_path", 0),
    (workflow_orchestrate, "liveness_path", 1),
    (workflow_orchestrate, "_lock_path", 2),
    (workflow_watch, "events_path", 0),
    (workflow_watch, "liveness_path", 1),
)
_WORKFLOW_PATH_BINDINGS: list[_RuntimePathBinding] = []


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
    name = filename.casefold().removesuffix(".exe")
    if re.fullmatch(r"python[0-9]+(?:\.[0-9]+)*", name):
        return "python"
    return name


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


def _workflow_state_files(directory: Path) -> frozenset[Path]:
    return frozenset(
        path
        for pattern in _WORKFLOW_STATE_PATTERNS
        for path in directory.glob(pattern)
        if path.is_file()
    )


def _assert_no_shared_workflow_state(directory: Path, before: frozenset[Path]) -> None:
    leaked = sorted(_workflow_state_files(directory) - before)
    if leaked:
        names = ", ".join(path.name for path in leaked)
        raise AssertionError(
            f"test wrote workflow runtime state into shared git directory: {names}"
        )


@pytest.fixture
def assert_no_shared_workflow_state() -> Callable[[Path, frozenset[Path]], None]:
    """Expose the shared-state guard without writing into the repository's real git directory."""

    return _assert_no_shared_workflow_state


def _is_test_module(module: ModuleType) -> bool:
    source = getattr(module, "__file__", None)
    if not source or module.__name__ == __name__:
        return False
    try:
        return Path(source).resolve().is_relative_to(_TESTS_ROOT)
    except OSError:
        return False


def _discover_imported_path_helpers() -> list[_RuntimePathBinding]:
    """Find helper references imported into test modules during collection."""

    bindings: list[_RuntimePathBinding] = []
    for module in tuple(sys.modules.values()):
        if not isinstance(module, ModuleType) or not _is_test_module(module):
            continue
        for name, value in tuple(vars(module).items()):
            for replacement_index, original in enumerate(_ORIGINAL_WORKFLOW_PATH_HELPERS):
                if value is original:
                    bindings.append((module, name, replacement_index))
                    break
    return bindings


@pytest.fixture(scope="session", autouse=True)
def _collect_workflow_path_bindings() -> None:
    """Cache workflow helper binding sites once after test collection."""

    _WORKFLOW_PATH_BINDINGS[:] = [
        *_DIRECT_WORKFLOW_PATH_BINDINGS,
        *_discover_imported_path_helpers(),
    ]


def _patch_imported_path_helpers(
    monkeypatch: pytest.MonkeyPatch,
    replacements: tuple[_RuntimePathHelper, _RuntimePathHelper, _RuntimePathHelper],
) -> None:
    """Redirect the workflow helper binding sites cached after collection."""

    for module, name, replacement_index in _WORKFLOW_PATH_BINDINGS:
        monkeypatch.setattr(module, name, replacements[replacement_index])


@pytest.fixture(autouse=True)
def _isolate_workflow_runtime_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    assert_no_shared_workflow_state: Callable[[Path, frozenset[Path]], None],
) -> Iterator[None]:
    """Keep test cycle state local and fail if a route still reaches the shared git directory."""

    before = _workflow_state_files(_SHARED_GIT_DIRECTORY)

    def isolated_events_path(issue: int) -> Path:
        return tmp_path / f"qplus-events-{issue}.jsonl"

    def isolated_liveness_path(issue: int) -> Path:
        return tmp_path / f"qplus-cycle-{issue}.json"

    def isolated_lock_path(issue: int) -> Path:
        return tmp_path / f"qplus-cycle-{issue}.lock"

    replacements = (isolated_events_path, isolated_liveness_path, isolated_lock_path)
    _patch_imported_path_helpers(monkeypatch, replacements)

    yield

    assert_no_shared_workflow_state(_SHARED_GIT_DIRECTORY, before)


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
