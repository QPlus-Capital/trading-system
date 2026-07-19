"""#31: a stage may only build on artifacts it can prove were produced by the run it is in.

The failure this prevents actually happened: a run reported one variation's gate evidence beside
another variation's numbers, because Stage 2 had been re-run after Stage 3 read it. Every file
existed, every stage "succeeded", and the result was meaningless.

These tests drive the REAL stage entrypoints wherever the stage is cheap enough to complete
(Stage 1 ingesting a study, Stage 2), and for the heavy stages assert that the entrypoint refuses
before it starts computing -- which is the property that matters, since a refusal that arrives
after an hour of backtests is not a gate anyone will keep.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest
from core.data.mt5_csv import SOURCE_MARKER
from core.paths import REPO_ROOT
from research.stages import _runbook as rb
from research.stages import edge, lineage, portfolio, select, verdict

_CONFIG_SRC = '''
from dataclasses import dataclass


@dataclass
class _Inst:
    raw_symbol: str


def _eurusd() -> _Inst:
    return _Inst("EURUSD")


def _gbpusd() -> _Inst:
    return _Inst("GBPUSD")


INSTRUMENTS = [(_eurusd, "data/eurusd.csv", 1), (_gbpusd, "data/gbpusd.csv", 1)]
VARIATIONS = {"v_alpha": {}, "v_beta": {}}
PARAM_GRID: dict[str, list[float]] = {}
'''


def _write_config(path: Path, marker: str = "original") -> Path:
    path.write_text(f"{_CONFIG_SRC}\nMARKER = {marker!r}\n", encoding="utf-8")
    return path


def _write_study(study_dir: Path) -> Path:
    """A tiny study table: two variations x two training lengths x two instruments, all complete."""
    study_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for variation, ret in (("v_alpha", 30.0), ("v_beta", 20.0)):
        for train in (24, 36):
            for instrument in ("EURUSD", "GBPUSD"):
                rows.append(
                    {
                        "variation": variation,
                        "train_months": train,
                        "instrument": instrument,
                        "mean_oos_pct": ret + (2.0 if train == 36 else 0.0),
                        "return_per_dd": 3.0 if variation == "v_alpha" else 2.8,
                        "pct_profitable": 70.0,
                    }
                )
    pd.DataFrame(rows).to_csv(study_dir / "study.csv", index=False)
    pd.DataFrame({"variation": ["v_alpha", "v_beta"], "dsr": [1.5, 1.2]}).to_csv(
        study_dir / "ranking.csv", index=False
    )
    (study_dir / "overfitting.json").write_text('{"pbo": 0.05, "n_trials": 4}', encoding="utf-8")
    return study_dir


@pytest.fixture
def study(tmp_path: Path) -> tuple[Path, Path, Path]:
    """``(config, study_dir, run_dir)`` -- the inputs of a fresh framework run."""
    cfg = _write_config(tmp_path / "study_cfg.py")
    study_dir = _write_study(tmp_path / "study_src")
    run_dir = tmp_path / "run_test"
    run_dir.mkdir()
    return cfg, study_dir, run_dir


def _run_edge(study: tuple[Path, Path, Path]) -> None:
    cfg, study_dir, run_dir = study
    edge.main([str(cfg), "--from", str(study_dir), "--run", str(run_dir)])


# ------------------------------------------------------------------ the happy path
def test_a_clean_run_completes_stage_1_and_2(study: tuple[Path, Path, Path]) -> None:
    _cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])

    assert (run_dir / "selection.json").is_file()
    for stage in ("edge", "select"):
        m = lineage.read_manifest(run_dir, stage)
        assert m is not None, f"stage '{stage}' left no completion marker"
        assert m.verify_outputs(run_dir) == []
        assert m.verify_inputs() == []
    # Both stages belong to ONE run -- a shared run id is what makes "same run" checkable.
    assert lineage.read_manifest(run_dir, "edge").run_id == (  # type: ignore[union-attr]
        lineage.read_manifest(run_dir, "select").run_id  # type: ignore[union-attr]
    )
    # Stage 2 recorded the hash Stage 1's study.csv had when it READ it.
    sel = lineage.read_manifest(run_dir, "select")
    assert sel is not None
    assert sel.upstream["study.csv"] == lineage.sha256_file(run_dir / "study.csv")


# ------------------------------------------------------------------ tampering with artifacts
def test_altering_study_csv_stops_stage_2_and_names_both_hashes(
    study: tuple[Path, Path, Path],
) -> None:
    _cfg, _src, run_dir = study
    _run_edge(study)

    df = pd.read_csv(run_dir / "study.csv")
    df.loc[0, "mean_oos_pct"] = 999.0  # the edit that used to travel silently downstream
    df.to_csv(run_dir / "study.csv", index=False)

    with pytest.raises(SystemExit) as err:
        select.main(["--run", str(run_dir)])
    msg = str(err.value)
    assert "study.csv" in msg
    assert "recorded" in msg and "actual" in msg  # both hashes named, so the operator can see it


def test_altering_the_config_contents_stops_the_next_stage(
    study: tuple[Path, Path, Path],
) -> None:
    """Same path, different content -- the case no output hash can catch."""
    cfg, _src, run_dir = study
    _run_edge(study)
    _write_config(cfg, marker="edited-after-the-study-ran")

    with pytest.raises(SystemExit) as err:
        select.main(["--run", str(run_dir)])
    msg = str(err.value)
    assert "inputs of stage 'edge' changed" in msg
    assert "study_config" in msg


def test_replacing_selection_json_stops_stage_4(study: tuple[Path, Path, Path]) -> None:
    _cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)

    sel = json.loads((run_dir / "selection.json").read_text(encoding="utf-8"))
    sel["variation"] = "v_beta"  # a different structure than the portfolio was built for
    (run_dir / "selection.json").write_text(json.dumps(sel, indent=2), encoding="utf-8")

    with pytest.raises(SystemExit) as err:
        verdict.main(["--run", str(run_dir)])
    assert "selection.json" in str(err.value)


def test_portfolio_json_from_another_run_stops_stage_4(
    study: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Spec from one evaluation, trades from another -- each file intact, the pair meaningless."""
    _cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)

    other = json.loads((run_dir / "portfolio.json").read_text(encoding="utf-8"))
    other["variation"] = "v_beta"
    (run_dir / "portfolio.json").write_text(json.dumps(other, indent=2), encoding="utf-8")

    with pytest.raises(SystemExit) as err:
        verdict.main(["--run", str(run_dir)])
    assert "portfolio.json" in str(err.value)


