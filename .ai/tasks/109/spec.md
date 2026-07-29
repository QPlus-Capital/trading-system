# Issue 109: Classify workflow contracts at their real risk

## Problem

Executable Claude workflow contracts and the load-bearing architecture map classify below the risk
of changing them, while a duplicate workflow rule obscures the model's max-wins behaviour.

## Goal

Classify every `.claude/**` path as R3, `docs/architecture.md` as R2, and retain exactly one R3
workflow rule without lowering any tracked path.

## Non-goals

- No classifier logic, default class, gate list, task schema, or readiness behaviour changes.
- No live, monitoring, research, mutation-policy, or mutation-baseline file changes.
- No process-scaling change from issue #124.
- No workflow-contract rewrite from unmerged issue #107.

## Behavioural requirements

- The production classifier applies the highest matching class exactly as before.
- The `.claude/**` rule adds to the exact `.claude/settings.json` rule rather than replacing it.
- The tracked-tree comparison uses the real output of `git ls-files`.
- Removing the duplicate R2 workflow rule changes no tracked path's classification.
- The only permitted class increases are tracked `.claude/**` paths and `docs/architecture.md`.

## Acceptance criteria

- AC-01: `.claude/skills/specify-change/SKILL.md` and
  `.claude/agents/adversarial-code-reviewer.md` classify as R3.
- AC-02: `.claude/settings.json` still classifies as R3 and both its exact rule and the new catch-all
  rule exist.
- AC-03: `docs/architecture.md` classifies as R2.
- AC-04: `README.md` still classifies as R0.
- AC-05: `.github/workflows/ci.yml` still classifies as R3 and has no duplicate R2 rule.

## Invariants

- INV-01: Every existing path in the engineering-document R3 guard still classifies as R3.
- INV-02: No tracked path classifies lower than under the pre-change rules, and no path outside
  `.claude/**` plus `docs/architecture.md` is upgraded.
- INV-03: Adding the dead `.github/workflows/**` R2 rule back changes no tracked classification,
  proving max-wins was its only effect.
- INV-04: No trading, research, live, monitoring, mutation-policy, or mutation-baseline behaviour
  changes.

## Assumptions

- `git ls-files` is the authoritative tracked-tree inventory; the test fails if that inventory is
  empty or implausibly small.
- The pre-change model is reconstructed by reversing exactly the two added rules and the one removed
  rule, with structural assertions that those post-change rules exist.

## Open questions

None.

## Expected artifacts

- `.ai/quality/risk-classes.toml`
- `docs/engineering/risk-classes.md`
- `tests/test_quality_classify.py`
- A minimal local update to `tests/test_engineering_docs.py`
- `.ai/tasks/109/{spec,impact,test-plan,evidence,review}.md`
- One draft pull request linked to issue #109

## Risk class

R3. The production classifier assigns R3 once the risk-model file changes. This is also a semantic
R3 change because a mistake in the model can omit mandatory gates from a money-path change.

## Human decisions required

Jan approved issue #109, risk class R3, the exact scope, draft-only delivery, and Claude as the
independent reviewer. The branch uses current `origin/main@14f0cdb`; the hash `8b75ff0` named in the
request was no longer origin/main when implementation started.
