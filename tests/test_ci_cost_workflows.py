"""Executable contract for the cost-aware CI event and platform split."""

from __future__ import annotations

import ast
import re
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import yaml
from scripts.quality.mutation import load_policy

_ROOT = Path(__file__).resolve().parents[1]
_CI_PATH = _ROOT / ".github" / "workflows" / "ci.yml"
_MUTATION_PATH = _ROOT / ".github" / "workflows" / "mutation.yml"
_MT5_NODE = "tests/test_workflow_system_validation.py::test_pytest_blocks_real_mt5_boundaries"
_FULL_RECIPES = {
    "check-standard",
    "check-tests",
    "check-properties",
    "check-task-artifact",
    "check-security",
    "check-invariants",
    "check-pr-evidence",
}
_FAST_RECIPES = {"check-standard"}
_TOKEN = re.compile(
    r"\s*(?:(?P<op>\|\||&&|==|!=|!|\(|\))|"
    r"(?P<string>'[^']*')|(?P<bool>true|false)|"
    r"(?P<identifier>[A-Za-z_][A-Za-z0-9_.-]*))"
)


def _mapping(value: object, label: str) -> dict[str, Any]:
    assert isinstance(value, dict), f"{label} must be a mapping"
    return cast(dict[str, Any], value)


def _sequence(value: object, label: str) -> list[Any]:
    assert isinstance(value, list), f"{label} must be a sequence"
    return value


def _workflow(path: Path) -> dict[str, Any]:
    parsed = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
    return _mapping(parsed, str(path))


def _trigger_accepts(workflow: Mapping[str, Any], event_name: str, action: str = "") -> bool:
    triggers = _mapping(workflow["on"], "workflow.on")
    if event_name not in triggers:
        return False
    event = triggers[event_name]
    if event_name != "pull_request" or not isinstance(event, dict):
        return True
    event_map = _mapping(event, "pull_request trigger")
    types = _sequence(event_map.get("types", []), "pull_request.types")
    return action in {str(value) for value in types}


def _tokens(expression: str) -> list[str]:
    raw = expression.strip()
    if raw.startswith("${{") and raw.endswith("}}"):
        raw = raw[3:-2].strip()
    tokens: list[str] = []
    position = 0
    while position < len(raw):
        match = _TOKEN.match(raw, position)
        assert match is not None, f"unsupported GitHub expression at {raw[position:]!r}"
        tokens.append(match.group(match.lastgroup or ""))
        position = match.end()
    assert tokens, "job condition must not be empty"
    return tokens


class _Expression:
    """Fail-closed evaluator for the bounded GitHub condition grammar used here."""

    def __init__(self, expression: str, context: Mapping[str, object]) -> None:
        self._tokens = _tokens(expression)
        self._position = 0
        self._context = context

    def evaluate(self) -> bool:
        value = self._or()
        assert self._position == len(self._tokens), (
            f"unparsed GitHub expression tokens: {self._tokens[self._position :]}"
        )
        assert isinstance(value, bool), f"job condition did not resolve to bool: {value!r}"
        return value

    def _take(self, token: str | None = None) -> str | None:
        if self._position >= len(self._tokens):
            return None
        found = self._tokens[self._position]
        if token is not None and found != token:
            return None
        self._position += 1
        return found

    def _or(self) -> object:
        value = self._and()
        while self._take("||") is not None:
            right = self._and()
            value = bool(value) or bool(right)
        return value

    def _and(self) -> object:
        value = self._equality()
        while self._take("&&") is not None:
            right = self._equality()
            value = bool(value) and bool(right)
        return value

    def _equality(self) -> object:
        value = self._unary()
        while self._position < len(self._tokens):
            operator = self._tokens[self._position]
            if operator not in {"==", "!="}:
                break
            self._position += 1
            right = self._unary()
            value = value == right if operator == "==" else value != right
        return value

    def _unary(self) -> object:
        if self._take("!") is not None:
            return not bool(self._unary())
        return self._primary()

    def _primary(self) -> object:
        token = self._take()
        assert token is not None, "unexpected end of GitHub expression"
        if token == "(":
            nested_value = self._or()
            assert self._take(")") is not None, "unclosed GitHub expression parenthesis"
            return nested_value
        if token.startswith("'"):
            return token[1:-1]
        if token in {"true", "false"}:
            return token == "true"
        assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*", token), (
            f"unsupported GitHub expression token: {token!r}"
        )
        resolved: object = self._context
        for part in token.split("."):
            assert isinstance(resolved, Mapping) and part in resolved, (
                f"unknown GitHub expression identifier: {token!r}"
            )
            resolved = resolved[part]
        return resolved


