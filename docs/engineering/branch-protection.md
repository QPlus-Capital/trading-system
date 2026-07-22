# Branch protection for `main`

Jan applies these settings in GitHub after this workflow lands. Repository code cannot enforce
GitHub's server-side rules, so this page is the exact configuration checklist and audit reference.

## Ruleset target

- Create one active branch ruleset named `Protect main`; target the default branch `main`.
- Set enforcement to `Active`, with no bypass actors (including repository administrators).
- Enable **Restrict deletions**, **Block force pushes**, and **Require linear history**.
- Enable **Require a pull request before merging** with one required approval, dismissal of stale
  approvals after new commits, approval of the most recent reviewable push, and no allowed bypass.
- Enable **Require conversation resolution before merging**.
- Enable required status checks and require branches to be up to date before merging.

## Required status checks

Select these exact contexts after one pull request has produced them:

- `CI / standard-quality`
- `CI / tests`
- `CI / task-artifact-validation`
- `CI / security`
- `CI / critical-invariants`
- `CI / pr-evidence-validation`
- `Critical mutation / mutation-critical`

Do not mark a path-filtered or aggregate substitute as required. Each context maps to a local
`just` recipe, and the workflows have no path filter that can omit an R3 change.

## Review and merge policy

- Direct pushes to `main` are prohibited by the pull-request rule; Jan merges only after every
  required check is successful and every conversation is resolved.
- Claude performs the independent review after the Codex implementation and read-only adversarial-
  review artifact are complete. Its findings are resolved or dispositioned before approval.
- R3 has no autonomous merge: Jan decides every business, trading, methodology, live-money,
  architecture, risk, scope, go-live, and merge question. Auto-merge is not
  used for R3 even when all technical checks are green.
- Jan approves every merge; CI, Claude, Codex, and hooks never merge.

Audit this ruleset after workflow/job renames and quarterly. A renamed required check must be
updated here and in GitHub in the same rollout window so protection never silently disappears.
