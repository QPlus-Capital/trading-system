# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | `tests/test_quality_validate_task.py` | RED: validator module absent at collection | GREEN: clean and rejection cases pass |
| AC-02 | `tests/test_quality_impact.py` | RED: impact module absent; tracked JSON churned | GREEN: dependencies pass; local JSON is ignored |
| AC-03 | readiness and validator tests | RED: failed gates and empty R3 review passed | GREEN: missing/failed gates and empty review block; clean R3 passes |
| AC-04 | classifier plus full gate commands | BASELINE: quality glob already requires R3 | GREEN: R3 reported; 606 tests and all static gates pass |
| INV-01 | `test_declared_risk_may_not_understate_the_classifier` and source review | RED: composed guard absent | GREEN: classifier result is reused and cannot be understated |
| INV-02 | `test_report_never_claims_complete_coverage` | RED: impact report absent | GREEN: report explicitly disclaims completeness |
| INV-03 | `git diff origin/main -- justfile` review | BASELINE: existing recipe captured | GREEN: only new recipes follow the unchanged `check` recipe |
| INV-04 | `validate_task 64` and artifact review | RED: issue artifact absent | GREEN: four ACs and four INVs validate without transcripts |
