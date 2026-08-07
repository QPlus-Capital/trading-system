"""CI must confirm the local gates without becoming a second, divergent policy.

Two properties carry real risk and are checked here rather than trusted:

**A skipped required check counts as satisfied on GitHub.** A conditional job can therefore never be
a required status context -- protection on `main` would report green without evaluating anything.
Only ``required-checks`` may be required, and it must always run.

**CI and the local gates must not drift.** Every gate step invokes a `just` recipe that exists in
the justfile, so `just gates` and CI run the same commands.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[1]
_CI_PATH = _ROOT / ".github" / "workflows" / "ci.yml"
_JUSTFILE = (_ROOT / "justfile").read_text(encoding="utf-8")
_CI_TEXT = _CI_PATH.read_text(encoding="utf-8")


def _workflow() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(_CI_TEXT)
    return loaded


def _jobs() -> dict[str, Any]:
    jobs: dict[str, Any] = _workflow()["jobs"]
    return jobs


def _recipes(job: dict[str, Any]) -> set[str]:
    found: set[str] = set()
    for step in job.get("steps", []):
        run = str(step.get("run", ""))
        # The lookbehind keeps `uvx --from rust-just just check` from matching inside "rust-just"
        # and swallowing the recipe name that follows.
        found.update(re.findall(r"(?<![-\w])just\s+([a-z][a-z0-9-]*)", run))
    return found


def test_exactly_one_workflow_file_remains() -> None:
    """Two workflows meant two triggers, two concurrency groups and two places to keep in sync."""
    workflows = sorted(path.name for path in (_ROOT / ".github" / "workflows").glob("*.yml"))
    assert workflows == ["ci.yml"]


def test_the_required_context_always_runs() -> None:
    """The job branch protection requires must not be conditional, or protection is fail-open."""
    required = _jobs()["required-checks"]
    assert str(required["if"]).strip() in {"always()", "True"}
    assert "needs" in required


def test_the_required_context_depends_on_every_other_job() -> None:
    """A job it does not watch could fail without blocking the merge."""
    jobs = _jobs()
    watched = set(jobs["required-checks"]["needs"])
    assert watched == set(jobs) - {"required-checks"}


def test_the_required_context_fails_on_a_failed_job_and_tolerates_a_skip() -> None:
    """Skipped is legitimate for a conditional job; failed and cancelled never are."""
    step = str(_jobs()["required-checks"]["steps"][0]["run"])
    assert '"success", "skipped"' in step
    assert "sys.exit(1)" in step


def test_only_the_conditional_jobs_carry_a_condition() -> None:
    """Everything else runs unconditionally -- the conditions are where the minutes are saved."""
    conditional = {
        name for name, job in _jobs().items() if "if" in job and name != "required-checks"
    }
    assert conditional == {"mt5-boundary", "mutation"}


def test_no_job_is_gated_on_draft_state() -> None:
    """The review happens on an ordinary pull request. Gating CI on draft state was what made the
    gates run only after the review had already finished."""
    assert "draft" not in _CI_TEXT


def test_the_windows_runner_is_conditional() -> None:
    """Windows bills at twice the Linux rate, so it runs only for the MT5 boundary it exists for."""
    jobs = _jobs()
    windows = {name for name, job in jobs.items() if "windows" in str(job.get("runs-on", ""))}
    assert windows == {"mt5-boundary"}
    assert "if" in jobs["mt5-boundary"], "an unconditional Windows job doubles the routine cost"


def test_the_linux_jobs_fall_back_to_the_hosted_runner() -> None:
    """Every Linux job uses one variable whose safe default remains GitHub-hosted."""
    expected = "${{ vars.CI_LINUX_RUNNER || 'ubuntu-latest' }}"
    jobs = _jobs()
    assert {name for name, job in jobs.items() if job["runs-on"] == expected} == {
        "quality",
        "mutation",
        "required-checks",
    }


def test_the_windows_boundary_job_is_pinned_to_the_hosted_runner() -> None:
    """The MT5 boundary never shares the configurable Linux runner used by CI."""
    boundary = _jobs()["mt5-boundary"]
    assert boundary["runs-on"] == "windows-latest"
    assert "CI_LINUX_RUNNER" not in str(boundary)


def test_the_required_context_keeps_its_name() -> None:
    """Branch protection and the review cycle both wait for this exact context."""
    assert "required-checks" in _jobs()


def test_every_ci_gate_invokes_a_recipe_the_justfile_defines() -> None:
    for job in _jobs().values():
        for recipe in _recipes(job):
            assert re.search(rf"^{re.escape(recipe)}(?:\s+[^:]*)?:", _JUSTFILE, re.MULTILINE), (
                f"CI runs `just {recipe}`, which the justfile does not define"
            )


def test_the_quality_job_runs_the_gates_the_contract_names() -> None:
    """CI must not quietly run fewer gates than the R3 contract requires."""
    assert _recipes(_jobs()["quality"]) >= {
        "check",
        "check-properties",
        "check-security",
        "check-invariants",
        "check-parity",
    }


def test_ci_never_reimplements_a_gate_inline() -> None:
    """A gate spelled out in YAML drifts from the recipe it copies."""
    gate_steps = "\n".join(
        str(step.get("run", ""))
        for job in _jobs().values()
        for step in job.get("steps", [])
        if "just " in str(step.get("run", ""))
    )
    for direct in ("uv run ruff", "uv run mypy", "uv run pytest", "pip-audit"):
        assert direct not in gate_steps


def test_the_conditional_scope_uses_the_production_policy() -> None:
    """The filter imports the modules the local tooling uses, and never restates policy.

    Mutation left the push filter entirely: a push measures no mutants, and which targets the
    one per-ticket run measures is decided by ``workflow.mutation`` itself inside the mutation
    job (`just mutation-affected`) — the same production code path the local gate uses.
    """
    scope = next(step for step in _jobs()["quality"]["steps"] if step.get("id") == "scope")
    run = str(scope["run"])
    assert "from workflow.classify import" in run
    assert "select_fast_targets" not in run, "target selection must not live in the filter"

    mutation_runs = " ".join(
        str(step.get("run", "")) for step in _jobs()["mutation"]["steps"]
    )
    assert "just mutation-affected" in mutation_runs
    assert "just mutation-critical" in mutation_runs


def test_a_push_never_triggers_the_mutation_job() -> None:
    """Mutation evidence is produced once per ticket by the cycle, on the head the review
    certified — not on every intermediate push (three full runs on #177, one of them used)."""
    scope = next(step for step in _jobs()["quality"]["steps"] if step.get("id") == "scope")
    run = str(scope["run"])
    assert 'needs_mutation, mutation_scope = False, ""' in run
    # PyYAML reads a bare `on:` key as boolean True; normalize so the assertion reads plainly.
    normalized = {str(key): value for key, value in _workflow().items()}
    triggers = normalized.get("on") or normalized["True"]
    assert "schedule" in triggers, "the weekly critical run keeps the global baseline honest"
    assert triggers["workflow_dispatch"]["inputs"]["scope"]["options"] == [
        "everything",
        "mutation-affected",
    ]


def test_every_action_is_pinned_to_a_commit_sha() -> None:
    """A moving tag lets a third party change what runs against this repository."""
    for reference in re.findall(r"uses:\s*(\S+)", _CI_TEXT):
        _, _, version = reference.partition("@")
        assert re.fullmatch(r"[0-9a-f]{40}", version), f"{reference} is not pinned to a SHA"


def test_concurrency_cancels_superseded_runs() -> None:
    """One push per round is the rule; a superseded run must not keep burning minutes."""
    assert _workflow()["concurrency"]["cancel-in-progress"] is True