def test_stage_3_refuses_a_tampered_upstream_before_doing_any_work(
    study: tuple[Path, Path, Path],
) -> None:
    """The refusal must land immediately -- Stage 3's real work is hours of backtests."""
    cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _write_config(cfg, marker="edited")

    with pytest.raises(SystemExit) as err:
        portfolio.main(["--run", str(run_dir), "--risk", "flat:0.15"])
    assert "changed" in str(err.value)
    assert not (run_dir / "portfolio_trades.csv").exists()  # nothing was computed


# ------------------------------------------------------------------ atomicity & invalidation
def test_a_stage_that_raises_publishes_nothing(tmp_path: Path) -> None:
    run = rb.RunDir.open(tmp_path)
    with pytest.raises(RuntimeError), run.stage("edge", argv={}) as st:
        st.save_json("run_manifest.json", {"config": "x"})
        raise RuntimeError("died after the first output")

    assert not (tmp_path / "run_manifest.json").exists()
    assert lineage.read_manifest(tmp_path, "edge") is None  # no completion marker -> invisible
    assert not list(tmp_path.glob(".staging_*"))  # and no debris left behind


def test_rerunning_stage_2_invalidates_stage_3_and_4(study: tuple[Path, Path, Path]) -> None:
    _cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)
    _fake_verdict_stage(run_dir)
    assert lineage.read_manifest(run_dir, "portfolio") is not None

    select.main(["--run", str(run_dir)])  # the exact sequence that corrupted the real run

    assert lineage.read_manifest(run_dir, "select") is not None
    assert lineage.read_manifest(run_dir, "portfolio") is None
    assert lineage.read_manifest(run_dir, "verdict") is None
    # The stale FILES may still sit there; what matters is that nothing will accept them again.
    with pytest.raises(SystemExit):
        verdict.main(["--run", str(run_dir)])


