# Evidence

## HEAD

HEAD: 75b6ffa9c68e5779643e67119aba452d86586f71

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | explicit intended-path classifier | 0 | R3 after the required mutation-policy path; semantic R3 upgrade recorded |
| `red-first` | focused registry + property tests against importable stubs | 1 | RED: all 11 new guards failed at their target operation |
| `red-first` | Decimal-artifact guard against first implementation | 1 | RED: a JSON float was accepted until the read path was tightened |
| `mutation-red-first` | Linux runs `29987770547`, `29988036781`, `29988295451` | 1 | RED: new target absent from baseline; 12 then 5 then 1 survivor exposed before ratcheting |
| `format` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | GREEN: all three changed Python files are Ruff-formatted |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py` | 0 | GREEN: updated module-map path exists |
| `check` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check` | 0 | GREEN: Ruff, mypy over 156 files, vulture, and 778 pytest tests passed; one Linux-only test skipped on Windows |
| `impacted-tests` | `uv run pytest -q tests/test_quality_properties.py tests/test_research_forward_test_registry.py --hypothesis-seed=20260721` | 0 | GREEN: all 24 impact-selected tests passed |
| `property-tests-where-applicable` | `just check-properties` | 0 | GREEN: 10 deterministic properties passed twice with seed 20260721 |
| `integration-tests` | full pytest within `just check` | 0 | GREEN: 778 passed with no live terminal/account interaction |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-12` | 0 | GREEN: valid task with 9 acceptance criteria and 6 invariants |
| `adversarial-review` | `.ai/tasks/P-12/review.md` | 0 | GREEN: 20 counterexamples attempted; no unresolved finding |
| `invariants` | `just check-invariants` | 0 | GREEN: 143 critical live, parity, sizing, research-integrity, registry, and workflow tests passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `29994706827` | 0 | GREEN: weakened-test probe, combined 1,082-mutant critical ratchet, and artifact upload passed on formatted code HEAD `75b6ffa` |
| `parity-where-applicable` | `git diff --quiet origin/main -- core live monitoring research/config research/engine research/portfolio research/stages` | 0 | GREEN: no stage, result-computation, monitoring, core, or live path changed; no reported number can move |
| `live-money-review` | `git diff --quiet origin/main -- live core/strategies core/broker.py core/instruments.py` plus security artifact test | 0 | GREEN: no live/risk/order/account/broker/signal code or runner interaction; identifier is opaque and disk-checked |
| `human-decision-escalation` | task-spec human-decision and open-question audit | 0 | GREEN: operational enrollment values are not guessed; Jan retains approval |
| `no-autonomous-merge` | branch/PR workflow audit | 0 | GREEN: ready PR only, no merge or auto-merge action |
| `security` | `just check-security` | 0 | GREEN: tracked-secret scan, dependency audit, and static security passed |
| `impact` | `just impact` against `origin/main` | 0 | GREEN: R3; two direct tests, one critical escalation, no discovered consumer |
| `merge-union` | TOML set-union assertions against pre-merge P-04 and P-12 parents | 0 | GREEN: all 10 targets, 12 test selections, and 208 survivor entries are retained exactly; registry AST is unchanged |
| `pr-ready` | `just pr-ready P-12` | 0 | READY: valid task, declared/classified R3, all 14 required gates exit 0, evidence current |

## Coverage and mutation

The focused registry suite and two deterministic properties cover content/path identity, every
hashed input, append-only definitions, source/cohort isolation, exact Decimal storage, and disk
credential exclusion. Linux run `29994706827` measured the merged P-04/P-12 scope at 1,082
mutants: 874 killed and 208 surviving, with zero unhealthy outcomes. The baseline retains every
P-04 resampling survivor and every P-12 cohort survivor; the forward target kills 32/33, and its
sole survivor removes explicit `ensure_ascii=True`, exactly equivalent to `json.dumps`' default.

## Deferred checks

None. Operational enrollment remains a human-input open question in `spec.md`, not a deferred
verification claim.
