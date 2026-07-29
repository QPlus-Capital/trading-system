# Evidence

## HEAD

HEAD: 7727beee1549c67991c641bc887bfef6f6ef5a4e

This is the last non-evidence commit. The final evidence-only commit does not change production
code, tests, configuration, or the measured mutation baseline.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `just check-fast origin/main` | 0 | All 14 changed Python files were formatted; Ruff and strict mypy passed. |
| `docs-consistency` | `just check` plus `uv run python -m scripts.quality.validate_task --task-id ISSUE-121 --base origin/main` | 0 | Engineering-document guards passed; the task artifact is valid with 18 acceptance criteria and 14 invariants. |
| `check` | `just check` | 0 | Ruff, strict mypy over 181 files, Vulture, and pytest passed: 1,369 passed, one Windows-only mutation skip, 98 warnings. |
| `impacted-tests` | `just check-fast origin/main` | 0 | All 204 directly and transitively affected account, notification, preflight, parity, runner, dashboard, risk-view, sizing, swap, and signal-parity tests passed with fakes only. |
| `property-tests-where-applicable` | `just check-properties` | 0 | The property suite passed twice with seed 20260721: 21 passed on each run. |
| `integration-tests` | `just check-fast origin/main` | 0 | The real dotenv parser plus preflight, notification, parity, swap-analysis, dashboard, runner, and live CLI boundaries were exercised through synthetic input and bridges; 204 focused tests passed and no terminal was initialized. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-121 --base origin/main` | 0 | Task artifact valid: 18 acceptance criteria and 14 invariants. |
| `adversarial-review` | [Claude final independent review](https://github.com/QPlus-Capital/trading-system/pull/123#pullrequestreview-4807831900), submitted 2026-07-29, and `.ai/tasks/ISSUE-121/review.md` | 0 | **No finding.** The production `_contains_login_literal` caught all 15 reintroduction forms, including ten that evaded the previous guard. Five unrelated-number probes produced no false positive, and the actual 375-file tracked tree produced zero hits. `_LOGIN_SUFFIXES` derives from `ACCOUNTS`, so a third account extends the guard. |
| `invariants` | `just check-invariants` | 0 | All 519 critical-invariant tests passed with 12 warnings. |
| `mutation-on-touched-critical` | GitHub Actions Critical mutation run `30454030879` | 0 | Linux ratchet passed on `7727bee`: 27 targets, 5,171 total, 4,761 killed, 410 exact-name survivors, and every unhealthy outcome zero. The baseline is regenerated from run `30452526580`'s retained artifact over the identical non-evidence tree. |
| `parity-where-applicable` | 80-case profile/login/currency decision oracle plus the independent review's 96-case accepting-path differential | 0 | Removing `execute` produced zero accept/refuse divergences across 80 combinations; the earlier review measured zero accepting-path divergences across 96 combinations. |
| `live-money-review` | [Claude final independent review](https://github.com/QPlus-Capital/trading-system/pull/123#pullrequestreview-4807831900), submitted 2026-07-29, and `.ai/tasks/ISSUE-121/review.md` | 0 | **No finding.** The login guard is stronger without broadening to unrelated numbers: seed `20260721`, magic `770077`, `x = 12_345`, `total = 4646`, and an SSRN identifier remain accepted. The one deleted assertion was replaced by the production-function assertion, and the independent forms were added to the existing guard test's parameter list. No MT5 terminal, runner, account, or order was touched. |
| `human-decision-escalation` | `.ai/tasks/ISSUE-121/spec.md` | 0 | Jan's environment, code-owned four-digit suffix, public-history, restart, merge, and go-live decisions are explicit. |
| `no-autonomous-merge` | requested draft-only delivery | 0 | No ready, merge, or auto-merge action is authorized. |

### Additional evidence

| Check | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_live_accounts.py::test_guard_refuses_when_the_login_environment_is_missing` | 1 | RED as required: `Failed: DID NOT RAISE SystemExit`; the old guard silently skipped the missing login. |
| `red-first-expanded` | `uv run pytest -q tests/test_live_accounts.py tests/test_live_run_cli.py` | 1 | RED at collection: the pre-change `LiveAccount` did not accept `expected_login_env`. |
| `review-red-first` | `uv run pytest -q tests/test_live_accounts.py tests/test_live_parity_check.py tests/test_research_swap_analysis.py tests/test_monitoring_dashboard.py -k "preflight_masks or login_literal_guard or tracked_text or wrong_terminal"` | 1 | Nine failures reproduced F1-F4: three missed canonical login forms, excluded/partial tracked trees, two disclosed login values, and all three unguarded consumers. |
| `review-red-first-suffix` | `uv run pytest -q tests/test_live_accounts.py::test_code_owned_login_suffix_rejects_a_consistent_other_profile_copy` | 1 | RED as required: `Failed: DID NOT RAISE SystemExit`; copying the MEX identity into the TTP variables formerly self-validated. |
| `review-N1-N4-red-first` | `uv run pytest -q tests/test_live_accounts.py tests/test_live_notify.py -k "plausible_reintroduction or ai_task_login_suffix or documented_env_layout or operator_docs or longer_than or no_mode_parameter or missing_remote_notification"` | 1 | Actual RED: 16 failed and 12 passed. Ten serialization forms escaped the scan; `.ai` suffix evidence, uv round-trip, both operator guides, short-login refusal, dead-signature removal, and loud notification fallback all failed. |
| `latest-review-red-first` | `uv run pytest -q tests/test_live_accounts.py -k "tracked_code_is_caught_however or underscore_separated_login_literal or widening_the_suffix_rule or suffix_rule_covers_every or normalising_digit_underscores"` | 1 | Actual RED: 11 failed and three passed. All eight independently written code forms depended on the `.ai`-only suffix rule, while all three digit-underscore forms evaded both matchers; the tree-wide and per-account feasibility checks passed. |
| `latest-review-focused-green` | same focused command as `latest-review-red-first` | 0 | All 14 review cases passed after applying the account-derived suffix rule tree-wide and normalizing digit separators. |
| `account-guard-focused-green` | `uv run pytest -q tests/test_live_accounts.py` | 0 | All 81 account identity and anti-recommit guard tests passed. |
| `review-focused-green` | `uv run pytest -q tests/test_live_accounts.py tests/test_live_notify.py tests/test_live_run_cli.py tests/test_live_parity_check.py tests/test_research_swap_analysis.py tests/test_monitoring_dashboard.py` | 0 | All 94 focused account, notification, and consumer tests passed; `just check-fast` later passed all 147 impact-selected tests. |
| `guard-mode-differential` | `uv run pytest -q tests/test_live_accounts.py::test_guard_account_accept_refuse_matrix_matches_the_mode_independent_rule` | 0 | Two profiles x ten login values x four currencies: 80 comparisons, zero accept/refuse divergences after removing `execute`. |
| `impact` | `just impact origin/main` | 0 | R3; all seven changed production paths, direct and transitive tests, and the new notification critical escalation identified, with no unknown or dynamic edge. |
| `security` | `just check-security` | 0 | Secret scan clean, pip-audit found no known vulnerabilities, and Ruff security checks passed. |
| `tracked-content` | repository guard in `tests/test_live_accounts.py` | 0 | The scan proves `live/accounts.py` and the test tree are present before checking; after digit-underscore normalization, zero assignment-shaped login literals or account-derived known suffixes exist across the rebased 380-file tracked tree. No unclassified long number in `.env.example`/docs or operator-home path was found. |
| `diff-integrity` | `git diff --check origin/main...HEAD` | 0 | No whitespace errors. |
| `mutation-N2-harness` | GitHub Actions run `30436434645` | 1 | The new operator-document test exposed that Mutmut did not copy `RUN.md`; adding that required input to `also_copy` fixed the sandbox without skipping or weakening a test. |
| `mutation-N1-N4-first` | GitHub Actions run `30436603792` | 1 | Measured 4,704 total, 4,288 killed, 416 survivors. The three obsolete `execute` survivors disappeared; six previously unmeasured `Notifier.__init__` beep mutants survived. |
| `mutation-N1-N4-tested` | GitHub Actions run `30437328697` | 1 | Behavioral platform/opt-in tests killed five notifier survivors: 4,293/4,704 killed, 411 survived. The old baseline then failed only because its three removed names and one Mutmut-trampoline-equivalent name required regeneration. |
| `mutation-N1-N4-final` | GitHub Actions run `30437957532` | 0 | Mutation self-test and exact ratchet passed at 4,293/4,704 killed with 411 exact-name survivors; all unhealthy statuses were zero. |
| `phase-2-merge-guards` | focused account/dashboard suites plus a temporary six-record runner matrix and the committed foreign-only regressions | 0 | The 380-file tracked tree has zero login hits while `logins = [...]`, `assert state.login == ...`, and `504_071_681` are caught. An undecodable record halted at first, middle, and last in a six-record enumeration for both `magic == MAGIC` and `magic is None` (six cases); foreign-only records block with `inf` without halting or flattening (three cases). All 27 mutation targets include `live-runner-fail-closed`, both dashboard tests survive, and all sixteen disjoint finding IDs are present. |
| `mutation-merged-measurement` | GitHub Actions Critical mutation run `30452526580`; downloaded `mutation-critical-result/critical.toml`; `check_baseline(report, load_baseline())` | 0 | The first merged-tree workflow executed all 27 targets and retained 5,171 outcomes: 4,761 killed, 410 survived, all unhealthy counts zero. Its workflow exit 1 was the expected stale 24-target baseline mismatch. Regenerating from that artifact made the exact local ratchet check return no issues; no survivor was invented or hand-merged. |
| `readiness-audit` | `uv run python -m scripts.quality.pr_ready ISSUE-121 --base origin/main` | 0 | READY against current `origin/main` `14f0cdb`: all 14 required R3 gates have exit 0, task artifacts and risk class pass, and evidence covers non-evidence HEAD `7727bee`. |

