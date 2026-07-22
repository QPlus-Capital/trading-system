# Adversarial review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| R-01 | P1 | `scripts/quality/hooks/decisions.py:20` allowed the exact dotted `live.run --mode execute` spelling because a word boundary preceded `--mode` | Correct the matcher and retain the exact unsafe command plus safe neighbours as parameterized tests; register F-018 | resolved |
| R-02 | P2 | `scripts/quality/hooks/decisions.py:42` treated the brace-delimited synthetic fixture variable in test source as a real named secret | Preserve the closing brace in value parsing, allow brace placeholders, and retain both fake-secret and clean-source tests; register F-019 | resolved |
| R-03 | P1 | `scripts/quality/hooks/pre_bash.py:168` represented an undiscoverable R3 task as no validation issues, allowing the review-artifact guard to fail open | Emit an explicit missing-review issue, test orchestration without a task, and register F-020 | resolved |
| R-04 | P2 | The initial runner/order patterns also blocked offline pytest and documentation-search commands containing ordinary words such as `runner`, `stop`, `place`, and `order` | Restrict matching to repository live entrypoints, service controls, and broker actions; retain benign near-neighbour tests | resolved |
| R-05 | P1 | Commit and push checks initially validated task files from the working tree, which could differ from the staged index or pushed HEAD | Materialize and validate the exact index/HEAD task snapshot through `validate_task_dir`; test the staged revisions used | resolved |
| R-06 | P2 | The dogfood commit hook re-flagged its synthetic fixture because the exact staged f-string had an escaped newline after the brace placeholder | Add the exact staged representation to the clean regression, accept only escaped whitespace suffixes after brace placeholders, and register F-021 | resolved |
| R-07 | P2 | Raw bypass matching treated the test's quoted `# type: ignore` counterexample as a real suppression and blocked the dogfood commit | Tokenize Python additions, inspect actual comments/code only, scope per-file ignores to TOML, and register F-022 | resolved |

## Dispositions

The review attempted 20 counterexamples: dotted and slash module spellings, signal-only live start,
service stop, explicit order placement, offline runner tests, documentation search, two force-push
forms, a synthetic fake secret, its committed source placeholder, direct main R0/R1, failed and
successful readiness, missing baseline evidence, broad and narrow suppressions, missing R3 task,
unresolved review, staged-versus-working-tree drift, quoted suppression fixtures, and documentation
examples. R-01 through R-07 are resolved with
executable guards. No live process, account, terminal, runner, order, or position was accessed.