# ------------------------------------------------------------------ legacy runs
def test_a_legacy_run_needs_the_flag_and_is_never_deployable(tmp_path: Path) -> None:
    (tmp_path / "study.csv").write_text("variation\nv_alpha\n", encoding="utf-8")
    (tmp_path / "selection.json").write_text('{"variation": "v_alpha"}', encoding="utf-8")

    strict = rb.RunDir.open(tmp_path)
    with pytest.raises(SystemExit) as err:
        strict.require("study.csv", "edge")
    assert "legacy" in str(err.value).lower()

    legacy = rb.RunDir.open(tmp_path, allow_legacy=True)
    assert legacy.require("study.csv", "edge").is_file()  # readable for inspection...
    with pytest.raises(SystemExit):
        legacy.assert_deployable()  # ...but never blessed


# --------------------------------------------------------- Codex round 1 on PR #38
def test_a_stage_bundle_copied_from_another_run_is_rejected(
    study: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """Each artifact intact, each manifest self-consistent -- but from two different runs.

    Verifying a stage against ITSELF cannot catch this: the copied bundle's outputs match its own
    manifest perfectly. Only the run id and the recorded upstream hashes tie the stages together.
    """
    _cfg, _src, run_a = study
    _run_edge(study)
    select.main(["--run", str(run_a)])

    cfg_b = _write_config(tmp_path / "cfg_b.py", marker="run-b")
    src_b = _write_study(tmp_path / "study_b")
    run_b = tmp_path / "run_b"
    run_b.mkdir()
    edge.main([str(cfg_b), "--from", str(src_b), "--run", str(run_b)])
    select.main(["--run", str(run_b)])

    # Lift B's whole select bundle -- manifest AND output -- into A.
    for name in ("selection.json", "_stage_select.json"):
        shutil.copyfile(run_b / name, run_a / name)

    run = rb.RunDir.open(run_a)
    with pytest.raises(SystemExit) as err:
        run.require("selection.json", "select")
    assert "run" in str(err.value).lower()


def test_an_upstream_artifact_swapped_after_the_stage_read_it_is_rejected(
    study: tuple[Path, Path, Path],
) -> None:
    """Stage 3 recorded the selection hash it READ; that record must be enforced, not just kept."""
    _cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)

    # Re-publish select with different content, then put stage 3 back exactly as it was -- marker
    # AND quarantined outputs -- so the directory looks untouched to anything but the hashes.
    marker = (run_dir / "_stage_portfolio.json").read_text(encoding="utf-8")
    select.main(["--run", str(run_dir), "--variation", "v_beta"])
    for name in ("portfolio.json", "portfolio_trades.csv", "full_history_trades.csv"):
        shutil.copyfile(run_dir / "_invalidated" / "portfolio" / name, run_dir / name)
    (run_dir / "_stage_portfolio.json").write_text(marker, encoding="utf-8")

    run = rb.RunDir.open(run_dir)
    with pytest.raises(SystemExit) as err:
        run.require("portfolio.json", "portfolio")
    assert "selection.json" in str(err.value)


def test_an_ingested_study_without_provenance_is_never_deployable(
    study: tuple[Path, Path, Path],
) -> None:
    """`--from` hashes the files as they are NOW, not the ones that produced study.csv."""
    _cfg, _src, run_dir = study
    _run_edge(study)  # ingests a hand-written study: nothing ties it to this config
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)

    run = rb.RunDir.open(run_dir)
    with pytest.raises(SystemExit) as err:
        run.assert_deployable()
    assert "provenance" in str(err.value).lower() or "herkunft" in str(err.value).lower()


def test_a_study_carrying_provenance_is_deployable_and_tracks_its_own_inputs(
    study: tuple[Path, Path, Path],
) -> None:
    """A study that records what IT was computed from can be ingested and still verified."""
    cfg, src, run_dir = study
    lineage.write_provenance(src, lineage.external_inputs(cfg, _load(cfg)))
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)

    rb.RunDir.open(run_dir).assert_deployable()  # must not raise

    _write_config(cfg, marker="edited-after-the-study")  # the source's own inputs are now stale
    with pytest.raises(SystemExit):
        rb.RunDir.open(run_dir).require("study.csv", "edge")


