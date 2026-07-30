# Adversarial review

## Findings

Independent review completed by Claude in a fresh session on 2026-07-30 against code head
`62dbc23`, delivered as a pull-request review on
[#133](https://github.com/QPlus-Capital/trading-system/pull/133#pullrequestreview-4812996451).

No findings; 9 counterexamples attempted.

This record is written by the reviewer, not transcribed by the builder. A verdict copied by the
author of the work under review is self-certification with an extra step; see the issue that removes
the transcription entirely.

## Counterexamples attempted

1. **Line-level diff of all 58 finding-pattern files.** Exactly one changed line each, `severity`.
   `P1`×32 → `Defect`, `P2`×24 → `Suspected defect`, `P3`×2 → `Note`. No other field in any pattern
   moved. Checked against `origin/main` rather than trusting the branch's own migration test.
2. **Every legacy id after the hash change.** The severity feeds the content hash that derives the
   id, so the rename could have orphaned every numeric reference. All 55 ids `F-001`–`F-055` resolve,
   plus the 3 derived ones; `legacy-manifest.toml` was recomputed rather than left stale.
3. **The blocking severity set.** `validate_task._CRITICAL` is `{blocker, defect, suspected defect}`
   — the first three block, `Note` does not, so INV-01 is preserved under the new names.
4. **Repository-wide search for residual `"P0"`–`"P3"`** as a severity across `.claude`,
   `.ai/quality`, `docs`, `CLAUDE.md`, `AGENTS.md` and `.github`: none.
5. **The selection matrix, executed** over seven class-and-path combinations: R0 and R1 select none;
   R2 selects code and test; R3 on `live/**` adds live-money; R3 on `research/**` adds methodology;
   R3 on both selects all four; and R3 touching neither specialist path still selects only code and
   test. The last case is what makes it a matrix rather than a slope.
6. **Tool declarations of all four agents.** Each declares `Read, Grep, Glob, Bash` with no write
   surface, so INV-02 holds across the set and not only for the new agent.
7. **Skill count and names.** Exactly five: `build-change`, `create-issue`, `resolve-findings`,
   `review-change`, `specify-change`.
8. **The five constitution §4 invariants** named explicitly in `methodology-reviewer.md`: leakage,
   holdout, `net_r`, lineage, equal-footing sizing.
9. **The empty activation register.** This branch removes two of the three remaining rows and #110
   removes the third, so the pair produces a state none of the loader, renderer or digest had seen. I
   reproduced the failure it prevents by stripping every row on the #110 tree, where the loader still
   raises `activation must be a non-empty TOML table array`. This branch introduces `_optional_tables`
   precisely for that case, and `_render_activations` degrades to a valid header-only table. Because
   #110 does not modify `workflow_contract.py` it inherits the tolerance either way, so both merge
   orders are safe.

## Dispositions

No finding required a disposition. The full suite passed locally at **1615 passed, 1 skipped**.

One deferred check remains, recorded rather than resolved: no CI run has yet executed against an
empty activation register, because neither branch reaches that state alone. Merging #110 first makes
this branch's own CI the first run against a genuinely empty register — before `main` rather than
after — which is the recommended order.
