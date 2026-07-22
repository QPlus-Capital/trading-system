# Engineering session policy

Start a fresh session for every non-trivial issue. The task specification and repository artifacts,
not chat history, are the durable audit trail; restore context by reading the issue, constitution,
task artifact, current diff, and tests.

Claude uses an isolated subagent as its primary adversarial-review path, with a read-only review
remit and the complete behavioural contract. Codex is the primary builder. For the highest-stakes
trading exception, either agent may build, but the builder does not review its own decisions.
After any material fix, rerun the full adversarial review over the complete branch rather than only
the latest patch.

If context becomes confused, contradictory, or too large to trace confidently, stop. Persist the
current specification, impact, test, review, and evidence artifacts; record open questions; then
continue in a fresh session from those artifacts. Never guess through a safety, methodology,
architecture, business, trading, live-money, or risk decision because a session is degraded.
