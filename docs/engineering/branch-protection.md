# Branch protection for `main`

These settings were applied on 2026-07-30. Repository code cannot enforce GitHub's server-side
rules, so this page records the active configuration and remains its audit reference.

## Ruleset target

- Use one active branch ruleset named `main`; target the default branch `main`.
- Set enforcement to `Active`, with no bypass actors (including repository administrators).
- Enable **Restrict deletions** and **Block force pushes**.
- Do not enable **Require linear history**. The pull-request rule permits squash-only merging, which
  produces linear history without a separate ruleset rule.
- Enable **Require a pull request before merging** with zero required approvals. GitHub does not
  allow an account to approve its own pull request, and both review agents push through the same
  account, so a required approval would make every pull request impossible to merge.
- Do not dismiss stale approvals after new commits, do not require approval of the most recent
  reviewable push, and do not require a code-owner review.
- Enable **Require conversation resolution before merging**.
- Enable required status checks, but do not require branches to be up to date before merging.
  Non-strict checks avoid forcing every other open branch to rebase and re-run after one pull
  request merges.

## Required status checks

Require these exact contexts, without a workflow-name prefix:

- `platform-quality`
- `full-quality`
- `critical-change-filter`
- `mutation-critical`

The first two contexts are jobs in `.github/workflows/ci.yml`; the latter two are jobs in
`.github/workflows/mutation.yml`. The mutation filter always reports, while the expensive mutation
job runs only when its workflow condition selects it. The workflows have no trigger-level path
filter that can omit an R3 change.

## Review and merge policy

- Direct pushes to `main` are prohibited by the pull-request rule; Jan merges only after every
  required check is successful and every conversation is resolved.
- Claude performs the independent review after the Codex implementation and read-only adversarial-
  review artifact are complete. Its findings are resolved or dispositioned before approval.
- R3 has no autonomous merge: Jan decides every business, trading, methodology, live-money,
  architecture, risk, scope, go-live, and merge question. Auto-merge is not
  used for R3 even when all technical checks are green.
- Jan authorizes every merge; the zero-review setting reflects the single-account limitation, not
  a transfer of merge authority. CI, Claude, Codex, and hooks never merge.

Audit this ruleset after workflow/job renames and quarterly. A renamed required check must be
updated here and in GitHub in the same rollout window so protection never silently disappears.
