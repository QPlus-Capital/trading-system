# Evidence

## HEAD

HEAD: 198d66a2761abe8f6a4153c317f86a94b5baa651

Branch `claude/125-mutation-total`, rebased onto `origin/main` at `14f0cdb`.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_mutation.py` before the production change | 1 | RED: **1 failed, 150 passed** — `test_added_production_code_alone_no_longer_fails_the_ratchet` failed with `mutation total changed: expected 4646, observed 4774`. The single failure is the criterion under change; every preservation test and all 128 differential cases were already green. |
| `red-first` | `uv run pytest -q tests/test_quality_mutation.py -k both_totals_stay_visible` after extracting `summary_lines` behaviour-preserving and before adding the baseline total | 1 | RED: **2 failed** — `assert '4646' in 'Mutation critical: 4364/4775 killed, 411 survived; report critical.toml'`, on both the passing-run and the failing-run case. |
| `125-R1-red-first` | `uv run pytest -q tests/test_quality_mutation.py -k "policy_substitution or policy_fingerprint_ignores or baseline_without_a_policy_fingerprint or report_serializes_its_required_policy_fingerprint"` before the fingerprint implementation | 1 | RED: **4 failed, 156 deselected**. The same-ID/path coverage substitution returned no issue; the reorder oracle found no fingerprint implementation; a missing-key baseline loaded; and the report omitted the required key. |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: two changed files already formatted; Ruff and strict mypy clean over 181 source files. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_claude_runtime_files.py tests/test_docs_language.py tests/test_docs_architecture_map.py` | 0 | GREEN: **136 passed**. No engineering document changed. |
| `check` | `uvx --from rust-just just check` | 0 | GREEN on committed rebased HEAD: **1,430 passed**, 1 skipped (Mutmut needs fork/WSL on Windows), with Ruff, strict mypy, and Vulture green. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: impact selected `tests/test_quality_mutation.py` as the only directly related suite and discovered no transitive, critical-path or dynamic edge; **161 passed**, 1 skipped. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: **21 properties passed twice** with seed 20260721. |
| `integration-tests` | full pytest within `check` | 0 | GREEN: 1,430 passed with no MT5 terminal initialized and no runner contacted. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: **433 passed**. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 125` | 0 | GREEN: valid with **9 acceptance criteria and 4 invariants**. |
| `security` | `uvx --from rust-just just check-security` | 0 | GREEN: tracked-secret scan, dependency audit and static security checks. The deterministic digest has a line-local detect-secrets allowlist; the synthetic fake-secret guard remains active. |
| `parity-where-applicable` | `git diff --name-only origin/main...HEAD -- core research live monitoring` | 0 | GREEN: zero production trading paths changed. The change is confined to `scripts/quality/mutation.py` and its tests. |
| `mutation-on-touched-critical` | parsed baseline equality oracle plus `uv run pytest -q tests/test_quality_mutation.py -k "policy_fingerprint or policy_substitution or baseline_without_a_policy_fingerprint or report_serializes_its_required_policy_fingerprint or fast_report_fingerprints_the_whole_policy or committed_baseline"` | 0 | GREEN without a Linux rerun: baseline equals current `origin/main` except for the required fingerprint key; 24 targets produce `cfabed37203a17e3a538b8acefaced83c7a8a98ad5c8a67c7585e9924c34c8ce`; summary stays **5,113/4,704/409**, the exact survivor set is unchanged, and **6 focused tests passed**. |
| `live-money-review` | changed-path audit against `live/**`, sizing, risk and broker paths | 0 | GREEN: no live, risk, order or account code changed; no MT5 terminal was initialised and no runner was contacted at any point. |
| `human-decision-escalation` | issue #125 plus Jan's accepted 125-R1 decision | 0 | GREEN: Jan ratified the complete target-definition fingerprint as the specific replacement guard. |
| `no-autonomous-merge` | — | 0 | GREEN: not merged, auto-merge not enabled, not marked ready for review. |
| `adversarial-review` | Claude's independent fingerprint-remediation review in `.ai/tasks/125/review.md` | 0 | GREEN on 2026-07-29: no findings; ten policy variations verified that target/pattern ordering is cosmetic while target and pattern content remains bound. |
| `readiness` | `uv run python -m scripts.quality.pr_ready 125 --base origin/main` | 0 | GREEN: READY on code HEAD `198d66a`; the later evidence-only commit is accepted by the freshness check. |

## Coverage and mutation

No production file under `core`, `research`, `live` or `monitoring` changed, so the critical
trading results and live-money behaviour are unaffected. The quality-policy path is not vacuous:
the committed baseline gains the required whole-policy fingerprint
`cfabed37203a17e3a538b8acefaced83c7a8a98ad5c8a67c7585e9924c34c8ce`.
No target, pattern, threshold, survivor classification, health value, score, or measured total
changed relative to current `origin/main`.

The rebase takes Main's measured 5,113 total, 4,704 killed, 409 survived, zero unhealthy statuses,
24 target IDs, and complete exact-name survivor set. Parsed comparison proves the rebased baseline
is identical to Main except for the one required fingerprint key. No Linux mutation run is needed:
#125 changes no code that generates mutants, and the policy identity is deterministically derived
from `.ai/quality/mutation.toml`. The same whole-policy fingerprint is emitted for fast and critical
scopes; scope selection does not alter it.

`tool_version` is deliberately outside the fingerprint. The installed-version check in
`scripts/quality/mutation.py` refuses a mismatched tool before measurement, while an intentional
version change requires a real mutation run and a newly measured exact survivor set. Including it
in this policy digest would duplicate the former check and could not replace the latter.

### 125-R1 executable counterexample

Before the remediation, the focused red-first command produced four failures:

- a safety-critical killed-only pattern was removed and a broader trivial pattern added while target
  IDs, paths, survivors, health, and the improved score stayed acceptable; `check_baseline` returned
  no issue;
- no policy-fingerprint implementation existed for the ordering oracle;
- a baseline without the fingerprint loaded successfully; and
- the report omitted the required field.

After the remediation, the substitution changes the digest and is rejected, while pure target and
pattern reordering leaves the digest unchanged. Further focused guards prove that target ID, exact
path spelling, pattern content, and pattern multiplicity remain bound. The baseline key is mandatory
and validated as a lowercase SHA-256 digest.

### Real-data replay of the rule change

The strongest available evidence is not synthetic. The artifact `mutation-critical-result` of the
failing Linux run 30432148064 on PR #105 was downloaded and replayed against the baseline committed
at that run's own commit `a221985`, using the production `check_baseline` from this branch:

```
observed total 5106, baseline total 4978
observed score 0.9195, baseline score 0.9178

OLD rule -> 2 issue(s):
  - unexplained surviving mutants: ['live.mt5_bridge.x__position_ticket__mutmut_1',
    'live.runner.xǁLiveRunnerǁ_total_open_risk__mutmut_46']
  - mutation total changed: expected 4978, observed 5106; update the baseline with an explanation

NEW rule -> 1 issue(s):
  - unexplained surviving mutants: ['live.mt5_bridge.x__position_ticket__mutmut_1',
    'live.runner.xǁLiveRunnerǁ_total_open_risk__mutmut_46']
```

The verdict that survives is the one naming the two genuinely uncovered mutants in PR #105's own new
code, one of which is in `_total_open_risk` — the function an independent review separately found to
carry a defect. The verdict that disappears is the one that carried no information about the branch.

### Why total alone is not quality evidence

Two consecutive Linux runs of the same branch, 30431184595 at 07:26 and 30432148064 at 07:42 on
2026-07-29:

| Run | total | unexplained survivors | score |
|---|---|---:|---|
| 30431184595 | 4978 vs 5118 | 53 | regressed, 0.9097 < 0.9178 |
| 30432148064 | 4978 vs 5106 | 2 | passed |

Between the two runs the builder closed 51 real test gaps. Both substantive verdicts moved. The total
verdict did not change state, because the branch still added code. A condition whose state is
independent of test strength cannot detect a test-strength defect.

The accepted review finding identified the narrower exception to the original claim: mutant total
can incidentally move when mutation-policy coverage changes, because policy changes alter which
mutants exist. The total is still not a reliable identity for that policy—it also moves with ordinary
production-code size. The required canonical fingerprint replaces that accidental protection with a
specific binding of every target ID, exact path string, and complete pattern multiset. The total
comparison remains removed.

## Deferred checks

None. The independent review is clean, the deterministic rebase proof is complete, and branch
protection is active on `main`.