def _selected_jobs(
    workflow: Mapping[str, Any],
    *,
    event_name: str,
    action: str,
    draft: bool,
    critical_changed: bool = False,
) -> set[str]:
    if not _trigger_accepts(workflow, event_name, action):
        return set()
    context: dict[str, object] = {
        "github": {
            "event_name": event_name,
            "event": {"pull_request": {"draft": draft}},
        },
        "needs": {
            "critical-change-filter": {"outputs": {"changed": str(critical_changed).lower()}}
        },
    }
    selected: set[str] = set()
    for name, raw_job in _mapping(workflow["jobs"], "jobs").items():
        job = _mapping(raw_job, f"job {name}")
        condition = job.get("if")
        if condition is None or _Expression(str(condition), context).evaluate():
            selected.add(name)
    return selected


def _job(workflow: Mapping[str, Any], name: str) -> dict[str, Any]:
    return _mapping(_mapping(workflow["jobs"], "jobs")[name], f"job {name}")


def _steps(job: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [_mapping(step, "job step") for step in _sequence(job["steps"], "job.steps")]


def _recipes(job: Mapping[str, Any]) -> set[str]:
    recipes: set[str] = set()
    for step in _steps(job):
        run = str(step.get("run", ""))
        matches = re.findall(r"(?:^|\s)just\s+([a-z0-9-]+)\b", run)
        if matches:
            recipes.add(matches[-1])
    return recipes


def _embedded_python(workflow: Mapping[str, Any]) -> str:
    detector = _job(workflow, "critical-change-filter")
    step = next(
        step
        for step in _steps(detector)
        if str(step.get("name", "")) == "Detect configured critical production changes"
    )
    command = str(step["run"])
    marker = "<<'PY'\n"
    assert marker in command and command.rstrip().endswith("\nPY")
    return command.split(marker, 1)[1].rsplit("\nPY", 1)[0]


def _critical_predicate(workflow: Mapping[str, Any]) -> Callable[[Sequence[str]], bool]:
    source = _embedded_python(workflow)
    tree = ast.parse(source)
    executable = ast.Module(
        body=[
            node
            for node in tree.body
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef))
        ],
        type_ignores=[],
    )
    namespace: dict[str, object] = {}
    exec(compile(executable, "<mutation-workflow>", "exec"), namespace)  # noqa: S102
    predicate = namespace.get("critical_changed")
    assert callable(predicate), "workflow must define critical_changed(paths)"
    return cast(Callable[[Sequence[str]], bool], predicate)


def test_pull_request_edited_triggers_no_workflow() -> None:
    for workflow in (_workflow(_CI_PATH), _workflow(_MUTATION_PATH)):
        assert not _trigger_accepts(workflow, "pull_request", "edited")


def test_draft_and_ready_events_select_the_expected_gate_sets() -> None:
    workflow = _workflow(_CI_PATH)
    draft_jobs = _selected_jobs(workflow, event_name="pull_request", action="opened", draft=True)
    ready_jobs = _selected_jobs(
        workflow, event_name="pull_request", action="ready_for_review", draft=False
    )

    assert draft_jobs == {"fast-quality"}
    assert _recipes(_job(workflow, "fast-quality")) == _FAST_RECIPES
    assert ready_jobs == {"full-quality", "mt5-boundary"}
    assert _recipes(_job(workflow, "full-quality")) == _FULL_RECIPES


def test_ready_synchronize_runs_the_full_set() -> None:
    workflow = _workflow(_CI_PATH)
    assert _selected_jobs(
        workflow, event_name="pull_request", action="synchronize", draft=False
    ) == {"full-quality", "mt5-boundary"}


def test_direct_ready_pull_request_runs_the_full_set() -> None:
    workflow = _workflow(_CI_PATH)
    assert _selected_jobs(workflow, event_name="pull_request", action="opened", draft=False) == {
        "full-quality",
        "mt5-boundary",
    }


def test_mutation_job_uses_the_policy_for_concrete_changed_paths() -> None:
    workflow = _workflow(_MUTATION_PATH)
    predicate = _critical_predicate(workflow)
    critical_path = load_policy().targets[0].path

    assert not predicate(["README.md"])
    assert not predicate(["tests/test_gate_consistency.py"])
    assert predicate([critical_path])
    assert "mutation-critical" not in _selected_jobs(
        workflow,
        event_name="pull_request",
        action="synchronize",
        draft=False,
        critical_changed=False,
    )
    assert "mutation-critical" in _selected_jobs(
        workflow,
        event_name="pull_request",
        action="synchronize",
        draft=False,
        critical_changed=True,
    )
    assert "mutation-critical" not in _selected_jobs(
        workflow,
        event_name="pull_request",
        action="synchronize",
        draft=True,
        critical_changed=True,
    )


def test_mutation_filter_has_no_copied_target_paths() -> None:
    workflow = _workflow(_MUTATION_PATH)
    source = _embedded_python(workflow)
    tree = ast.parse(source)
    imported = {
        alias.name for node in tree.body if isinstance(node, ast.ImportFrom) for alias in node.names
    }
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    target_paths = {target.path for target in load_policy().targets}
    string_literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }

    assert {"changed_paths", "load_model", "load_policy", "select_fast_targets"} <= imported
    assert {"changed_paths", "load_model", "load_policy", "select_fast_targets"} <= called
    assert not target_paths & string_literals


