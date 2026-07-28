# Evidence

## HEAD

HEAD: db162cf22dd654323c0348d30ac79c855698d6f2

This is the last non-evidence commit. The final evidence-only commit does not change production
code, tests, configuration, or the measured mutation baseline.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `just check-fast origin/main` | 0 | All ten changed Python files were formatted; Ruff and strict mypy passed. |
| `docs-consistency` | `just check` plus `uv run python -m scripts.quality.validate_task --task-id ISSUE-121 --base origin/main` | 0 | Engineering-document guards passed; the task artifact is valid with 13 acceptance criteria and 12 invariants. |
| `check` | `just check` | 0 | Ruff, strict mypy over 181 files, Vulture, and pytest passed: 1,241 passed, one Windows-only mutation skip, 98 warnings. |
| `impacted-tests` | `just check-fast origin/main` | 0 | All 87 directly and possibly affected account, preflight, parity, runner, dashboard, and swap tests passed with fakes only. |
| `property-tests-where-applicable` | `just check-properties` | 0 | The property suite passed twice with seed 20260721: 21 passed on each run. |
| `integration-tests` | `just check-fast origin/main` | 0 | The real preflight, parity, swap-analysis, dashboard, and live CLI boundaries were exercised through synthetic bridges; 87 focused tests passed and no terminal was initialized. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id ISSUE-121 --base origin/main` | 0 | Task artifact valid: 13 acceptance criteria and 12 invariants. |
| `adversarial-review` | `.ai/tasks/ISSUE-121/review.md` | 1 | The first independent review found F1-F5 and all are dispositioned; a complete re-review of the material remediation is required before readiness. |
| `invariants` | `just check-invariants` | 0 | All 356 critical-invariant tests passed with 12 warnings. |
| `mutation-on-touched-critical` | GitHub Actions Critical mutation run `30371059049` | 0 | Linux ratchet passed: 4,682 total, 4,269 killed, 413 exact-name survivors, and zero unexplained, timeout, suspicious, no-test, or error outcomes. |
| `parity-where-applicable` | independent review's 96-case differential plus accepting-path regression tests | 0 | The independent review measured zero divergences against `origin/main` across 96 accepting-path combinations; the remediation adds only refusal checks before data reads and preserves the already-verified accepting path. |
| `live-money-review` | `.ai/tasks/ISSUE-121/review.md` | 1 | The first live-money review validated AC-03/INV-01 and found F1-F5; the material boundary remediation requires a complete re-review. |
| `human-decision-escalation` | `.ai/tasks/ISSUE-121/spec.md` | 0 | Jan's environment, code-owned four-digit suffix, public-history, restart, merge, and go-live decisions are explicit. |
| `no-autonomous-merge` | requested draft-only delivery | 0 | No ready, merge, or auto-merge action is authorized. |

### Additional evidence

| Check | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_live_accounts.py::test_guard_refuses_when_the_login_environment_is_missing` | 1 | RED as required: `Failed: DID NOT RAISE SystemExit`; the old guard silently skipped the missing login. |
| `red-first-expanded` | `uv run pytest -q tests/test_live_accounts.py tests/test_live_run_cli.py` | 1 | RED at collection: the pre-change `LiveAccount` did not accept `expected_login_env`. |
| `review-red-first` | `uv run pytest -q tests/test_live_accounts.py tests/test_live_parity_check.py tests/test_research_swap_analysis.py tests/test_monitoring_dashboard.py -k "preflight_masks or login_literal_guard or tracked_text or wrong_terminal"` | 1 | Nine failures reproduced F1-F4: three missed canonical login forms, excluded/partial tracked trees, two disclosed login values, and all three unguarded consumers. |
| `review-red-first-suffix` | `uv run pytest -q tests/test_live_accounts.py::test_code_owned_login_suffix_rejects_a_consistent_other_profile_copy` | 1 | RED as required: `Failed: DID NOT RAISE SystemExit`; copying the MEX identity into the TTP variables formerly self-validated. |
| `review-focused-green` | `uv run pytest -q tests/test_live_accounts.py tests/test_live_run_cli.py tests/test_live_parity_check.py tests/test_research_swap_analysis.py tests/test_monitoring_dashboard.py` | 0 | All 63 focused account-boundary and consumer tests passed. |
| `impact` | `just impact origin/main` | 0 | R3; all five changed production paths and their direct tests identified, with no unknown or dynamic edge. |
| `security` | `just check-security` | 0 | Secret scan clean, pip-audit found no known vulnerabilities, and Ruff security checks passed. |
| `tracked-content` | repository guard in `tests/test_live_accounts.py` | 0 | The scan proves `live/accounts.py` and the test tree are present before checking; zero canonical login literals, unclassified long numbers in `.env.example`/docs, or operator-home paths were found. |
| `diff-integrity` | `git diff --check origin/main...HEAD` | 0 | No whitespace errors. |
| `mutation-harness-1` | GitHub Actions run `30359017703` | 1 | Infrastructure/configuration proof: Mutmut did not copy `.env.example`; fixed by adding the required test input to `also_copy`, without skipping a test. |
| `mutation-harness-2` | GitHub Actions run `30359179678` | 1 | Infrastructure/configuration proof: Mutmut did not copy `justfile`; fixed by adding the required test input to `also_copy`, without weakening the gate. |
| `mutation-first-complete` | GitHub Actions run `30359343709` | 1 | 4,672 total, 4,254 killed, 418 survived; eight new `live.accounts` survivors exposed missing outcome assertions. |
| `mutation-final` | GitHub Actions run `30360688026` | 0 | Seven account survivors killed by behavioral tests; the sole remaining account mutant is proven equivalent and named exactly in the baseline. |
| `mutation-review-first` | GitHub Actions run `30370163325` | 1 | Measured 4,682 total, 4,269 killed, and 413 survivors; the only new survivors were two exact `guard_connected_account` compatibility-argument mutations and the target/total required a baseline refresh. |
| `mutation-review-final` | GitHub Actions run `30371059049` | 0 | Mutation self-test passed; the Critical ratchet passed at 4,269/4,682 killed with 413 exact-name survivors. |
| `readiness-audit` | `uv run python -m scripts.quality.pr_ready ISSUE-121 --base origin/main` | 1 | Expected `NOT READY`: executable gates pass, while the complete independent adversarial and live-money re-reviews remain required. |

