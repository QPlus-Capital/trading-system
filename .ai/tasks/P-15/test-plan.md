# Test plan

| Requirement | Test | Before | After |
|---|---|---|---|
| AC-01 | Render both open-risk branches and inspect metric/error calls | RED: English label caused `StopIteration` | German label, values, help, and error pass |
| AC-02 | Render incomplete and hidden history scenarios | RED: English captions | German captions retain 200/100/3 values |
| AC-03 | Audit every scoped literal and the syntax-aware language exception | RED: legacy guard rejected German dashboard output | Scoped UI passes; comments and logs remain rejected |
| AC-04 | Focused dashboard rendering guard | RED: 1 failed | GREEN: focused guard passes |
| AC-05 | Classifier, impact, focused/full tests, task validation, review | R2 expected | R2 and all cumulative gates pass |
| INV-01, INV-03 | Normalized-AST and forbidden-path diff audits | Dashboard English | AST structure identical; forbidden paths clean |
| INV-02 | Language-guard synthetic comment/log counterexamples | Legacy blanket scan | English source/log protection remains active |
| INV-04 | MT5 boundary plus import bridge and fake dashboard inputs | No rendering guard | No terminal or runner interaction |
