# Evidence

## HEAD

HEAD: 79f10f4bfbc0a37891e49b011840fd6246e53585

This is the last non-evidence commit. The final evidence-only commit does not change production
code, tests, configuration, or the measured mutation baseline.

## Commands

### Required gates

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `format` | `just check-fast origin/main` | 0 | Four changed Python files formatted; Ruff and strict mypy passed. |
| `docs-consistency` | `just check` plus task validation | 0 | Engineering-document guards and the complete R3 suite passed. |
| `check` | `just check` | 0 | Ruff, strict mypy over 181 files, Vulture, and pytest passed: 1,229 passed, one Windows-only mutation skip, 98 warnings. |
| `impacted-tests` | `just check-fast origin/main` | 0 | All 75 directly and transitively impacted tests passed. |
| `property-tests-where-applicable` | `just check-properties` | 0 | The property suite passed twice with seed 20260721: 21 passed on each run. |
| `integration-tests` | `uv run pytest -q tests/test_live_accounts.py tests/test_live_run_cli.py tests/test_monitoring_dashboard.py` | 0 | All 75 account, CLI, and dashboard integration tests passed using fakes only. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task ISSUE-121` | 0 | Task artifact valid: 9 acceptance criteria and 8 invariants. |
| `adversarial-review` | `.ai/tasks/ISSUE-121/review.md` | 1 | Pending the independent Claude review; the draft must not be marked ready. |
| `invariants` | `just check-invariants` | 0 | All 346 critical-invariant tests passed with 12 warnings. |
| `mutation-on-touched-critical` | GitHub Actions Critical mutation run `30360688026` | 0 | Linux ratchet passed: 4,672 total, 4,261 killed, 411 exact-name equivalent survivors, and zero unexplained, timeout, suspicious, no-test, or error outcomes. |
| `parity-where-applicable` | focused configured-account regression tests | 0 | Valid synthetic account profiles preserve account metadata and guard outcomes; no signals, sizing, risk limits, orders, research artifacts, or trading results changed. |
| `live-money-review` | `.ai/tasks/ISSUE-121/review.md` | 1 | Pending the independent Claude live-money review; the draft must not be marked ready. |
| `human-decision-escalation` | `.ai/tasks/ISSUE-121/spec.md` | 0 | Jan's environment, public-history, restart, merge, and go-live decisions are explicit. |
| `no-autonomous-merge` | requested draft-only delivery | 0 | No ready, merge, or auto-merge action is authorized. |

### Additional evidence

| Check | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_live_accounts.py::test_guard_refuses_when_the_login_environment_is_missing` | 1 | RED as required: `Failed: DID NOT RAISE SystemExit`; the old guard silently skipped the missing login. |
| `red-first-expanded` | `uv run pytest -q tests/test_live_accounts.py tests/test_live_run_cli.py` | 1 | RED at collection: the pre-change `LiveAccount` did not accept `expected_login_env`. |
| `impact` | `just impact origin/main` | 0 | R3; direct live-account, CLI, and dashboard tests plus transitive parity/swap coverage identified; no unknown or dynamic edge. |
| `security` | `just check-security` | 0 | Secret scan clean, pip-audit found no known vulnerabilities, and Ruff security checks passed. |
| `tracked-content` | repository guard using `git ls-files` | 0 | Zero login-shaped literals and zero operator-home paths in tracked production/documentation content. |
| `diff-integrity` | `git diff --check origin/main...HEAD` | 0 | No whitespace errors. |
| `mutation-harness-1` | GitHub Actions run `30359017703` | 1 | Infrastructure/configuration proof: Mutmut did not copy `.env.example`; fixed by adding the required test input to `also_copy`, without skipping a test. |
| `mutation-harness-2` | GitHub Actions run `30359179678` | 1 | Infrastructure/configuration proof: Mutmut did not copy `justfile`; fixed by adding the required test input to `also_copy`, without weakening the gate. |
| `mutation-first-complete` | GitHub Actions run `30359343709` | 1 | 4,672 total, 4,254 killed, 418 survived; eight new `live.accounts` survivors exposed missing outcome assertions. |
| `mutation-final` | GitHub Actions run `30360688026` | 0 | Seven account survivors killed by behavioral tests; the sole remaining account mutant is proven equivalent and named exactly in the baseline. |
| `readiness-audit` | `uv run python -m scripts.quality.pr_ready ISSUE-121 --base origin/main` | 1 | Expected `NOT READY`: every executable gate passed; only independent `adversarial-review` and `live-money-review` remain non-zero, so delivery stays draft. |

## Red-first proof

The load-bearing AC-03 test was run before implementation. With the login variable absent, the old
code returned from `guard_account()` instead of refusing, so pytest failed with `DID NOT RAISE
SystemExit`. The expanded pre-implementation suite also failed because the environment-variable
profile boundary did not exist. Neither failure was fabricated or inferred.

## Impact

`just impact origin/main` classified the change R3 because `live/accounts.py` is the live-money
identity boundary. Direct consumers are `live.run`, the live-facing `just` recipes, and monitoring
startup; the configured-account behavior is exercised through synthetic bridges only. The stricter
failure mode is deliberate: missing, malformed, placeholder, or mismatching identity now stops
before terminal connection instead of disabling the guard.

No strategy, research, portfolio, sizing, risk-limit, order-placement, or reported-result path
changed. Account currency, starting balance, symbol overrides, and valid-input behavior remain
unchanged.

## Security summary

The repository guard found no tracked broker login literal or operator-home terminal path.
`.env.example` contains inert placeholders only. Refusal messages name the profile or environment
variable but never echo its value. `just check-security` passed: secret scan clean, no known
dependency vulnerabilities, and static-security checks green.

## Coverage and mutation

Behavioral coverage pins successful resolution, wrong-account refusal, missing configuration in
both execute and signal-only use, malformed/blank/padded/non-positive/placeholder values, refusal
message non-disclosure, pre-connect CLI refusal, `.env.example`, and actual `just` entrypoint
loading.

The final Linux Critical mutation run
[30360688026](https://github.com/QPlus-Capital/trading-system/actions/runs/30360688026) passed the
exact-name ratchet with 4,672 total, 4,261 killed, and 411 survivors. Seven of the first complete
run's eight `live.accounts` survivors were killed with distinct behavioral assertions. The one
remaining survivor, `live.accounts.x_guard_account__mutmut_1`, changes the ignored compatibility
assignment `_ = execute` to `_ = None`; `execute` intentionally cannot affect identity resolution,
comparisons, control flow, exceptions, or output, so this is equivalent rather than inconvenient.
There were no unexplained survivors, timeouts, suspicious results, tests without coverage, or
mutation errors.

## Live safety attestation

No MT5 terminal was initialized or queried. Neither running runner was touched, stopped, or
restarted, and no order was placed, modified, or closed. Every live-boundary verification used
synthetic environment values, fakes, or static tracked-file inspection.

## Deferred checks

- Independent adversarial review is pending for Claude after the draft PR exists.
- Independent live-money review is pending for Claude after the draft PR exists.
- Jan must populate the four real values from the password manager and choose a quiet restart
  window before this can be deployed.
- Because these two independent reviews are intentionally outstanding, `pr-ready` is expected to
  report `NOT READY`; the PR must remain draft.
