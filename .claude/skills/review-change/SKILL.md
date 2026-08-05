---
name: review-change
description: Invoke as Claude's primary review path for a completed pull request.
---

This is Claude's primary review skill. It runs in a fresh session, is read-only and independent of
the builder, and delivers its result as a pull-request review. The orchestrator starts it with the
issue number; the branch and its pull request follow from that. **Lean is the default**: one pass by
Claude directly, no subagents. The full panel engages only when `[review.scope]` of
`workflow/workflow.toml` says so — a carve-out path, a diff over the size bound, or the operator's
ask — and the *actual* diff decides, whatever the issue declared.

## Required inputs

- The issue number, its contract, the effective risk class, the final diff and touched paths, the
  gate results, and the relevant source and tests.

## Procedure

1. In a fresh session, decide the lane from `[review.scope]` and the actual diff, then read the
   agent selection from the `[review]` table of `workflow/workflow.toml` for the effective risk
   class and touched paths. Do not select agents from prose or memory. In the lean lane no
   subagents run — review directly, one pass.
2. In the full program, invoke each selected read-only subagent with the issue contract, the diff,
   the gate results, and the executing paths. Never pass the builder's private context.
3. **Search effort is proportionate to the diff.** Target the behaviours whose failure costs the
   most; stop when further counterexamples stop changing the verdict. Never a fixed quota per
   changed behaviour.
4. Reconcile findings against every criterion the issue states.
5. **On a repeat round, review only the fix diff and the modules it touches** — a complete fresh
   review only when the fix reaches outside the original diff, or at R3 on the live path. Report
   only the findings table and the verdict; no fresh contract check, no counterexample appendix.
6. Run the commands your conclusions rest on. Invoke them worktree-safe — `uv run --directory
   <worktree> pytest …`, `git -C <worktree> …` — a compound command starting with `cd` falls
   outside the headless allowlist and is refused.
7. Submit one pull-request review: an inline `file:line` comment per finding, and a summary with
   the findings table, the contract check (first round only), and the decisions that belong to
   the operator, **each wrapped in `<!-- workflow-decision -->` … `<!-- /workflow-decision -->`**
   so the cycle can forward it to the operator's ticket chat and onto the issue. End the summary
   with `<!-- workflow-verdict sha:<the reviewed head> blocking:N advisory:M evidence:executed -->`.
   The sha names the commit this review read; a marker that names any other commit is no verdict
   at all, which is what keeps a later push from inheriting an earlier round's result. Evidence
   is `executed` only when you actually ran the decisive commands; if every command was refused,
   write `evidence:static` and say so in the summary — a clean static verdict is presented to
   the operator, never auto-certified.
8. Use `Blocker`, `Defect`, `Suspected defect`, or `Note`. Only the first two block and trigger a
   fix round; the other two are collected for the operator.
9. If no finding survives, record the number of counterexamples attempted.

## Outputs

- A read-only, fresh-context pull-request review that names its severities and carries the verdict
  marker.
- **The chat output ends with a summary in German**, written to the three rules in section 7 of
  `workflow/workflow.md`: two to five plain sentences weighted for this phase — what was found and
  what it means for the merge; a decision set off visibly with its question, options,
  recommendation and default, and its command on its own line; no heading over an empty section.

## Stop conditions

- Stop when inputs or gate results are stale, or when a selected agent did not run.
- Stop and escalate to the operator when a finding needs a decision only the operator can make.

## Prohibited shortcuts

- Do not edit files, commit, push, change pull-request state, merge, or interact with live trading.
- Do not review your own implementation. You never build.
- Do not invent findings, and do not accept narrative reassurance instead of executable evidence.
- Do not open follow-up issues; non-blocking observations go to the operator, who decides what
  becomes a ticket.
