# Adversarial review

## Findings

| ID | Severity | Finding | Disposition | Status |
|---|---|---|---|---|
| R-01 | P1 | A declared manual R3 upgrade enforced only the lower path-classifier gates | Effective risk is now max(classified, declared); regression and F-026 added | resolved |
| R-02 | P1 | The locked GitPython 3.1.50 had three published vulnerabilities | Lock upgraded to 3.1.54; dependency audit and F-027 added | resolved |
| R-03 | P1 | Plain Markdown issue templates lacked GitHub-required chooser metadata | Required frontmatter test and F-028 added | resolved |
| R-04 | P1 | An unchecked live-runner attestation could satisfy PR-body validation | Checked checklist enforcement, regression, and F-029 added | resolved |
| R-05 | P1 | A linked issue number was not reconciled with the numeric task artifact | Identity reconciliation, regression, and F-030 added | resolved |
| R-06 | P2 | Auto-discovery validated task 67 but reported `Task None` | Resolved identity output, CLI regression, and F-031 added | resolved |

## Dispositions

Thirty-four counterexamples were attempted across risk upgrades/downgrades, missing/failed/stale
evidence, blank and unchecked PR claims, mismatched task artifacts, workflow path filtering,
unpinned actions, hidden CI commands, secret disclosure, scanner errors, dependency advisories,
unmocked MT5 calls, template platform metadata, and push/edited-PR triggers. R-01 through R-06 were
fixed and rerun against the complete focused suite. No P2/P3 findings remain, and no live runner,
terminal, account, research result, or trading module was touched.
