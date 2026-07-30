# Reviewer-findings feedback loop

Every confirmed Claude or read-only `review-change` defect becomes permanent protection. The builder
must reproduce it with a failing test, fix the root cause, keep the generalized regression test,
and add one content-addressed file under `.ai/quality/finding-patterns/` before readiness is
reassessed. The registry loader derives its ID; the builder never chooses a numeric ID.

The registry entry names the defect class, severity, affected boundary, root cause, why existing
tests missed it, the permanent regression, its generalized form, and the workflow change. It must
describe a reusable failure pattern rather than only the one line that failed.

After any material fix, rerun the full adversarial review against the complete branch. Resolve
Blocker, Defect, and Suspected defect findings before readiness; record each Note disposition
without weakening a gate. A repeated defect class is a workflow failure, not merely another code
bug: strengthen the applicable skill, hook, test matrix, quality check, or constitution rule in the
same change or a separately linked blocking issue. Every repeated defect class is therefore
treated as a workflow failure.

The task artifact is the audit trail. The independent reviewer writes findings and dispositions in
`review.md`; the builder never transcribes them. `test-plan.md` records the red/green proof, and
`evidence.md` records the exact successful commands and HEAD. Readiness observes the submitted
pull-request review rather than parsing the audit record.
