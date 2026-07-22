# Adversarial review

## Findings

No findings; 7 counterexamples attempted

## Dispositions

The completed implementation was challenged with an accidental Monte Carlo consumer, a hidden
block-length clamp, an unseeded global RNG, one scalar restart shared by every replication,
near-cancelling plug-in moments, equality at the `T/10` boundary, and implicit NumPy dtype changes.
Focused regressions cover the executable counterexamples. The remaining mutation survivors are
exact-name ratcheted and classified; no unexplained survivor remains. This builder review does not
replace Claude's independent review of the pull request.