def test_code_changing_between_stages_blocks_deployment(
    study: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """external_inputs covers configs and data, never the research code itself -- git state does."""
    _cfg, _src, run_dir = study
    lineage.write_provenance(_src, lineage.external_inputs(_cfg, _load(_cfg)))
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    # Stage 3 runs entirely under a different revision -- self-consistent, so it publishes fine.
    monkeypatch.setattr(lineage, "git_state", lambda: {"commit": "deadbeef", "dirty": "clean"})
    _fake_portfolio_stage(run_dir)
    monkeypatch.undo()  # back to the real checkout, which is what a verdict would run under

    run = rb.RunDir.open(run_dir)
    with pytest.raises(SystemExit) as err:
        run.assert_deployable()
    assert "different code" in str(err.value).lower()


def test_an_older_schema_manifest_is_not_deployable(study: tuple[Path, Path, Path]) -> None:
    """Presence of a manifest is not evidence its inputs were ever recorded verifiably."""
    _cfg, _src, run_dir = study
    lineage.write_provenance(_src, lineage.external_inputs(_cfg, _load(_cfg)))
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)

    m = json.loads((run_dir / "_stage_select.json").read_text(encoding="utf-8"))
    m["schema"] = lineage.SCHEMA_VERSION - 1
    m["inputs"] = {"study_config": "sha256:whatever"}  # old shape: hash without a path
    (run_dir / "_stage_select.json").write_text(json.dumps(m, indent=2), encoding="utf-8")

    with pytest.raises(SystemExit) as err:
        rb.RunDir.open(run_dir).assert_deployable()
    assert "schema" in str(err.value).lower()


def test_the_canonical_swap_snapshot_is_recorded_even_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """standard_broker() falls back to swap-less results, so 'absent' is a real computed state.

    Globbing the snapshot directory records only what is THERE. A run computed without the
    snapshot then carries no entry for it at all, so pulling it afterwards -- which changes the
    realized-cost model -- leaves the swap-free portfolio looking perfectly valid.
    """
    missing = tmp_path / "ttp_markets_swaps.json"
    monkeypatch.setattr(lineage, "swap_snapshot_path", lambda _name: missing)

    recorded = lineage.external_inputs(Path("research/config/robustness.py"))
    key = "swap_snapshot:ttp_markets_swaps"
    assert key in recorded, "the snapshot standard_broker() looks for must always be recorded"
    assert recorded[key]["sha256"] == "absent"


def test_rerunning_a_stage_drops_outputs_it_no_longer_produces(
    study: tuple[Path, Path, Path],
) -> None:
    """An optional artifact left behind by a previous run used to deadlock the next stage."""
    cfg, src, run_dir = study
    _run_edge(study)
    assert (run_dir / "overfitting.json").is_file()

    (src / "overfitting.json").unlink()  # a source that no longer carries the optional artifact
    _run_edge(study)

    assert not (run_dir / "overfitting.json").exists()
    select.main(["--run", str(run_dir)])  # must not deadlock


def test_inputs_changing_during_a_stage_abort_publication(
    study: tuple[Path, Path, Path],
) -> None:
    """Stage 3 runs for hours; a config edited mid-run must not be recorded as its input."""
    cfg, _src, run_dir = study
    _run_edge(study)
    run = rb.RunDir.open(run_dir)
    snapshot = lineage.external_inputs(cfg, _load(cfg))

    with pytest.raises(SystemExit) as err, run.stage("select", inputs=snapshot) as st:
        _write_config(cfg, marker="edited-while-the-stage-was-running")
        st.save_json("selection.json", {"variation": "v_alpha"})
    assert "changed while" in str(err.value).lower() or "während" in str(err.value).lower()
    assert lineage.read_manifest(run_dir, "select") is None  # nothing published


def test_legacy_verdict_does_not_demand_full_history(tmp_path: Path) -> None:
    """Legacy mode exists to READ old runs; a run predating an artifact must stay inspectable.

    The run below still cannot finish -- it has no market data -- so this asserts the one thing
    that matters: whatever stops it, it is not the missing full-history stream.
    """
    (tmp_path / "run_manifest.json").write_text('{"config": "x.py"}', encoding="utf-8")
    (tmp_path / "selection.json").write_text('{"variation": "v", "gates": {}}', encoding="utf-8")
    (tmp_path / "portfolio.json").write_text('{"instruments": []}', encoding="utf-8")
    (tmp_path / "portfolio_trades.csv").write_text("market,r\nEURUSD,1.0\n", encoding="utf-8")

    # It dies later, on the missing config -- which is the point: it got PAST the artifact gate.
    with pytest.raises(Exception) as err:  # noqa: B017 - the type is not what is under test
        verdict.main(["--run", str(tmp_path), "--allow-legacy-unverified"])
    assert "full_history_trades.csv" not in str(err.value)


