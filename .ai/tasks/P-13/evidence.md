# Evidence

## HEAD

HEAD: 950eda91ef7735117eed930d61e4060808aaea15

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify` | 0 | GREEN: classified R3 with all 14 mandatory gates |
| `red-first` | `uv run pytest -q tests/test_research_forward_decision.py tests/test_research_forward_decision_power.py tests/test_quality_properties.py` before implementation | 1 | RED: all three files failed collection because `research.forward_decision` did not exist |
| `mutation-red-first` | Linux runs `29997471940`, `29998077193`, and `29998352237` | 1 | RED: 93, then 4, then 1 new forward-decision survivors prevented the old ratchet from passing |
| `format` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | GREEN: all four changed Python files are Ruff-formatted |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_engineering_docs.py tests/test_gate_consistency.py` | 0 | GREEN: all 67 architecture, engineering-document, and local/CI gate-consistency tests passed |
| `check` | `uvx --from rust-just just check` with Git Bash on `PATH` | 0 | GREEN: Ruff, strict mypy over 159 files, vulture, and 817 pytest tests passed; one Linux-only mutation test skipped on Windows |
| `impacted-tests` | `uv run pytest -q tests/test_quality_properties.py tests/test_research_forward_decision.py tests/test_research_forward_decision_power.py --hypothesis-seed=20260721` | 0 | GREEN: all 47 impact-selected tests passed |
| `property-tests-where-applicable` | `just check-properties` | 0 | GREEN: 12 deterministic properties passed twice with seed 20260721 |
| `integration-tests` | full pytest within `just check` | 0 | GREEN: 817 passed with no registry write and no live terminal/account interaction |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task P-13` | 0 | GREEN: valid P-13 task artifact |
| `adversarial-review` | `.ai/tasks/P-13/review.md` | 0 | GREEN: 28 counterexamples attempted; no unresolved finding |
| `invariants` | `just check-invariants` | 0 | GREEN: all 178 critical live, parity, sizing, research-integrity, registry, decision, and workflow tests passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `29998846357` | 0 | GREEN: weakened-test probe, combined 1,451-mutant critical ratchet, and artifact upload passed on code HEAD `950eda9` |
| `parity-where-applicable` | no-consumer diff plus exact P-12/P-04 source diff | 0 | GREEN: no existing result computation changed; `forward_test_registry.py` and `portfolio/resample.py` are byte-for-byte unchanged from `origin/main` |
| `live-money-review` | `git diff --quiet origin/main -- live core/strategies core/broker.py core/instruments.py` | 0 | GREEN: no live/risk/order/account/broker/signal path changed and no live system was invoked |
| `human-decision-escalation` | task-spec human-decision and open-question audit | 0 | GREEN: Option A and every statistical constant are fixed by the build contract; the unsupplied operational enrollment mapping remains explicit rather than guessed |
| `no-autonomous-merge` | branch/PR workflow audit | 0 | GREEN: ready PR only; Jan retains approval and no merge or auto-merge action is permitted |
| `security` | `just check-security` | 0 | GREEN: tracked-secret scan, dependency audit, and high-signal static security checks passed |
| `impact` | `just impact` against `origin/main` | 0 | GREEN: one additive production module, three direct tests, one critical escalation, and no discovered consumer |
| `pr-ready` | `just pr-ready P-13` | 0 | READY: valid task, declared/classified R3, all 14 required gates exit 0, and evidence current |

## Coverage and mutation

The focused suite covers the two-condition efficacy and futility endpoints, calendar-month
boundaries, strict bound comparisons, pre-endpoint suppression, explicit trade/as-of inputs,
registry/source identity, selected-block production decisions, all 5/10/20/60 sensitivity
analyses, exact Decimal bootstrap arithmetic, and deterministic clustered power fixtures. Linux
run `29998846357` measured the combined critical scope at 1,451 mutants: 1,242 killed and 209
surviving, with zero unhealthy outcomes. The P-13 target kills 368/369; its sole survivor removes
the explicit `Decimal("0")` start from a non-empty sum of validated Decimal values and is
equivalent.

## Deferred checks

None. The registry's operational enrollment-key mapping remains an explicit human-input open
question in `spec.md`; it is not part of this read-only decision package.