## Red-first proof

The load-bearing AC-03 test was run before implementation. With the login variable absent, the old
code returned from `guard_account()` instead of refusing, so pytest failed with `DID NOT RAISE
SystemExit`. The expanded pre-implementation suite also failed because the environment-variable
profile boundary did not exist.

The independent-review guards were also executed before their fixes. Nine focused failures proved
that the preflight disclosed both values, the leak scan missed all three requested forms and could
scan an incomplete tree, and the three consumers read account-specific data without an identity
guard. The code-owned suffix test separately failed with `DID NOT RAISE SystemExit` for a consistent
MEX-to-TTP copy. The N1-N4 suite then produced 16 actual failures: ten missed secret
serializations, a missing `.ai` suffix rule, uv's documented-layout truncation, two missing operator
warnings, the short-login suffix acceptance, the inert mode parameter, and silent loss of remote
alerts. None of these failures was fabricated or inferred.

The latest reviewer-supplied oracle was folded into the repository before remediation. Its focused
run produced exactly 11 failures and three passing feasibility checks: eight independent code
representations proved that the suffix matcher was ineffective outside `.ai/**`, and three
underscore-separated Python integer literals evaded both matchers. The same 14 cases are green
after the fix, and the complete account suite passes 81 tests.

## Impact

`just impact origin/main` classified the change R3 because `live/accounts.py` is the live-money
identity boundary. Direct consumers are `live.run`, the live-facing `just` recipes, preflight,
parity, monitoring startup, the swap-snapshot refresh, and the notification fan-out. Configured
account behavior is exercised through synthetic bridges only. Missing, malformed, placeholder,
too-short, wrong-suffix, or mismatching identity stops before terminal connection or the first
account-specific data read. Missing or partial Telegram configuration now emits a redacted warning.