# --------------------------------------------------------- Codex round 2 on PR #38
def test_provenance_does_not_survive_a_swapped_study_artifact(
    study: tuple[Path, Path, Path],
) -> None:
    """A sidecar naming only external inputs does not bind the study FILES it sits beside."""
    cfg, src, run_dir = study
    lineage.write_provenance(src, lineage.external_inputs(cfg, _load(cfg)))

    df = pd.read_csv(src / "study.csv")
    df.loc[0, "mean_oos_pct"] = 999.0  # results swapped in after the provenance was written
    df.to_csv(src / "study.csv", index=False)

    with pytest.raises(SystemExit) as err:
        _run_edge(study)
    assert "provenance" in str(err.value).lower()


def test_stages_using_different_configs_are_not_deployable(
    study: tuple[Path, Path, Path], tmp_path: Path
) -> None:
    """--config is a supported override, so nothing stopped stage 3 from using another config."""
    cfg, src, run_dir = study
    lineage.write_provenance(src, lineage.external_inputs(cfg, _load(cfg)))
    _run_edge(study)
    select.main(["--run", str(run_dir)])

    other = _write_config(tmp_path / "cfg_other.py", marker="a different study config")
    _fake_portfolio_stage(run_dir, config=other)

    with pytest.raises(SystemExit) as err:
        rb.RunDir.open(run_dir).assert_deployable()
    assert "study_config" in str(err.value)


def test_the_git_digest_covers_staged_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    """`git diff` omits the index: restaging different content kept the digest identical."""
    calls: list[tuple[str, ...]] = []

    class _R:
        returncode = 0
        stdout = ""

    def _fake_run(args, **_kw):  # type: ignore[no-untyped-def]
        calls.append(tuple(args))
        return _R()

    monkeypatch.setattr("research.stages.lineage.subprocess.run", _fake_run)
    lineage.git_state()
    assert any("--cached" in c for c in calls), "the staged diff must feed the lineage digest"


def test_the_lineage_module_is_in_the_architecture_map() -> None:
    """AGENTS.md's Definition of Done: every added file appears in the module map."""
    doc = (Path(__file__).resolve().parents[1] / "docs" / "architecture.md").read_text("utf-8")
    assert "research/stages/lineage.py" in doc


