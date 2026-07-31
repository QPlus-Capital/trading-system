# Evidence

## HEAD

HEAD: b547c3ae750f644d579a3083614ad7dbb6423e6b

The later evidence-only commit changes no document, guard, or test behaviour.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_engineering_workflow_docs.py::test_branch_protection_names_every_required_check_and_setting` against the unchanged page | 1 | The assertion received the seven retired contexts instead of the four active contexts. |
| `review-red-first` | `uv run pytest -q tests/test_engineering_workflow_docs.py` with the round-two counterexamples against the old helpers | 1 | 13 failed and 3 passed: all ten future-action forms escaped, non-matrix strategy was refused, reusable workflows were accepted, and a renamed closing heading widened the parser. |
| `focused` | `uv run pytest -q tests/test_engineering_workflow_docs.py` | 0 | All 16 tests passed, including the ten future-action cases and the three N-01/N-02 boundary cases. |
| `finding-registry` | `uv run pytest -q tests/test_finding_registry.py tests/test_finding_registry_split.py tests/test_engineering_workflow_docs.py` | 0 | 26 tests passed; all four new files are valid content-addressed entries and every named regression resolves. |
| `format` | `just check-standard` | 0 | Ruff, strict mypy over 193 source files, and Vulture passed. |
| `docs-consistency` | `just check` | 0 | The complete suite includes the engineering-document consistency guards; all passed. |
| `check` | `uvx --from rust-just just check` | 0 | Ruff, strict mypy over 193 files, Vulture, and pytest passed: 1,712 passed and one expected unavailable-Mutmut skip. |
| `impacted-tests` | `uv run pytest -q tests/test_engineering_workflow_docs.py tests/test_finding_registry.py tests/test_finding_registry_split.py` | 0 | All 26 documentation and permanent-finding-registry tests passed. |
| `property-tests-where-applicable` | `just check-properties` | 0 | All 21 property tests passed twice with seed `20260721`. |
| `integration-tests` | `uvx --from rust-just just check` | 0 | The full Windows repository integration suite passed with 1,712 tests and one capability skip. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id 135 --base origin/main` | 0 | Task 135 is valid with five acceptance criteria and three invariants. |
| `adversarial-review` | Claude review `4826969384` on PR #145 | 1 | Every round-two finding is dispositioned, but the complete independent re-review of this material fix has not run. |
| `invariants` | `just check-invariants` | 0 | All 529 critical invariant tests passed. |
| `mutation-on-touched-critical` | Python evaluation of `select_fast_targets(changed_paths("origin/main"), load_policy(), load_model())` | 0 | The production selector found zero mutation targets because no production or configured critical function changed. |
| `parity-where-applicable` | `just check` on Windows plus impact classification | 0 | The documentation and parsed YAML behavior is platform-independent and the Windows suite passed; no Linux run is claimed. |
| `live-money-review` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | Not applicable: no live, research, strategy, sizing, risk-limit, or trading path changed. |
| `human-decision-escalation` | Approved issue #135 and live-ruleset API comparison | 0 | Jan approved the exact R3 scope with no open business, trading, architecture, or risk decision. |
| `no-autonomous-merge` | `gh pr view 145 --json isDraft,autoMergeRequest,headRefName,url` | 0 | PR #145 remains draft on its feature branch with auto-merge disabled. |
| `security` | `just check-security` | 0 | Secret scan and Ruff security checks passed; pip-audit found no known vulnerability. |
| `impact` | `uv run python -m scripts.quality.impact --base origin/main` | 0 | Only the existing engineering-workflow documentation test is directly related; no production, critical-path, or unknown dynamic edge was found. |
| `risk-classification` | `uv run python -m scripts.quality.classify --base origin/main` | 0 | R3, because `docs/engineering/**` is governance that protects live-money and result-integrity changes. |
| `pr-ready` | `uvx --from rust-just just pr-ready 135 origin/main` | 1 | Correctly NOT READY on `adversarial-review` alone; task artifacts, R3 classification, and evidence currency all pass. |

## Coverage and mutation

The behavioral guard scopes context parsing between two required headings, resolves each
workflow's effective context from `job.name` or its key, permits non-matrix strategy options,
refuses matrix and reusable-workflow jobs, and requires exact set equality with the four documented
contexts. It checks future application claims sentence-by-sentence: all ten measured phrasings are
committed negative cases. It also binds Active enforcement, no bypass actors, code-owner policy,
squash-only merging, the applied date, ruleset name, pull-request parameters, deliberate
zero-approval and non-strict-check reasons, and both closing-warning clauses. Four generalized
content-addressed findings permanently record the prior confirmed defect classes. No production,
workflow, ruleset, configured mutation target, threshold, or baseline changed.

The Linux-only mutation command was probed on Windows and correctly refused because Mutmut 3.5.0
requires `fork`. That refusal is not presented as a passing ratchet. The executable production
selector returned an empty target set, which is the applicable mutation result for this
documentation-only implementation.

## Deferred checks

- Claude's complete independent re-review of `b547c3a` is pending.
- `pr-ready` remains correctly blocked on that review alone.
- Linux parity has not been observed for this branch and is not claimed green while the pull
  request remains draft.