def test_only_the_mt5_boundary_job_uses_windows() -> None:
    workflow = _workflow(_CI_PATH)
    platforms = {
        name: str(_mapping(job, f"job {name}")["runs-on"])
        for name, job in _mapping(workflow["jobs"], "jobs").items()
    }
    assert platforms == {
        "fast-quality": "ubuntu-latest",
        "full-quality": "ubuntu-latest",
        "mt5-boundary": "windows-latest",
    }


def test_mt5_boundary_job_runs_the_exact_windows_node() -> None:
    workflow = _workflow(_CI_PATH)
    boundary = _job(workflow, "mt5-boundary")
    commands = [str(step.get("run", "")) for step in _steps(boundary)]
    pytest_commands = [command for command in commands if "pytest" in command]
    assert pytest_commands == [f"uv run pytest -q {_MT5_NODE}"]


def test_ready_test_node_inventory_is_partitioned_without_loss() -> None:
    workflow = _workflow(_CI_PATH)
    assert "check-tests" in _recipes(_job(workflow, "full-quality"))
    assert _MT5_NODE in next(
        str(step["run"])
        for step in _steps(_job(workflow, "mt5-boundary"))
        if "pytest" in str(step.get("run", ""))
    )

    source = (_ROOT / "tests" / "test_workflow_system_validation.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not any(
        isinstance(node, (ast.Import, ast.ImportFrom))
        and any(alias.name == "MetaTrader5" for alias in node.names)
        for node in tree.body
    ), "the full Linux suite must collect without importing the Windows-only package"


def test_full_job_invokes_every_existing_gate_as_a_distinct_step() -> None:
    workflow = _workflow(_CI_PATH)
    full = _job(workflow, "full-quality")
    recipe_steps = [
        step
        for step in _steps(full)
        if re.search(r"(?:^|\s)just\s+[a-z0-9-]+\b", str(step.get("run", "")))
    ]
    assert _recipes(full) == _FULL_RECIPES
    assert len(recipe_steps) == len(_FULL_RECIPES)
    assert len({str(step.get("name", "")) for step in recipe_steps}) == len(_FULL_RECIPES)
    assert all(str(step.get("name", "")).startswith("Gate: ") for step in recipe_steps)


def test_consolidated_jobs_cache_dependencies_and_preserve_limits() -> None:
    ci = _workflow(_CI_PATH)
    for name in ("fast-quality", "full-quality", "mt5-boundary"):
        job = _job(ci, name)
        setup = next(
            step for step in _steps(job) if "astral-sh/setup-uv@" in str(step.get("uses", ""))
        )
        options = _mapping(setup["with"], f"{name} setup-uv.with")
        assert options["enable-cache"] == "true"
        assert options["cache-dependency-glob"] == "uv.lock"

    assert int(str(_job(ci, "fast-quality")["timeout-minutes"])) <= 20
    assert int(str(_job(ci, "full-quality")["timeout-minutes"])) <= 30
    assert int(str(_job(ci, "mt5-boundary")["timeout-minutes"])) <= 30
    mutation = _workflow(_MUTATION_PATH)
    assert int(str(_job(mutation, "mutation-critical")["timeout-minutes"])) == 45


def test_each_consolidated_gate_keeps_its_previous_timeout_ceiling() -> None:
    ci = _workflow(_CI_PATH)
    expected = {
        "Gate: Standard Quality": 20,
        "Gate: Tests": 30,
        "Gate: Deterministic Property Replay": 30,
        "Gate: Task-Artifact Validation": 10,
        "Gate: Security": 20,
        "Gate: Critical Invariants": 20,
        "Gate: PR-Evidence Validation": 10,
    }
    full = {
        str(step.get("name", "")): int(str(step["timeout-minutes"]))
        for step in _steps(_job(ci, "full-quality"))
        if str(step.get("name", "")).startswith("Gate: ")
    }
    assert full == expected
    fast_standard = next(
        step
        for step in _steps(_job(ci, "fast-quality"))
        if step.get("name") == "Gate: Standard Quality"
    )
    assert int(str(fast_standard["timeout-minutes"])) == 20


def test_expression_evaluator_refuses_unknown_or_trailing_input() -> None:
    context: dict[str, object] = {"github": {"event_name": "pull_request"}}
    for expression in (
        "github.missing == 'x'",
        "github.event_name == 'pull_request' unsupported",
        "'unterminated",
    ):
        try:
            _Expression(expression, context).evaluate()
        except AssertionError:
            continue
        raise AssertionError(f"expression evaluator accepted unsupported input: {expression!r}")
