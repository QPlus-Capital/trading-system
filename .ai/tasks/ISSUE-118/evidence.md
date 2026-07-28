# Evidence

## HEAD

HEAD: b81012936e83ca71e99aa46c81a8d34d664e2478

The only later commit permitted by readiness is this evidence file itself.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `$env:PATH='C:\Program Files\Git\bin;' + $env:PATH; uvx --from rust-just just check-fast origin/main` | 0 | No changed Python file required formatting; Ruff and strict mypy passed. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_gate_consistency.py tests/test_docs_language.py` | 0 | 139 documentation and gate-consistency tests passed. |
| `check` | `$env:PATH='C:\Program Files\Git\bin;' + $env:PATH; uvx --from rust-just just check` | 0 | Ruff, strict mypy over 180 files, Vulture, and 1,194 tests passed; one Linux-only mutation test skipped on Windows. |
| `impacted-tests` | `$env:PATH='C:\Program Files\Git\bin;' + $env:PATH; uvx --from rust-just just check-fast origin/main` | 0 | No production file or configured test dependency changed; the full suite remains the mandatory proof. |
| `property-tests-where-applicable` | `$env:PATH='C:\Program Files\Git\bin;' + $env:PATH; uvx --from rust-just just check-properties` | 0 | 21 properties passed twice with fixed Hypothesis seed `20260721`. |
| `integration-tests` | `uv run pytest -q tests/test_quality_mutation.py tests/test_quality_hooks.py tests/test_quality_classify.py tests/test_quality_pr_ready.py tests/test_gate_consistency.py` | 0 | 88 quality-tooling integration tests passed; one expected native-Windows Mutmut test skipped. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-118 --base origin/main` | 0 | Task schema, nine acceptance criteria, six invariants, R3 declaration, traceability, evidence, and review are valid. |
| `adversarial-review` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-118 --base origin/main` | 0 | Six builder counterexamples have resolved executable dispositions; independent Claude review remains external. |
| `invariants` | `$env:PATH='C:\Program Files\Git\bin;' + $env:PATH; uvx --from rust-just just check-invariants` | 0 | 316 critical invariant tests passed. |
| `mutation-on-touched-critical` | `$env:MUTATION_REPORT='<artifact>/critical.toml'; uv run python -c "<MutationReport/load_baseline/check_baseline comparator>"` | 0 | The Linux self-test and mutation execution were sound. The retained `4,568`-mutant report compares with zero issues against the regenerated baseline: 4,151 killed, 417 exactly classified survivors, and every unhealthy status zero. |
| `parity-where-applicable` | `git diff --exit-code origin/main...HEAD -- core research live monitoring` | 0 | No trading, research, live, monitoring, signal, sizing, risk, or result code changed. |
| `live-money-review` | production-diff audit plus `just check-invariants` | 0 | No live module, runner, MT5 terminal, risk limit, order path, account state, or trading decision was touched. |
| `human-decision-escalation` | task specification and issue #118 | 0 | Jan required wholesale regeneration, explicit tightening proof, draft-only delivery, and Jan-only merge authority; no decision remains delegated. |
| `no-autonomous-merge` | branch and delivery-state audit | 0 | Separate branch `codex/mutation-baseline-refresh-20260728`; draft PR only, with no ready transition, merge, or auto-merge action. |

## Additional evidence

| Check | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify .ai/quality/mutation-baseline.toml ...` | 0 | R3 because the mutation baseline governs the critical quality gate. |
| `red-first` | retained-report comparison against the pre-change baseline | 1 | Four failures: total `4,406 != 4,568`; 53 unexplained survivors; 29 baseline survivors now killed; derived score `0.9087 < 0.9108`. |
| `baseline-green` | identical retained-report comparison after wholesale regeneration | 0 | `check_baseline` returns `[]`; targets and all summary fields match, and the classified survivor set exactly equals the observed set. |
| `focused-quality` | `uv run pytest -q tests/test_quality_mutation.py tests/test_quality_hooks.py` | 0 | 38 tests passed; one expected native-Windows Mutmut test skipped. |
| `ratchet-structure` | TOML/report/policy structural assertion script | 0 | Total `4,568 > 4,406`; 22 targets match report and policy; all 417 survivors are classified exactly once; all unhealthy statuses are zero. |
| `scope-boundary` | `git diff --exit-code origin/main...HEAD -- .ai/quality/mutation.toml pyproject.toml scripts tests core research live monitoring` | 0 | No mutation policy, target, selection, threshold, tooling, test, or production file changed. |
| `impact` | `$env:PATH='C:\Program Files\Git\bin;' + $env:PATH; uvx --from rust-just just impact origin/main` | 0 | No changed production file, direct/transitive test edge, critical-path production escalation, or unknown dynamic edge. |
| `security` | `$env:PATH='C:\Program Files\Git\bin;' + $env:PATH; uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit found no known vulnerabilities, and Ruff security checks passed. |
| `pr-ready-audit` | `$env:PATH='C:\Program Files\Git\bin;' + $env:PATH; uvx --from rust-just just pr-ready ISSUE-118 origin/main` | 0 | The artifact and all 14 R3 gate records validate for implementation HEAD `b810129`; delivery nevertheless remains draft by Jan's explicit instruction. |

## Linux source measurement

- Workflow: [Critical mutation run 30333581031](https://github.com/QPlus-Capital/trading-system/actions/runs/30333581031)
- Source: `main@494eafc5404bb9148c1df0887f7260b189cc36d6`
- Event: manually dispatched on `main`
- Mutation self-test: passed
- Mutmut/Python: Mutmut `3.5.0`, Python `3.13`, Linux
- Result: total `4,568`; killed `4,151`; survived `417`; all other statuses zero
- Retained artifact: `mutation-critical-result`, GitHub artifact digest
  `sha256:f37188fba97dd64f1d861a3b3105ab59811b9ad9d6aeabd6a2a1adef5a51f0e9`
- Extracted `critical.toml` SHA-256:
  `e56acfc4b4c57770a15d800379955a2a15e25e09c45d0725aa1165029729fd71`

The workflow conclusion is `failure` solely because it compared the sound result with the stale
`4,406`-mutant baseline. The mutation self-test passed, the execution completed, the report has no
timeout/no-test/skipped/suspicious/not-checked outcome, and the report was retained successfully.
Replaying the comparator against this branch's regenerated baseline exits `0`.

## Ratchet tightening proof

- Exact total increases: `4,406 -> 4,568` (`+162`).
- Killed count increases: `4,013 -> 4,151` (`+138`).
- Exact survivor count changes: `393 -> 417` (`+24` net), comprising 364 preserved names,
  29 removed now-killed names, and 53 newly generated names.
- All 53 new names are confined to code changed by #96:
  - `research.portfolio.path_risk.x_replay_scenario_path`: 14;
  - `research.portfolio.sizing.x__daily_diagnostics`: 1;
  - `research.portfolio.sizing.x__synchronized_h4_minima`: 38.
- #97 and #98 increase/change the measured mutant surface but introduce no unexplained survivor.
- The 53 new names are classified conservatively as `meaningful` gaps, never guessed equivalent.
- Every survivor is allowed by exact name; any 418th survivor fails closed.
- All 29 formerly allowed survivors now killed are removed. This is the direct ratchet tightening.
- No target, mutant pattern, test selection, comparison implementation, or configured threshold
  changed.

The derived score moves from `4,013 / 4,406 = 0.9108034498` to
`4,151 / 4,568 = 0.9087127846`. This is reported rather than hidden: it is a consequence of the
expanded measured code surface, not a changed threshold or comparison rule. The exact-name survivor
ratchet is stricter because the 29 killed names are no longer allowed.

## Coverage and mutation

The retained Linux report covers the complete configured critical scope: 22 targets and 4,568
mutants. The mutation self-test passed, every mutant reached a terminal killed/survived state, all
unhealthy statuses are zero, and the regenerated exact-name comparator passes. Local focused,
property, integration, invariant, and full-suite coverage commands are recorded above.

## Newly killed survivors

All 29 baseline survivors now measured killed are removed:

1. `research.portfolio.path_risk.x_replay_scenario_path__mutmut_133`
2. `research.portfolio.path_risk.x_replay_scenario_path__mutmut_134`
3. `research.portfolio.path_risk.x_replay_scenario_path__mutmut_135`
4. `research.portfolio.path_risk.x_replay_scenario_path__mutmut_138`
5. `research.portfolio.path_risk.x_replay_scenario_path__mutmut_139`
6. `research.portfolio.path_risk.x_replay_scenario_path__mutmut_140`
7. `research.portfolio.path_risk.x_replay_scenario_path__mutmut_69`
8. `research.portfolio.sizing.x__daily_diagnostics__mutmut_83`
9. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_116`
10. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_148`
11. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_152`
12. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_153`
13. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_188`
14. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_224`
15. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_225`
16. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_228`
17. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_230`
18. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_25`
19. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_33`
20. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_37`
21. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_44`
22. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_46`
23. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_48`
24. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_52`
25. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_59`
26. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_63`
27. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_90`
28. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_94`
29. `research.portfolio.sizing.x__synchronized_h4_minima__mutmut_96`

## Workflow finding

Mutmut `3.5.0` requires `fork` and cannot run on the operator's native Windows machine. The
repository intentionally skips the Linux-only mutation self-test locally and executes the critical
scope in a dedicated Ubuntu job. When #96, #97, and #98 merged under the documented
infrastructure-red exception while the organisation's Actions allowance was exhausted until
2026-08-01, this gate had no local substitute. The production and deterministic Windows gates could
be run, but the baseline's mutant total and exact survivor set could not be refreshed until a Linux
run started.

This is a workflow finding, not a claim that the mutation harness failed: run `30333581031` proves
the self-test and harness are sound. The missing local execution environment allowed the committed
comparison artifact to become stale.

## Scope confirmation

The committed change is limited to:

- `.ai/quality/mutation-baseline.toml`;
- `.ai/tasks/ISSUE-118/`.

No open pull-request branch was checked out, edited, rebased, or pushed. No live runner or MT5
terminal was touched.

## Deferred checks

- Independent Claude review and Jan's merge decision.
- No new Linux mutation execution is claimed for this branch; the wholesale baseline is bound to
  retained run `30333581031` on the identical production/tooling state. The pull request remains
  draft and must not be marked ready.
