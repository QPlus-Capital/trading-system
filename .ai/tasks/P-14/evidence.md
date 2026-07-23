# Evidence

## HEAD

HEAD: f6229bacc7373d26026f3df3e70d8cccc8ad252e

## Commands

| Gate | Command | Exit status | Result |
|---|---|---:|---|
| `red-first` | `uv run pytest -q tests/test_live_mt5_bridge.py::test_history_deals_exports_ticket_and_fee tests/test_monitoring_deals.py::test_fee_moves_ledger_equity_and_trade_net_pnl tests/test_monitoring_risk_view.py::test_same_second_opening_cost_is_excluded_from_its_own_basis tests/test_monitoring_dashboard.py::test_load_live_retries_an_interleaved_deal_snapshot tests/test_monitoring_dashboard.py::test_load_live_fails_closed_when_history_never_stabilises` | 1 | RED: all five guards failed independently on missing export, fee accounting, opening basis, mixed snapshot, and fail-closed retry |
| `red-first` | Linux Critical mutation workflow run `29990552934` before the ratchet update | 1 | RED: the old 774-mutant baseline rejected the expanded 1,237-mutant scope |
| `red-first` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-fast origin/main` before formatting | 1 | RED: the format guard named eight touched files |
| `red-first` | `uv run python -m scripts.quality.validate_task --task-id P-14 --base origin/main` before completing the test map | 1 | RED: AC-05, INV-03, and INV-04 were unmapped |
| `format` | `uv run python -m scripts.quality.impact --base origin/main --check-format` | 0 | GREEN: every changed Python file is formatted; unrelated baseline files remain out of scope |
| `docs-consistency` | `uv run pytest -q tests/test_docs_architecture_map.py tests/test_docs_language.py tests/test_engineering_docs.py tests/test_engineering_workflow_docs.py` | 0 | GREEN: 124 documentation and governance guards passed |
| `check` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check` | 0 | GREEN: Ruff, mypy over 151 files, vulture, and 742 pytest tests passed; one Linux-only mutation self-test skipped on Windows |
| `impacted-tests` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-fast origin/main` | 0 | GREEN: R3 impact selection ran 123 direct/transitive tests after format, lint, and types |
| `property-tests-where-applicable` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-properties` | 0 | GREEN: nine deterministic properties passed twice with seed 20260721 |
| `integration-tests` | full `uv run pytest -q` inside `just check` | 0 | GREEN: 742 passed, including the fake-bridge `_load_live` path; no live terminal interaction |
| `artifact-schema` | `uv run python -m scripts.quality.validate_task --task-id P-14 --base origin/main` | 0 | GREEN: five acceptance criteria and five invariants validate |
| `adversarial-review` | `.ai/tasks/P-14/review.md` and artifact validation | 0 | GREEN: twelve counterexamples attempted; three findings resolved; no P0-P2 remains open |
| `invariants` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-invariants` | 0 | GREEN: 129 live-risk, parity, sizing, research-integrity, and workflow invariants passed |
| `mutation-on-touched-critical` | Linux Critical mutation workflow run `29991539702` | 0 | GREEN: self-test and ratchet passed; 967/1,237 killed, 270 reviewed survivors, zero unhealthy outcomes |
| `parity-where-applicable` | `uv run pytest -q tests/test_live_parity_check.py tests/test_live_runner_cycle.py` plus scope diff | 0 | GREEN: shared-signal parity and runner-cycle behavior pass; no signal, runner, sizing, or order method changed |
| `live-money-review` | focused diff review of `live/mt5_bridge.py`, `live/runner.py`, `live/risk_control.py`, and `live/accounts.py` | 0 | GREEN: only read-only `history_deals` export changed; no trade placement, sizing, limit, guard, or runner path changed |
| `human-decision-escalation` | issue #41 pinned build contract and `.ai/tasks/P-14/spec.md` | 0 | GREEN: unresolved broker fee usage is recorded as an operator observation; Jan retains live-money and merge authority |
| `no-autonomous-merge` | feature-branch/PR workflow audit | 0 | GREEN: no merge or auto-merge action exists; the ready PR is handed to Claude and Jan |
| `security` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile check-security` | 0 | GREEN: tracked-secret scan, dependency audit, and static security passed |
| `pr-ready` | `uvx --from rust-just just --shell powershell.exe --shell-arg -NoProfile pr-ready P-14 origin/main` | 0 | GREEN: task, risk, traceability, review, current evidence, and all required R3 gates pass |

## Coverage and mutation

The three production defects each have failing-first behavioral coverage, snapshot field identity is
parameterized across all exported fields, and ticket-order balance reconstruction has a
deterministic Hypothesis property. Linux run `29991539702` proves the mutation self-test and the
expanded critical ratchet on the formatted implementation: 967/1,237 mutants killed (78.2% versus
the preceding 75.6%), 270 conservatively classified survivors, and no no-test, skipped, suspicious,
timeout, unchecked, interrupted, segfault, or type-check-only outcome.

## Deferred checks

Claude's independent review and Jan's merge decision occur on the ready pull request. Whether the
deployed broker emits non-zero `fee` values is an operator observation, not a correctness blocker;
synthetic fee-only fixtures exercise the complete path.
