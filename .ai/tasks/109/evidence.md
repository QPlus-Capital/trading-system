# Evidence

## HEAD

HEAD: ae64907f8f633f72a83e26cda6a9dd6152b19d93

Only this evidence file may change after the tested implementation commit.

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_quality_classify.py tests/test_engineering_docs.py` before the TOML change | 1 | RED: **9 failed, 90 passed**. Both executable-contract cases, architecture R2, catch-all coexistence, duplicate-rule removal, tracked-tree reconstruction, and the new engineering-doc guards failed. |
| `format` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: both changed Python files were already Ruff-formatted; Ruff and strict mypy passed. |
| `docs-consistency` | `uv run pytest -q tests/test_engineering_docs.py tests/test_gate_consistency.py tests/test_docs_language.py` | 0 | GREEN: **142 passed**. |
| `check` | `uvx --from rust-just just check` | 0 | GREEN: Ruff, strict mypy over 181 source files, Vulture, and **1298 tests passed**; one native-Windows mutation test skipped. |
| `impacted-tests` | `uvx --from rust-just just check-fast origin/main` | 0 | GREEN: impact selected `tests/test_engineering_docs.py` and `tests/test_quality_classify.py`; **99 passed**. |
| `property-tests-where-applicable` | `uvx --from rust-just just check-properties` | 0 | GREEN: **21 properties passed twice** with seed `20260721`. |
| `integration-tests` | `uv run pytest -q tests/test_quality_classify.py tests/test_quality_pr_ready.py tests/test_quality_impact.py tests/test_quality_hooks.py` | 0 | GREEN: **85 passed** across classifier/readiness/impact/hook consumers. |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task 109 --base origin/main` | 0 | GREEN: task 109 is valid with five acceptance criteria and four invariants. |
| `adversarial-review` | [Claude independent review](https://github.com/QPlus-Capital/trading-system/pull/129#pullrequestreview-4810102389), submitted 2026-07-29 | 0 | **No finding.** The reviewer classified all 380 tracked files under both `main` and branch rule sets: zero classifications were lowered and exactly twelve were raised (eleven `.claude/**` contracts R0 to R3 and `docs/architecture.md` R0 to R2). All five acceptance-criterion path cases were checked through the production classifier. Four not-yet-existing paths under `.github/workflows/`, `.claude/skills/`, `.claude/agents/`, and bare `.claude/` also classified R3, proving the broad globs fail closed for future workflow contracts. |
| `invariants` | `uvx --from rust-just just check-invariants` | 0 | GREEN: **443 passed**, including the production classifier and tracked-tree guards. |
| `mutation-on-touched-critical` | GitHub Actions Critical mutation run `30459101696` | 0 | GREEN on reviewed head `ae64907`: Linux executed the unchanged 24-target critical ratchet, killed 4,704 of 5,113 mutants, retained the 409 exact-name survivors, and passed. No mutation target or baseline changed in this PR. |
| `parity-where-applicable` | `git diff --exit-code origin/main...HEAD -- live monitoring research core .ai/quality/mutation-baseline.toml .ai/quality/mutation.toml` | 0 | GREEN: no trading, signal, sizing, risk, result, mutation-policy, or mutation-baseline file changed. |
| `live-money-review` | changed-path and scoped-diff audit | 0 | GREEN: no live path, terminal, runner, account, order, risk limit, market data, or research result was touched. |
| `human-decision-escalation` | issue #109 plus project permit inspection | 0 | GREEN: Jan approved the exact R3 scope; no unresolved business, methodology, live-money, architecture, or risk decision remains. |
| `no-autonomous-merge` | branch and delivery-state inspection | 0 | GREEN: feature branch and draft-only delivery; no ready transition, auto-merge, or merge. |

## Additional evidence

| Check | Command | Exit status | Result |
|---|---|---:|---|
| `risk-classification` | `uv run python -m scripts.quality.classify --base origin/main` | 0 | R3 because the authoritative risk model and governance companion changed. |
| `tracked-tree-differential` | production `classify_path` over `git ls-files -z`, reconstructed pre-change model versus committed model | 0 | **380 tracked paths**, **12 class increases**, **0 decreases**. The increases are exactly 11 `.claude/**` contracts from R0 to R3 plus `docs/architecture.md` from R0 to R2. |
| `dead-rule-differential` | add the removed `.github/workflows/**` R2 rule back and classify all 380 tracked paths | 0 | **0 path changes**. The retained R3 rule wins for every matching workflow path, proving the R2 rule was dead. |
| `focused-classification` | `uv run pytest -q tests/test_quality_classify.py tests/test_engineering_docs.py` | 0 | **99 passed** after implementation. |
| `security` | `uvx --from rust-just just check-security` | 0 | Secret scan clean, pip-audit found no known vulnerabilities, and Ruff security checks passed. |
| `impact` | `uvx --from rust-just just impact origin/main` | 0 | No changed production module; direct tests are the two classifier/document guard files. The full suite remains binding. |

## Permit and baseline

- Start facts verified before code changes: card `Ready to Implement`, labels `approved` and
  `risk:R3`, open issue #109.
- The requested hash `8b75ff0` was no longer `origin/main`; fetched `origin/main` was `14f0cdb`.
  The branch was created from the actual current `origin/main`, not from unmerged issue #107.
- The required GitHub state transition was performed in the correct internal order—card to
  `Implementing`, then remove `approved`—but it was performed after local test/spec work had begun.
  This timing deviation is recorded rather than represented as compliant.

## Coverage and mutation

The behavioural and structural guards call the production classifier. Expected classes are literal.
The complete tracked-tree comparison rejects every downgrade and every upgrade outside the approved
scope. Reintroducing the removed workflow R2 rule changes zero classifications.

The change touches no configured production mutation target. Native Windows cannot execute Mutmut
3.5 and has no WSL installation, so the local mutation attempt exits 1 at the platform guard. The
Linux `mutation-critical` PR workflow is the remaining mutation evidence; no survivor baseline,
target, threshold, or test selection changed.

## Deferred checks

- Jan must still make the PR ready and merge it. This evidence does not authorize a ready, merge,
  or auto-merge action.