## Red-first proof

The load-bearing AC-03 test was run before implementation. With the login variable absent, the old
code returned from `guard_account()` instead of refusing, so pytest failed with `DID NOT RAISE
SystemExit`. The expanded pre-implementation suite also failed because the environment-variable
profile boundary did not exist.

The independent-review guards were also executed before their fixes. Nine focused failures proved
that the preflight disclosed both values, the leak scan missed all three requested forms and could
scan an incomplete tree, and the three consumers read account-specific data without an identity
guard. The code-owned suffix test separately failed with `DID NOT RAISE SystemExit` for a consistent
MEX-to-TTP copy. None of these failures was fabricated or inferred.

## Impact

`just impact origin/main` classified the change R3 because `live/accounts.py` is the live-money
identity boundary. Direct consumers are `live.run`, the live-facing `just` recipes, preflight,
parity, monitoring startup, and the swap-snapshot refresh. Configured-account behavior is exercised
through synthetic bridges only. The stricter failure mode is deliberate: missing, malformed,
placeholder, wrong-suffix, or mismatching identity now stops before terminal connection or before
the first account-specific data read instead of disabling the guard.

No strategy, research, portfolio, sizing, risk-limit, order-placement, or reported-result path
changed. Account currency, starting balance, symbol overrides, and valid-input behavior remain
unchanged.

## Security summary

The repository guard found no tracked broker-login literal, unclassified bare long number in
`.env.example` or documentation, or operator-home terminal path. It includes tests, resolves the
real Git top-level, and fails if sentinel paths or a plausible file count are absent. `.env.example`
contains inert placeholders only. Refusal messages name the profile or environment variable but
never echo its value, and preflight masks connected and expected logins as `***NNN`.
`just check-security` passed: secret scan clean, no known dependency vulnerabilities, and
static-security checks green.

Operational warning: `uv run --env-file .env` does **not** override an environment variable already
exported by the invoking shell. A stale PowerShell `$env:MT5_TTP_LOGIN` silently takes precedence
over `.env`; the operator must clear or verify exported `MT5_*` variables before starting a command.
The code-owned suffix catches cross-profile copies but cannot distinguish two accounts sharing the
same suffix.

## Coverage and mutation

Behavioral coverage pins successful resolution, wrong-account refusal, missing configuration in
both execute and signal-only use, malformed/blank/padded/non-positive/placeholder values, refusal
message non-disclosure, pre-connect CLI refusal, `.env.example`, and actual `just` entrypoint
loading.

The final Linux Critical mutation run
[30371059049](https://github.com/QPlus-Capital/trading-system/actions/runs/30371059049) passed the
exact-name ratchet with 4,682 total, 4,269 killed, and 413 survivors. The review remediation added
ten mutants; eight were killed. The two added survivors,
`live.accounts.x_guard_connected_account__mutmut_4` and `__mutmut_8`, replace the helper's
`execute=False` argument with `None` or `True`. `guard_account()` intentionally discards that
compatibility parameter, so neither mutation can affect the bridge read, comparisons, refusal,
return value, control flow, or output. They are proven equivalent rather than inconvenient. There
were no unexplained survivors, timeouts, suspicious results, tests without coverage, or mutation
errors.

## Live safety attestation

No MT5 terminal was initialized or queried. Neither running runner was touched, stopped, or
restarted, and no order was placed, modified, or closed. Every live-boundary verification used
synthetic environment values, fakes, or static tracked-file inspection.

## Deferred checks

- A complete independent adversarial re-review is required because the remediation materially
  changes live, monitoring, and research-snapshot boundaries.
- A complete independent live-money re-review is required for the same reason.
- Jan must populate the four real values from the password manager and choose a quiet restart
  window before this can be deployed.
- Because these two independent reviews are intentionally outstanding, `pr-ready` is expected to
  report `NOT READY`; the PR must remain draft.
