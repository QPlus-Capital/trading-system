"""Content-addressed lineage for the staged research pipeline (#31).

A research run is four stages writing into one directory. Until now a stage only checked that its
input FILE EXISTED, so artifacts from different configurations or executions could be combined
without anyone noticing -- a run once reported one variation's gate evidence beside another
variation's numbers, because stage 2 had been re-run after stage 3 read it.

This module makes each stage record what it was computed FROM, by content:

* every external input (study config, live config, instrument definitions, raw CSVs, broker/swap
  snapshot) is hashed by content, never trusted by path -- editing a config in place must
  invalidate everything downstream;
* every upstream artifact it read is recorded with the hash it had at read time;
* every output it wrote is recorded with its hash.

Reading is the gate. :meth:`StageManifest.verify` re-hashes the files on disk and refuses when
anything moved, which is the path that actually matters: the previous attempt at this put its
check on the WRITE side, where the failing case never went.

Completion is a manifest file, written last and atomically. A stage that dies half-way leaves no
manifest, so its outputs are invisible to everything downstream rather than half-visible.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from core.paths import REPO_ROOT

SCHEMA_VERSION = 1

# The pipeline order. A stage completing invalidates every stage after it: its outputs are the
# inputs those stages were computed from, so their results no longer describe anything real.
STAGE_ORDER: tuple[str, ...] = ("edge", "select", "portfolio", "verdict")

_MANIFEST_PREFIX = "_stage_"
_STAGING_PREFIX = ".staging_"


class LineageError(SystemExit):
    """A stage refused to run because its inputs are not the ones it was computed from.

    Deliberately a ``SystemExit``: every raise site is a CLI-level fail-closed, and the operator
    needs the message, not a traceback.
    """


# --------------------------------------------------------------------------------------------
# hashing
# --------------------------------------------------------------------------------------------
def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    """Content hash of one file, streamed so a 25k-row CSV costs nothing measurable."""
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _repo_relative(path: Path) -> str:
    """``path`` relative to the repo when inside it, so manifests survive a moved checkout."""
    try:
        return Path(path).resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def hash_paths(paths: dict[str, str | Path]) -> dict[str, dict[str, str]]:
    """``{label: {"path": ..., "sha256": ...}}`` for each file; missing ones hash to ``"absent"``.

    The PATH is stored alongside the hash on purpose. A hash alone proves that a recorded input
    was some particular content, but it cannot be re-checked later -- nothing knows which file to
    re-hash. Storing the path makes the recorded input verifiable, which is what lets a downstream
    stage refuse a config that was edited in place after the upstream stage ran.

    Absence is itself a fact worth recording: a run whose swap snapshot was missing and one where
    it was present are not the same computation, and must not validate against each other.
    """
    out: dict[str, dict[str, str]] = {}
    for label, p in paths.items():
        path = Path(p)
        out[label] = {
            "path": _repo_relative(path),
            "sha256": sha256_file(path) if path.is_file() else "absent",
        }
    return out


def rehash_recorded(entry: dict[str, str]) -> str:
    """Re-hash the file a manifest input entry points at, as it is on disk NOW."""
    p = Path(entry["path"])
    f = p if p.is_absolute() else REPO_ROOT / p
    return sha256_file(f) if f.is_file() else "absent"


def git_state() -> dict[str, str]:
    """Current commit plus a digest of any uncommitted changes.

    A dirty worktree is not reproducible, so the digest of ``git status --porcelain`` +
    ``git diff`` is recorded: two runs from the same commit but different edits get different
    lineage, which is the honest answer.
    """
    def _run(*args: str) -> str:
        try:
            r = subprocess.run(
                ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, timeout=30
            )
            return r.stdout if r.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):  # git absent / not a repo
            return ""

    commit = _run("rev-parse", "HEAD").strip() or "unknown"
    dirt = _run("status", "--porcelain") + _run("diff")
    return {"commit": commit, "dirty": sha256_bytes(dirt.encode()) if dirt.strip() else "clean"}


# --------------------------------------------------------------------------------------------
# the manifest
# --------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class StageManifest:
    """What one stage was computed from, and what it produced."""

    stage: str
    run_id: str
    completed_at: str
    git: dict[str, str]
    argv: dict[str, Any]
    seeds: dict[str, Any]
    inputs: dict[str, Any]  # external content hashes (configs, raw data, broker snapshot)
    semantics: dict[str, Any]  # variation, train length, universe, stops, risk policy/fraction
    upstream: dict[str, str]  # artifact -> hash AT READ TIME
    outputs: dict[str, str]  # artifact -> hash as written
    schema: int = SCHEMA_VERSION

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema": self.schema,
                "stage": self.stage,
                "run_id": self.run_id,
                "completed_at": self.completed_at,
                "git": self.git,
                "argv": self.argv,
                "seeds": self.seeds,
                "inputs": self.inputs,
                "semantics": self.semantics,
                "upstream": self.upstream,
                "outputs": self.outputs,
            },
            indent=2,
            sort_keys=True,
            default=str,
        )

    @classmethod
    def from_json(cls, text: str) -> StageManifest:
        d = json.loads(text)
        return cls(
            stage=d["stage"],
            run_id=d["run_id"],
            completed_at=d["completed_at"],
            git=d.get("git", {}),
            argv=d.get("argv", {}),
            seeds=d.get("seeds", {}),
            inputs=d.get("inputs", {}),
            semantics=d.get("semantics", {}),
            upstream=d.get("upstream", {}),
            outputs=d.get("outputs", {}),
            schema=int(d.get("schema", 0)),
        )

    def verify_outputs(self, run_path: Path) -> list[str]:
        """Artifacts whose content on disk no longer matches what this stage wrote."""
        drifted = []
        for name, recorded in self.outputs.items():
            f = run_path / name
            actual = sha256_file(f) if f.is_file() else "absent"
            if actual != recorded:
                drifted.append(f"{name}\n      recorded {recorded}\n      actual   {actual}")
        return drifted

    def verify_inputs(self) -> list[str]:
        """External inputs whose CONTENT changed since this stage ran.

        This is the check the output hashes cannot make. ``study.csv`` may sit untouched while the
        config it was computed from was edited in place -- same path, different meaning. A stage
        reading that ``study.csv`` would then combine it with the NEW config's instruments and
        account profile, and every hash would still agree.
        """
        drifted = []
        for label, entry in _walk_inputs(self.inputs):
            actual = rehash_recorded(entry)
            if actual != entry["sha256"]:
                drifted.append(
                    f"{label} ({entry['path']})"
                    f"\n      recorded {entry['sha256']}\n      actual   {actual}"
                )
        return drifted


def _walk_inputs(
    inputs: dict[str, Any], prefix: str = ""
) -> list[tuple[str, dict[str, str]]]:
    """Flatten a manifest's ``inputs`` into ``(label, entry)`` pairs.

    Handles the one level of nesting ``external_inputs`` produces (``raw_data``) and silently
    skips anything that is not a path+hash entry, so a manifest written by an older schema is
    read for what it does carry rather than crashing the stage that reads it.
    """
    out: list[tuple[str, dict[str, str]]] = []
    for label, value in inputs.items():
        name = f"{prefix}{label}"
        if not isinstance(value, dict):
            continue
        if "path" in value and "sha256" in value:
            out.append((name, {"path": str(value["path"]), "sha256": str(value["sha256"])}))
        else:
            out.extend(_walk_inputs(value, prefix=f"{name}."))
    return out


def manifest_path(run_path: Path, stage: str) -> Path:
    return run_path / f"{_MANIFEST_PREFIX}{stage}.json"


def read_manifest(run_path: Path, stage: str) -> StageManifest | None:
    f = manifest_path(run_path, stage)
    if not f.is_file():
        return None
    try:
        return StageManifest.from_json(f.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, KeyError):
        return None  # unreadable == incomplete; the stage must be re-run


def producing_stage(run_path: Path, artifact: str) -> tuple[str, StageManifest] | None:
    """Which completed stage claims ``artifact`` as its output."""
    for stage in STAGE_ORDER:
        m = read_manifest(run_path, stage)
        if m is not None and artifact in m.outputs:
            return stage, m
    return None


# --------------------------------------------------------------------------------------------
# writing a stage
# --------------------------------------------------------------------------------------------
class StageWriter:
    """Collects a stage's outputs in a staging directory and commits them atomically.

    Used as a context manager. Files are written under ``.staging_<stage>/`` and only moved into
    the run directory once the body finishes without raising; the manifest -- the completion
    marker -- is written last, so an interrupted stage leaves nothing that downstream will accept.
    """

    def __init__(
        self,
        run_path: Path,
        stage: str,
        *,
        run_id: str,
        argv: dict[str, Any] | None = None,
        seeds: dict[str, Any] | None = None,
        inputs: dict[str, Any] | None = None,
        semantics: dict[str, Any] | None = None,
    ) -> None:
        self.run_path = run_path
        self.stage = stage
        self.run_id = run_id
        self._argv = argv or {}
        self._seeds = seeds or {}
        self._inputs = inputs or {}
        self._semantics = semantics or {}
        self._upstream: dict[str, str] = {}
        self._staging = run_path / f"{_STAGING_PREFIX}{stage}"
        self._names: list[str] = []

    # -- inputs the stage consumed --
    def record_upstream(self, artifact: str, digest: str) -> None:
        """Note that this stage read ``artifact`` while it hashed to ``digest``."""
        self._upstream[artifact] = digest

    def add_semantics(self, **kw: Any) -> None:
        """Record the decisions this stage made (variation, universe, risk ...)."""
        self._semantics.update(kw)

    # -- outputs --
    def file(self, name: str) -> Path:
        """A staging path to write ``name`` to; it appears in the run dir only on commit."""
        if name not in self._names:
            self._names.append(name)
        return self._staging / name

    def save_json(self, name: str, obj: dict[str, Any]) -> Path:
        f = self.file(name)
        f.write_text(json.dumps(obj, indent=2), encoding="utf-8")
        return f

    # -- lifecycle --
    def __enter__(self) -> StageWriter:
        shutil.rmtree(self._staging, ignore_errors=True)
        self._staging.mkdir(parents=True, exist_ok=True)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        if exc_type is not None:  # the stage failed -> publish nothing at all
            shutil.rmtree(self._staging, ignore_errors=True)
            return
        self._commit()

    def _commit(self) -> None:
        # 1. move every produced file into the run directory
        outputs: dict[str, str] = {}
        for name in self._names:
            src = self._staging / name
            if not src.is_file():
                continue  # the stage declared it but never wrote it
            dst = self.run_path / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            os.replace(src, dst)
            outputs[name] = sha256_file(dst)
        shutil.rmtree(self._staging, ignore_errors=True)

        # 2. anything computed FROM this stage is now stale -- remove those completion markers
        #    before publishing ours, so no window exists in which both look valid.
        invalidate_downstream(self.run_path, self.stage)

        # 3. the manifest is the completion marker: written last, atomically.
        m = StageManifest(
            stage=self.stage,
            run_id=self.run_id,
            completed_at=datetime.now(tz=UTC).isoformat(timespec="seconds"),
            git=git_state(),
            argv=self._argv,
            seeds=self._seeds,
            inputs=self._inputs,
            semantics=self._semantics,
            upstream=self._upstream,
            outputs=outputs,
        )
        final = manifest_path(self.run_path, self.stage)
        tmp = final.with_suffix(".json.tmp")
        tmp.write_text(m.to_json(), encoding="utf-8")
        os.replace(tmp, final)


def invalidate_downstream(run_path: Path, stage: str) -> list[str]:
    """Drop the completion markers of every stage that runs after ``stage``. Returns their names."""
    if stage not in STAGE_ORDER:
        return []
    dropped = []
    for later in STAGE_ORDER[STAGE_ORDER.index(stage) + 1 :]:
        f = manifest_path(run_path, later)
        if f.is_file():
            f.unlink()
            dropped.append(later)
    return dropped


# --------------------------------------------------------------------------------------------
# reading a stage's output -- the gate
# --------------------------------------------------------------------------------------------
@dataclass
class VerifiedInputs:
    """Hashes of the upstream artifacts a stage actually read, for its own manifest."""

    digests: dict[str, str] = field(default_factory=dict)

    def add(self, artifact: str, digest: str) -> None:
        self.digests[artifact] = digest


def verify_artifact(
    run_path: Path, artifact: str, produced_by: str, *, allow_legacy: bool
) -> str:
    """Hash of ``artifact``, after checking it is what its producing stage actually wrote.

    Fails closed when the producing stage never completed, when the file changed since, or when
    any of that stage's own outputs drifted -- an edited ``study.csv`` invalidates the whole edge
    stage, not only the one file the caller happened to ask for.

    ``allow_legacy`` tolerates a run that predates lineage (no manifests at all). Such a run can
    still be inspected, but :func:`assert_deployable` refuses to call it deployable.
    """
    f = run_path / artifact
    if not f.is_file():
        raise LineageError(
            f"missing '{artifact}' in {run_path}\n  -> run the '{produced_by}' stage first."
        )

    found = producing_stage(run_path, artifact)
    if found is None:
        if allow_legacy or not any(read_manifest(run_path, s) for s in STAGE_ORDER):
            # No lineage anywhere: a pre-#31 run. Permitted only in legacy mode, and never
            # deployable -- see assert_deployable.
            if allow_legacy:
                return sha256_file(f)
            raise LineageError(
                f"'{artifact}' in {run_path} has no lineage (run predates artifact hashing).\n"
                "  -> re-run the pipeline, or pass --allow-legacy-unverified to inspect it\n"
                "     (a legacy run can never produce a deployable PASS)."
            )
        raise LineageError(
            f"'{artifact}' in {run_path} was not produced by any completed stage.\n"
            f"  -> re-run the '{produced_by}' stage."
        )

    stage, manifest = found
    drifted = manifest.verify_outputs(run_path)
    if drifted:
        detail = "\n    - ".join(drifted)
        raise LineageError(
            f"stage '{stage}' artifacts changed since it ran:\n    - {detail}\n"
            f"  -> re-run '{stage}' (and everything after it); its recorded results no longer\n"
            "     describe the files on disk."
        )
    # The external side of the same question: the artifacts are intact, but were they computed
    # from the configs and raw data that are on disk right now? Editing a config in place leaves
    # every output hash valid while changing what those outputs MEAN.
    changed = manifest.verify_inputs()
    if changed:
        detail = "\n    - ".join(changed)
        raise LineageError(
            f"inputs of stage '{stage}' changed since it ran:\n    - {detail}\n"
            f"  -> re-run '{stage}' (and everything after it); '{artifact}' was computed from\n"
            "     different content than what these paths hold now."
        )
    return manifest.outputs[artifact]


def assert_deployable(run_path: Path, *, allow_legacy: bool) -> None:
    """Refuse a deployable verdict for a run whose lineage cannot be verified.

    Legacy mode exists to READ an old run, not to bless it: a result whose inputs cannot be
    confirmed must never reach a live-money decision.
    """
    missing = [s for s in STAGE_ORDER[:-1] if read_manifest(run_path, s) is None]
    if missing:
        raise LineageError(
            f"run {run_path} has no verified lineage for: {', '.join(missing)}.\n"
            "  -> a run without content-verified inputs cannot produce a deployable verdict."
        )


def new_run_id() -> str:
    return str(uuid.uuid4())


# --------------------------------------------------------------------------------------------
# the external inputs every stage depends on
# --------------------------------------------------------------------------------------------
def external_inputs(
    study_config: Path, cfg: Any = None, fixed_config: Path | None = None
) -> dict[str, Any]:
    """Content hashes of everything outside the run directory that a stage's result depends on.

    Hashed by CONTENT, never by path: editing ``robustness.py`` in place changes the computation
    while leaving the filename identical, and a path-keyed manifest would happily validate the
    old result against the new config.

    Covers the study config, the frozen live config (when a stage trades its stops), the
    instrument definitions, every raw CSV the config lists, and the broker swap snapshot.
    """
    paths: dict[str, str | Path] = {
        "study_config": study_config,
        "instruments": REPO_ROOT / "core" / "instruments.py",
        "broker": REPO_ROOT / "core" / "broker.py",
    }
    if fixed_config is not None:
        paths["fixed_live_config"] = fixed_config
    for snap in sorted((REPO_ROOT / "core" / "config" / "broker").glob("*.json")):
        paths[f"swap_snapshot:{snap.stem}"] = snap

    out: dict[str, Any] = hash_paths(paths)
    if cfg is not None:  # the raw H4 data the whole study is computed from
        raw: dict[str, str | Path] = {}
        for entry in getattr(cfg, "INSTRUMENTS", []):
            factory, csv_path = entry[0], entry[1]
            raw[str(factory().raw_symbol)] = REPO_ROOT / str(csv_path)
        out["raw_data"] = hash_paths(raw)
    return out