No strategy, research, portfolio, sizing, risk-limit, order-placement, or reported-result path
changed. Account currency, starting balance, symbol overrides, and valid-input behavior remain
unchanged.

## Security summary

The repository guard found no tracked broker-login literal or account-derived known login suffix
anywhere in the tracked tree after digit-underscore normalization, and no
unclassified bare long number in `.env.example` or documentation, or operator-home terminal path.
It covers 30 committed serialization forms plus three digit-underscore forms, includes tests,
resolves the real Git top-level, and fails if sentinel paths or a plausible file count are absent.
`.env.example` contains inert,
single-quoted placeholders only. Refusal and notification messages never echo a login, token, or
chat identifier; preflight masks connected and expected logins as `***NNN`.
`just check-security` passed: secret scan clean, no known dependency vulnerabilities, and
static-security checks green.

Operational warning: `uv run --env-file .env` does **not** override an environment variable already
exported by the invoking shell. A stale PowerShell `$env:MT5_TTP_LOGIN` silently takes precedence
over `.env`; the operator must clear or verify exported `MT5_*` variables before starting a command.
The code-owned suffix catches cross-profile copies but cannot distinguish two accounts sharing the
same suffix.

## Coverage and mutation

Behavioral coverage pins successful resolution, wrong-account refusal, missing configuration,
malformed/blank/padded/non-positive/placeholder/too-short values, refusal-message non-disclosure,
pre-connect CLI refusal, 30 secret serialization forms, a tree-wide suffix rule derived from every
configured account, digit-underscore normalization, real uv
round-trip of Windows paths and later Telegram values, mode-independent identity decisions, loud
redacted notification fallback, and Windows-only opt-in beep behavior.

The merged Linux Critical mutation run
[30454030879](https://github.com/QPlus-Capital/trading-system/actions/runs/30454030879) passed the
exact-name ratchet over all 27 targets with 5,171 total, 4,761 killed, and 410 survivors. The
baseline was regenerated from the retained artifact of the preceding identical-tree measurement
[30452526580](https://github.com/QPlus-Capital/trading-system/actions/runs/30452526580), not from
either conflicting predecessor baseline.

Against #103/#105's 5,113/4,704/409 predecessor, the three #121 targets add 58 mutants, 57 kills,
and the already-classified unreachable `Notifier.__init__` default-argument mutant. Against #121's
4,704/4,293/411 predecessor, the merged `live-runner-fail-closed` target and ordering guard add 467
mutants and 468 kills while killing
`live.risk_control.xǁRiskControllerǁmust_flatten__mutmut_3`; the survivor set therefore tightens by
one. There were no unexplained survivors, timeouts, suspicious results, tests without coverage, or
mutation errors.

## Live safety attestation

No MT5 terminal was initialized or queried. Neither running runner was touched, stopped, or
restarted, and no order was placed, modified, or closed. Every live-boundary verification used
synthetic environment values, fakes, or static tracked-file inspection.

## Deferred checks

- Jan must populate the four real values from the password manager and choose a quiet restart
  window before this can be deployed.
- Jan must still make the PR ready and merge it. This evidence does not authorize a ready, merge,
  or auto-merge action.
