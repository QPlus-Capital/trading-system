# Evidence

## HEAD

HEAD: 70fc969d99e9f15234628d0ff0f7be8860e8751e

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | explicit intended-path classifier | 0 | R3 after the required mutation-policy path; semantic R3 upgrade recorded |
| `red-first` | focused registry + property tests against importable stubs | 1 | RED: all 11 new guards failed at their target operation |
| `red-first` | Decimal-artifact guard against first implementation | 1 | RED: a JSON float was accepted until the read path was tightened |
| `mutation-red-first` | Linux runs `29987770547`, `29988036781`, `29988295451` | 1 | RED: new target absent from baseline; 12 then 5 then 1 survivor exposed before ratcheting |
| `format` | `uv run ruff check .` via `just check` | 0 | GREEN: all files passed Ruff |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py` | 0 | GREEN: updated module-map path exists |
| `check` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check` | 0 | GREEN: Ruff, mypy over 152 files, vulture, and 735 pytest tests passed; one Linux-only test skipped on Windows |
| `impacted-tests` | `uv run pytest -q tests/test_quality_properties.py tests/test_research_forward_test_registry.py --hypothesis-seed=20260721` | 0 | GREEN: all 24 impact-selected tests passed |
| `property-tests-where-applicable` | `just check-properties` | 0 | GREEN: 10 deterministic properties passed twice with seed 20260721 |
| `integration-tests` | full pytest within `just check` | 0 | GREEN: 735 passed with no live terminal/account interaction |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-12` | 0 | GREEN: valid task with 9 acceptance criteria and 6 invariants |
| `adversarial-review` | `.ai/tasks/P-12/review.md` | 0 | GREEN: 20 counterexamples attempted; no unresolved finding |
| `invariants` | `just check-invariants` | 0 | GREEN: 143 critical live, parity, sizing, research-integrity, registry, and workflow tests passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `29988817310` | 0 | GREEN: weakened-test probe, 807-mutant critical ratchet, and artifact upload passed on code HEAD `18cfac4`; only task impact metadata changed afterward |
| `parity-where-applicable` | `git diff --quiet origin/main -- core live monitoring research/config research/engine research/portfolio research/stages` | 0 | GREEN: no stage, result-computation, monitoring, core, or live path changed; no reported number can move |
| `live-money-review` | `git diff --quiet origin/main -- live core/strategies core/broker.py core/instruments.py` plus security artifact test | 0 | GREEN: no live/risk/order/account/broker/signal code or runner interaction; identifier is opaque and disk-checked |
| `human-decision-escalation` | task-spec human-decision and open-question audit | 0 | GREEN: operational enrollment values are not guessed; Jan retains approval |
| `no-autonomous-merge` | branch/PR workflow audit | 0 | GREEN: ready PR only, no merge or auto-merge action |
| `security` | `just check-security` | 0 | GREEN: tracked-secret scan, dependency audit, and static security passed |
| `impact` | `just impact` against `origin/main` | 0 | GREEN: R3; two direct tests, one critical escalation, no discovered consumer |
| `pr-ready` | `just pr-ready P-12` | 0 | READY: valid task, declared/classified R3, all 14 required gates exit 0, evidence current |

## Coverage and mutation

The focused registry suite and two deterministic properties cover content/path identity, every
hashed input, append-only definitions, source/cohort isolation, exact Decimal storage, and disk
credential exclusion. Linux run `29988817310` measured 807 mutants: 617 killed and 190 surviving;
the new target killed 32/33. Its sole survivor removes explicit `ensure_ascii=True`, exactly
equivalent to `json.dumps`' default and recorded as such in the ratchet.

## Deferred checks

None. Operational enrollment remains a human-input open question in `spec.md`, not a deferred
verification claim.
