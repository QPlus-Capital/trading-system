# Test plan

| Requirement | Test | Before-fix result | After-fix result |
|---|---|---|---|
| AC-01 | AR(1) fixed reference and white-noise estimator tests | RED: module missing; stubs failed | GREEN: hard-coded 5.085266752079944 reference and near-one selection pass |
| AC-02 | selector ceiling/minimum/common-grid/diagnostic tests | RED: module missing; stubs failed | GREEN: ceiling/minimum/grid and exact L/T/candidate rejection pass |
| AC-03 | geometric run-length and invalid-input tests | RED: module missing; stubs failed | GREEN: 2% geometric-mean tolerance and invalid cases pass |
| AC-04 | circular wrap, marginal weights, shape, determinism tests | RED: module missing; stubs failed | GREEN: circular/uniform/bitwise/shape checks pass |
| AC-05 | sensitivity keys and signature-default tests | RED: module missing; stubs failed | GREEN: exact 5/10/20/60 and 10,000/20260719 defaults pass |
| AC-06 | 1,000-experiment seeded IID calibration | RED: module missing; stub failed | GREEN: nominal coverage is within 95% +/- 1.5% |
| AC-07 | 1,000-experiment seeded AR(1) calibration plus local IID negative control | RED: module missing; stub failed | GREEN: stationary coverage is within 95% +/- 2%; IID under-covers |
| AC-08 | architecture map, mutation fast/critical, and cumulative R3 gates | RED: module/target absent | GREEN: local R3 gates and Linux critical mutation ratchet pass |
| INV-01, INV-02 | import/diff audit and caller-array immutability | RED: utility absent | GREEN: no consumer/import and no caller mutation; forbidden paths unchanged |
| INV-03 | seeded examples and Hypothesis deterministic properties | RED: stubs failed both properties | GREEN: deterministic properties pass twice with fixed seed |
| INV-04 | exhaustive invalid/boundary parametrization | RED: stubs failed all cases | GREEN: empty/shape/finite/grid/L/replication cases pass |
| INV-05 | Linux mutation results for estimator and resampler patterns | RED: target absent, then 56 unexplained survivors | GREEN: 842/1,049 killed; 18 new reviewed survivors are exact-name ratcheted |
