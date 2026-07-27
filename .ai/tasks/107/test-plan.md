# Test plan

This change adds and amends governance documents. It fixes no defect, so there is no red-first guard
to record: nothing was observably wrong before. The protection is that the existing documentation
consistency tests continue to bind after the rewrite — they are what would catch a load-bearing rule
being dropped or a role marker being lost while the documents were restructured.

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | manual: `docs/engineering/workflow.md` reviewed phase by phase against the six phases | N/A: new document, no prior state | GREEN: each phase names actor, place and resulting status |
| AC-02 | manual: constitution §9 reviewed | N/A: rule did not exist | GREEN: §9 states the class scales gates, artifacts, PR sections and review agents |
| AC-03 | manual: constitution §16 reviewed | N/A: rule did not exist | GREEN: §16 states `codex/<issue>-<slug>`, one worktree per issue, squash on merge |
| AC-04 | manual: `AGENTS.md` reviewed | N/A: rule did not exist | GREEN: step 0 refuses without status, permit and class; card moves before the permit is removed |
| AC-05 | manual: `CLAUDE.md` reviewed | N/A: rule did not exist | GREEN: approval section states the order and that `arm:implement` is written last |
| AC-06 | `tests/test_engineering_docs.py`, `tests/test_engineering_workflow_docs.py`, `tests/test_docs_language.py`, `tests/test_docs_architecture_map.py`, `tests/test_claude_runtime_files.py` | GREEN before the change | GREEN after: 139 passed |
| INV-01 | `tests/test_engineering_docs.py::test_load_bearing_rule_is_stated`, `::test_role_contracts_preserve_exception_and_human_authority`, `::test_direct_to_main_exception_is_R0_only_everywhere` | GREEN before the change | GREEN after: every load-bearing phrase still present in every document that must state it |
| INV-02 | manual: `workflow.md` cross-checked against the constitution for contradiction; the file states the constitution wins | N/A: new document | GREEN: no contradiction found; precedence stated in the opening paragraph |

The manual rows are honest about what they are. A test that asserts a document contains a sentence
would restate the implementation rather than protect a behaviour; the consistency tests already
guard the load-bearing phrases, which is the property that actually matters here.
