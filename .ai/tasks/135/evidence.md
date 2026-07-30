# Evidence

## HEAD

HEAD: 6b711c671a756ad7a939402bb0952eb0af0d9bce

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_engineering_workflow_docs.py::test_branch_protection_names_every_required_check_and_setting` against the unchanged page | 1 | The assertion received the seven retired contexts instead of the four active contexts. |
| `focused` | `uv run pytest -q tests/test_engineering_workflow_docs.py::test_branch_protection_names_every_required_check_and_setting` | 0 | The corrected page names the exact four workflow jobs and all applied parameters and reasons. |

## Coverage and mutation

The behavioral guard parses the two workflow files and compares their job keys with the four
contexts documented on the page. It also checks the applied date, ruleset name, pull-request
parameters, deliberate zero-approval and non-strict-check reasons, and removal of the future-action
sentence. No production or mutation target changed; mutation evidence is therefore limited to the
unchanged R3 ratchet required by the gate set.

## Deferred checks

- Independent Claude review is pending.
- Full R3 gates and final evidence freshness are pending.
- Linux parity has not been observed for this branch and is not claimed green while the pull
  request remains draft.
