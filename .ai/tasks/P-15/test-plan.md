# Test plan

| Requirement | Test | Before | After |
|---|---|---|---|
| AC-01 | Render indeterminate open risk and inspect metric/error calls | RED expected: English copy | German label, value, help, and error |
| AC-02 | Render incomplete and hidden history scenarios | RED expected: English captions | German captions retain values |
| AC-03 | Audit every scoped literal and the syntax-aware language exception | RED: legacy guard rejects German dashboard output | Scoped UI passes; comments and logs remain rejected |
| AC-04 | Focused dashboard rendering guard | RED expected before production edit | GREEN after literal-only edit |
| AC-05 | Classifier, impact, focused/full tests, task validation, review | Pending | Every R2 gate exits 0 |
| INV-01, INV-03 | Production/forbidden-path diff audit | No production edit yet | Only scoped dashboard literals differ |
| INV-02 | Log-call and source-language audit | English logs | English logs unchanged |
| INV-04 | MT5 boundary plus fake dashboard inputs | No test yet | No terminal or runner interaction |