def test_code_changing_during_a_stage_aborts_publication(
    study: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stage can import revision A and finish after the checkout moved to B."""
    _cfg, _src, run_dir = study
    _run_edge(study)
    run = rb.RunDir.open(run_dir)  # git state is captured when the stage's work begins
    monkeypatch.setattr(lineage, "git_state", lambda: {"commit": "beefdead", "dirty": "clean"})

    with pytest.raises(SystemExit) as err, run.stage("select") as st:
        st.save_json("selection.json", {"variation": "v_alpha"})
    assert "code" in str(err.value).lower()
    assert lineage.read_manifest(run_dir, "select") is None


def test_legacy_acceptance_is_refused_when_the_run_has_manifests(
    study: tuple[Path, Path, Path],
) -> None:
    """Legacy mode is for wholly pre-lineage runs, not a blanket pass for unclaimed files."""
    cfg, src, run_dir = study
    lineage.write_provenance(src, lineage.external_inputs(cfg, _load(cfg)))
    _run_edge(study)

    # An artifact no completed stage claims, dropped into a run that DOES have lineage.
    (run_dir / "stray_evidence.json").write_text('{"pbo": 0.01}', encoding="utf-8")
    run = rb.RunDir.open(run_dir, allow_legacy=True)
    with pytest.raises(SystemExit) as err:
        run.require("stray_evidence.json", "edge")
    assert "not produced by any completed stage" in str(err.value)


def test_upstream_changing_before_publication_aborts_the_stage(
    study: tuple[Path, Path, Path],
) -> None:
    """Verdict can compute PASS, then publish it after selection moved underneath it."""
    _cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])

    run = rb.RunDir.open(run_dir)
    run.require("selection.json", "select")  # read it, recording its hash
    with pytest.raises(SystemExit) as err, run.stage("portfolio") as st:
        select.main(["--run", str(run_dir), "--variation", "v_beta"])  # upstream moves mid-stage
        st.save_json("portfolio.json", {"variation": "v_alpha"})
    assert "selection.json" in str(err.value)
    assert lineage.read_manifest(run_dir, "portfolio") is None


# --------------------------------------------------------- Codex round 3 on PR #38
def test_two_writers_for_one_stage_cannot_interleave(tmp_path: Path) -> None:
    """The hours-long portfolio stage is plausibly launched twice against one run directory."""
    run = rb.RunDir.open(tmp_path)
    with run.stage("edge") as first:
        first.save_json("run_manifest.json", {"config": "a"})
        second = rb.RunDir.open(tmp_path).stage("edge")
        # Separate staging areas: entering the second must not wipe the first one's work.
        with second:
            second.save_json("run_manifest.json", {"config": "b"})
        assert (first.file("run_manifest.json")).is_file()


def test_a_publication_lock_refuses_a_concurrent_writer(tmp_path: Path) -> None:
    run = rb.RunDir.open(tmp_path)
    writer = run.stage("edge")
    (tmp_path / ".staging_edge.lock").write_text("999", encoding="utf-8")
    with pytest.raises(SystemExit) as err, writer as st:
        st.save_json("run_manifest.json", {"config": "a"})
    assert "in progress" in str(err.value)


def test_untracked_file_contents_feed_the_git_digest(monkeypatch: pytest.MonkeyPatch) -> None:
    """An untracked module runs like a tracked one; only its PATH shows up in git status."""
    calls: list[tuple[str, ...]] = []

    class _R:
        returncode = 0
        stdout = ""

    def _fake_run(args, **_kw):  # type: ignore[no-untyped-def]
        calls.append(tuple(args))
        return _R()

    monkeypatch.setattr("research.stages.lineage.subprocess.run", _fake_run)
    lineage.git_state()
    assert any("--others" in c for c in calls), "untracked files must be enumerated"


def test_deployability_verifies_independently_of_the_caller(
    study: tuple[Path, Path, Path],
) -> None:
    """The advertised gate must not depend on the verdict happening to call require() first."""
    cfg, src, run_dir = study
    lineage.write_provenance(src, lineage.external_inputs(cfg, _load(cfg)))
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)
    rb.RunDir.open(run_dir).assert_deployable()  # clean: must not raise

    df = pd.read_csv(run_dir / "study.csv")
    df.loc[0, "mean_oos_pct"] = 999.0
    df.to_csv(run_dir / "study.csv", index=False)

    with pytest.raises(SystemExit) as err:
        rb.RunDir.open(run_dir).assert_deployable()  # called directly, nothing required first
    assert "study.csv" in str(err.value)


def test_a_manifest_without_a_study_config_input_is_not_deployable(
    study: tuple[Path, Path, Path],
) -> None:
    """An empty input record has nothing to verify, so verify_inputs() reports no drift."""
    cfg, src, run_dir = study
    lineage.write_provenance(src, lineage.external_inputs(cfg, _load(cfg)))
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)

    m = json.loads((run_dir / "_stage_select.json").read_text(encoding="utf-8"))
    m["inputs"] = {}
    (run_dir / "_stage_select.json").write_text(json.dumps(m, indent=2), encoding="utf-8")

    with pytest.raises(SystemExit) as err:
        rb.RunDir.open(run_dir).assert_deployable()
    assert "study config" in str(err.value)


def test_invalidated_downstream_outputs_are_quarantined(
    study: tuple[Path, Path, Path],
) -> None:
    """A stale report.html saying PASS must not stay where `just report` will open it."""
    _cfg, _src, run_dir = study
    _run_edge(study)
    select.main(["--run", str(run_dir)])
    _fake_portfolio_stage(run_dir)
    _fake_verdict_stage(run_dir)
    assert (run_dir / "verdict.json").is_file()

    select.main(["--run", str(run_dir), "--variation", "v_beta"])

    assert not (run_dir / "verdict.json").exists()
    assert (run_dir / "_invalidated" / "verdict" / "verdict.json").is_file()
    assert not (run_dir / "portfolio.json").exists()


def test_the_catalog_gate_reseeds_an_instrument_whose_csv_changed(tmp_path: Path) -> None:
    """Seeding is skipped when the instrument is present, so the CSV gate must sit THERE."""
    from core.data import mt5_csv

    catalog = tmp_path / "catalog"
    catalog.mkdir()
    csv = tmp_path / "eurusd.csv"
    csv.write_text("a,b\n1,2\n", encoding="utf-8")
    (catalog / ".timestamp_frame").write_text(mt5_csv.MT5_SERVER_TZ, encoding="utf-8")
    mt5_csv._stamp_catalog_source(catalog, "EURUSD.SIM", csv)

    assert mt5_csv.catalog_source_drift(catalog, {"EURUSD.SIM": csv}) == []
    csv.write_text("a,b\n1,3\n", encoding="utf-8")  # the file changes; the Parquet bars do not
    assert mt5_csv.catalog_source_drift(catalog, {"EURUSD.SIM": csv}) == ["EURUSD.SIM"]
    with pytest.raises(RuntimeError, match="different CSV content"):
        mt5_csv.require_current_sources(catalog, {"EURUSD.SIM": csv})


def test_a_stage_that_seeds_the_catalog_can_still_publish(
    study: tuple[Path, Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seeding PRODUCES the catalog, so it cannot be part of the pre-work snapshot.

    Hashing it up front makes the stage's own seeding look like input drift, and Stage 1 refuses
    to publish after the full sweep -- the most expensive possible place to discover it. Every
    other test ingests via --from and never seeds, so only this one covers that path.
    """
    cfg, src, run_dir = study
    seeded: dict[str, bool] = {}

    def _fake_study(_config: Path) -> Path:
        # Stand in for the sweep: seed the catalog, exactly as the real one does.
        marker = REPO_ROOT / "catalog" / SOURCE_MARKER
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text('{"SEEDED.SIM": "sha256:deadbeef"}', encoding="utf-8")
        seeded["yes"] = True
        return src / "study.csv"

    original = REPO_ROOT / "catalog" / SOURCE_MARKER
    backup = original.read_text(encoding="utf-8") if original.is_file() else None
    monkeypatch.setattr(edge, "_run_study", _fake_study)
    try:
        edge.main([str(cfg), "--run", str(run_dir)])  # no --from: takes the seeding path
    finally:
        if backup is not None:
            original.write_text(backup, encoding="utf-8")
        elif original.is_file():
            original.unlink()

    assert seeded, "the test must exercise the seeding path"
    assert lineage.read_manifest(run_dir, "edge") is not None, "stage 1 refused to publish"


def test_the_module_docstring_describes_the_current_state() -> None:
    """AGENTS.md forbids historical narrative in docstrings."""
    doc = lineage.__doc__ or ""
    for banned in ("Until now", "previous attempt", "once reported", "used to"):
        assert banned not in doc, f"docstring still narrates history: {banned!r}"


# ------------------------------------------------------------------ helpers
def _load(cfg: Path):  # type: ignore[no-untyped-def]
    from research.engine.config import load_config_module

    return load_config_module(cfg)


def _fake_portfolio_stage(run_dir: Path, config: Path | None = None) -> None:
    """Publish a Stage 3 result through the REAL writer, without running hours of backtests.

    Only the lineage is under test here; the numbers are irrelevant, so this stands in for the
    compute while keeping the publication path identical to production.
    """
    run = rb.RunDir.open(run_dir)
    run.require("selection.json", "select")
    sel = json.loads((run_dir / "selection.json").read_text(encoding="utf-8"))
    cfg_path = config if config is not None else run.study_config()
    inputs = lineage.external_inputs(cfg_path, _load(cfg_path))
    with run.stage("portfolio", argv={"risk": "flat:0.15"}, inputs=inputs) as st:
        frame = pd.DataFrame({"market": ["EURUSD"], "r": [1.0], "swap_r": [0.0]})
        frame.to_csv(st.file("portfolio_trades.csv"), index=False)
        frame.to_csv(st.file("full_history_trades.csv"), index=False)
        st.save_json(
            "portfolio.json",
            {"variation": sel["variation"], "instruments": ["EURUSD"], "tail_cap_pct": 0.2},
        )


def _fake_verdict_stage(run_dir: Path) -> None:
    run = rb.RunDir.open(run_dir)
    with run.stage("verdict", argv={}) as st:
        st.save_json("verdict.json", {"passed": False})
