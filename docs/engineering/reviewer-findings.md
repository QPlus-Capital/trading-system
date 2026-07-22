# Reviewer-findings feedback loop

Every confirmed Codex or adversarial-review defect becomes permanent protection. The implementer
must reproduce it with a failing test, fix the root cause, keep the generalized regression test,
and add one entry to `.ai/quality/finding-patterns.toml` before readiness is reassessed.

The registry entry names the defect class, severity, affected boundary, root cause, why existing
tests missed it, the permanent regression, its generalized form, and the workflow change. It must
describe a reusable failure pattern rather than only the one line that failed.

After any material fix, rerun the full adversarial review against the complete branch. Resolve P0,
P1, and P2 findings before readiness; record P3 disposition without weakening a gate. A repeated
defect class is a workflow failure, not merely another code bug: strengthen the applicable skill,
hook, test matrix, quality check, or constitution rule in the same change or a separately linked
blocking issue. Every repeated defect class is therefore treated as a workflow failure.

The task artifact is the audit trail. `review.md` records findings and dispositions, `test-plan.md`
records the red/green proof, and `evidence.md` records the exact successful commands and HEAD.
