"""Content-addressed lineage for the staged research pipeline (#31).

A research run is four stages writing into one directory. File existence proves nothing about
where a file came from, so each stage records what it was computed FROM, by content, and every
read is checked against that record.

Each stage manifest holds:

* every external input -- study config, live config, instrument definitions, raw CSVs, broker
  swap snapshot, the catalog's own record of which CSV content it was seeded from -- hashed by
  content and stored with its path, so it stays re-checkable;
* the git state (commit plus a digest of worktree, index and untracked file contents) captured
  when the stage's work begins, since external inputs never cover the research code itself;
* every upstream artifact it read, with the hash it had at read time;
* every output it wrote, with its hash.

**Reading is the gate.** :func:`verify_artifact` re-hashes what is on disk and refuses unless the
producing stage's outputs, its external inputs, and the whole chain still agree. Checking only on
the write side would leave the failing case -- reading an artifact somebody else replaced --
entirely uncovered.

**Publication is atomic and exclusive.** Outputs are staged per invocation, moved under a lock,
and the manifest -- the completion marker -- is written last. A stage that dies half-way leaves no
manifest, so its outputs are invisible downstream rather than half-visible. Inputs, git state and
upstream hashes are re-checked immediately before publishing, so a stage that ran for hours
cannot record content that appeared after its results were computed.

**Deployability is separate and stricter** (:func:`assert_deployable`): it re-verifies everything
independently of the caller, and additionally requires the current manifest schema, a study
provenance that is not merely ingested, one study config across all stages, and one git state.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import subprocess
import uuid
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any

from core.broker import TTP_MARKETS, swap_snapshot_path
from core.data.mt5_csv import read_catalog_sources
from core.paths import REPO_ROOT

from research.engine.candidate_returns import CANDIDATE_ARTIFACTS

#: Bumped whenever a manifest or provenance record gains a field the checks rely on. Adding one
#: without bumping would let an older record pass every check by carrying nothing to check.
SCHEMA_VERSION = 2

# A study ingested with ``--from`` carries this unless it recorded its own provenance: the
# hashes taken at ingestion describe the files as they are NOW, not the ones that produced it.
PROVENANCE_INGESTED = "ingested-unverified"
#: Written by a stage that computed its own study; the only other accepted value is a study's
#: own recorded provenance. A manifest carrying neither cannot be deployed.
PROVENANCE_COMPUTED = "computed-here"
PROVENANCE_RECORDED = "recorded-by-study"
_PROVENANCE_FILE = "_provenance.json"

#: What ``git_state()`` reports when git cannot be consulted at all. Identical placeholders in
#: every manifest would otherwise satisfy the code-lineage comparison, so deployment rejects it.
UNKNOWN_GIT = "unknown"

#: The artifacts a stage must have published for it to count as complete. A manifest alone is not
#: evidence: an empty output map verifies vacuously, and StageWriter silently skips a declared
#: output that was never written.
REQUIRED_OUTPUTS: dict[str, tuple[str, ...]] = {
    "edge": ("run_manifest.json", "study.csv", "edge_ranking.csv"),
    "select": ("selection.json",),
    "portfolio": ("portfolio.json", "portfolio_trades.csv", "full_history_trades.csv"),
}

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


def drifted_inputs(inputs: dict[str, Any]) -> list[str]:
    """Recorded inputs whose content on disk differs from the recorded hash, right now."""
    out = []
    for label, entry in _walk_inputs(inputs):
        actual = rehash_recorded(entry)
        if actual != entry["sha256"]:
            out.append(
                f"{label} ({entry['path']})"
                f"\n      recorded {entry['sha256']}\n      actual   {actual}"
            )
    # ``catalog_sources`` is per-instrument digests lifted out of one shared marker file, not a
    # path+hash pair, so the walk above cannot see it -- and silently skipping it would be the
    # same "nothing recorded reads as nothing changed" hole these checks exist to close.
    recorded_catalog = inputs.get("catalog_sources")
    if isinstance(recorded_catalog, dict):
        current = read_catalog_sources(REPO_ROOT / "catalog")
        for name, was in sorted(recorded_catalog.items()):
            now = current.get(name, "absent")
            if now != was:
                out.append(f"catalog bars for {name}\n      recorded {was}\n      actual   {now}")
    return out


#: Core files every study provenance record must bind. Candidate-return sidecars are additive:
#: new records bind them too, while records produced before that schema existed remain readable
#: when no sidecar is present beside them.
REQUIRED_STUDY_ARTIFACTS: tuple[str, ...] = (
    "study.csv",
    "ranking.csv",
    "overfitting.json",
)
STUDY_ARTIFACTS: tuple[str, ...] = REQUIRED_STUDY_ARTIFACTS + CANDIDATE_ARTIFACTS


def write_provenance(study_dir: Path, inputs: dict[str, Any]) -> Path:
    """Record, inside a study directory, what that study was computed from AND produced.

    Without this a study ingested via ``--from`` can only be hashed at INGESTION time, which
    describes the files as they are then rather than the ones that produced it -- so a stale
    study would carry a manifest certifying unrelated current inputs.

    The artifact hashes matter just as much as the inputs: a sidecar that names only the config
    still validates after the results beside it have been swapped, which would let arbitrary
    numbers inherit a genuine provenance record.
    """
    artifacts = hash_paths({name: study_dir / name for name in STUDY_ARTIFACTS})
    f = study_dir / _PROVENANCE_FILE
    payload = {
        "schema": SCHEMA_VERSION,
        "inputs": inputs,
        "artifacts": artifacts,
        # The code that PRODUCED the study. Without it an ingesting run attributes the study to
        # whatever is checked out at ingestion, so a study computed under one engine revision
        # could be combined with downstream stages run under another and still look consistent.
        "git": git_state(),
    }
    f.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return f


class ProvenanceMismatch(LineageError):
    """A study carries a provenance record that no longer describes the files beside it."""


def read_provenance(study_dir: Path) -> tuple[dict[str, Any], dict[str, str]] | None:
    """``(inputs, producer git state)`` a study recorded for itself, or ``None`` if it never did.

    Raises :class:`ProvenanceMismatch` when the record exists but the study files it names have
    changed -- refusing loudly, because silently falling back to "unprovenanced" would turn a
    detected swap into a mere downgrade.
    """
    f = study_dir / _PROVENANCE_FILE
    if not f.is_file():
        return None
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if int(d.get("schema", 0)) != SCHEMA_VERSION:
        return None
    inputs = d.get("inputs")
    if not isinstance(inputs, dict):
        return None

    # An absent or partial core record is not a weaker guarantee, it is NO guarantee: the loop
    # below would find nothing to compare and report no drift. Candidate sidecars are additive,
    # but any one that exists beside the study must also be recorded.
    recorded = d.get("artifacts")
    if not isinstance(recorded, dict) or any(
        not isinstance(recorded.get(n), dict) or "sha256" not in recorded.get(n, {})
        for n in REQUIRED_STUDY_ARTIFACTS
    ):
        raise ProvenanceMismatch(
            f"study in {study_dir} carries a provenance record without hashes for every\n"
            f"  core study artifact ({', '.join(REQUIRED_STUDY_ARTIFACTS)}).\n"
            "  -> it cannot bind those results to anything; re-run the study."
        )
    unbound_sidecars = [
        name
        for name in CANDIDATE_ARTIFACTS
        if (study_dir / name).is_file()
        and (not isinstance(recorded.get(name), dict) or "sha256" not in recorded.get(name, {}))
    ]
    if unbound_sidecars:
        raise ProvenanceMismatch(
            f"study in {study_dir} has unbound candidate artifacts "
            f"({', '.join(unbound_sidecars)}).\n"
            "  -> pre-filter evidence must carry content hashes; re-run the study."
        )
    drifted = []
    for name, entry in recorded.items():
        f_art = study_dir / name
        actual = sha256_file(f_art) if f_art.is_file() else "absent"
        if actual != entry.get("sha256"):
            drifted.append(f"{name}\n      recorded {entry.get('sha256')}\n      actual   {actual}")
    if drifted:
        detail = "\n    - ".join(drifted)
        raise ProvenanceMismatch(
            f"study in {study_dir} changed since it recorded its provenance:\n    - {detail}\n"
            "  -> these results are not the ones the recorded config and data produced."
        )

    producer = d.get("git")
    if not isinstance(producer, dict) or producer.get("commit", UNKNOWN_GIT) == UNKNOWN_GIT:
        raise ProvenanceMismatch(
            f"study in {study_dir} records no usable git state for the code that produced it.\n"
            "  -> ingesting it would attribute the study to whatever is checked out now;\n"
            "     re-run the study."
        )
    return dict(inputs), {str(k): str(v) for k, v in producer.items()}


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

    commit = _run("rev-parse", "HEAD").strip() or UNKNOWN_GIT
    # Three sources, because each alone has a blind spot: `git diff` sees only the worktree,
    # `git diff --cached` only the index, and `git status --porcelain` carries status letters and
    # paths but never content. An untracked module -- which runs exactly like a tracked one --
    # appears only in the third, so its CONTENT is hashed explicitly here.
    dirt = _run("status", "--porcelain") + _run("diff") + _run("diff", "--cached")
    untracked = _run("ls-files", "--others", "--exclude-standard").split("\n")
    parts = [dirt]
    for rel in sorted(p.strip() for p in untracked if p.strip()):
        f = REPO_ROOT / rel
        parts.append(f"{rel}:{sha256_file(f) if f.is_file() else 'absent'}")
    blob = "\n".join(parts)
    return {"commit": commit, "dirty": sha256_bytes(blob.encode()) if blob.strip() else "clean"}


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
        return drifted_inputs(self.inputs)


def _walk_inputs(inputs: dict[str, Any], prefix: str = "") -> list[tuple[str, dict[str, str]]]:
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
        git: dict[str, str] | None = None,
        check_git: bool = True,
    ) -> None:
        self.run_path = run_path
        self.stage = stage
        self.run_id = run_id
        # False when ``git`` describes another process's checkout (an ingested study): comparing
        # it against this one at publication would always disagree, and meaninglessly.
        self._check_git = check_git
        # The state when the stage's WORK began, not when it finished. A stage that imported one
        # revision and published after the checkout moved would otherwise claim the new revision
        # produced its results -- and every later stage, running under that revision, would agree.
        self._git = git if git is not None else git_state()
        self._argv = argv or {}
        self._seeds = seeds or {}
        self._inputs = inputs or {}
        self._semantics = semantics or {}
        self._upstream: dict[str, str] = {}
        # Per INVOCATION, not per stage: two portfolio runs against one directory would otherwise
        # share a staging area and each __enter__ would wipe the other's work, letting one process
        # publish files the other produced under its own inputs and semantics.
        self._staging = run_path / f"{_STAGING_PREFIX}{stage}_{os.getpid()}_{uuid.uuid4().hex[:8]}"
        # ONE lock for the whole run, not one per stage: the upstream recheck and the publication
        # that follows it must exclude other STAGES too. Per-stage locks let select replace
        # selection.json between portfolio's recheck and its publish, so portfolio would commit a
        # manifest citing a hash that no longer exists -- hours of work, immediately invalid.
        self._lock = run_path / f"{_STAGING_PREFIX}publication.lock"
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

    @contextlib.contextmanager
    def _publication_lock(self) -> Iterator[None]:
        """Serialise publication so two writers cannot interleave move + manifest."""
        try:
            fd = os.open(self._lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise LineageError(
                f"another stage is publishing into {self.run_path}\n"
                f"  (lock: {self._lock}). Wait for it, or remove the lock if no such process\n"
                "  is running -- two stages publishing into one run corrupt its lineage."
            ) from None
        try:
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            yield
        finally:
            self._lock.unlink(missing_ok=True)

    def _commit(self) -> None:
        # The checks and the publication they authorise happen under ONE run-wide lock. Verifying
        # first and locking afterwards leaves a window in which another stage invalidates exactly
        # what was just verified, so the manifest would cite a hash that no longer exists.
        with self._publication_lock():
            self._verify_still_valid()
            self._publish()

    def _verify_still_valid(self) -> None:
        # 0. The inputs were hashed BEFORE the work started. If any of them changed while the
        #    stage ran -- Stage 3 takes hours -- the results describe the old content while the
        #    manifest would record the new hashes, and nothing downstream could ever tell.
        drifted = drifted_inputs(self._inputs)
        if drifted:
            shutil.rmtree(self._staging, ignore_errors=True)
            detail = "\n    - ".join(drifted)
            raise LineageError(
                f"inputs changed while stage '{self.stage}' was running:\n    - {detail}\n"
                "  -> nothing was published; re-run the stage against the current inputs."
            )

        # 0b. Same question for the code: did the checkout move while this stage ran?
        if self._check_git and (now := git_state()) != self._git:
            shutil.rmtree(self._staging, ignore_errors=True)
            was = self._git
            raise LineageError(
                f"the code changed while stage '{self.stage}' was running:\n"
                f"    - at start: commit {was['commit'][:12]} dirty={was['dirty'][:19]}\n"
                f"    - now:      commit {now['commit'][:12]} dirty={now['dirty'][:19]}\n"
                "  -> nothing was published; these results were computed by different code."
            )

        # 0c. And the upstream artifacts this stage READ: an earlier stage re-run mid-flight would
        #     otherwise let the verdict compute PASS and then publish it on top of a moved chain.
        moved = []
        for artifact, recorded in self._upstream.items():
            f = self.run_path / artifact
            actual = sha256_file(f) if f.is_file() else "absent"
            if actual != recorded:
                moved.append(f"{artifact}\n      read     {recorded}\n      now      {actual}")
        if moved:
            shutil.rmtree(self._staging, ignore_errors=True)
            detail = "\n    - ".join(moved)
            raise LineageError(
                f"upstream artifacts changed while stage '{self.stage}' was running:\n"
                f"    - {detail}\n"
                "  -> nothing was published; the stage before this one was re-run underneath it."
            )

    def _publish(self) -> None:
        """Move the staged outputs in and write the completion marker. Caller holds the lock."""
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

        # 2. drop artifacts the PREVIOUS run of this stage produced but this one did not. Left in
        #    place they deadlock the next stage: it sees the file, calls require(), and is refused
        #    because no completed stage claims it.
        previous = read_manifest(self.run_path, self.stage)
        if previous is not None:
            for name in previous.outputs:
                if name not in outputs:
                    (self.run_path / name).unlink(missing_ok=True)

        # 3. anything computed FROM this stage is now stale -- retire those stages, markers and
        #    outputs alike, before publishing ours, so no window exists in which both look valid.
        invalidate_downstream(self.run_path, self.stage)

        # 4. the manifest is the completion marker: written last, atomically.
        m = StageManifest(
            stage=self.stage,
            run_id=self.run_id,
            completed_at=datetime.now(tz=UTC).isoformat(timespec="seconds"),
            git=self._git,
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
    """Retire every stage that runs after ``stage``: its marker AND its outputs.

    Removing only the marker leaves a readable ``report.html`` and a ``verdict.json`` saying
    PASS beside a selection that no longer exists. Nothing downstream would accept them again,
    but an operator opening the newest report has no way to see that -- so the artifacts go with
    the marker, into ``_invalidated/<stage>/`` where they can still be inspected but are plainly
    not the run's current answer.
    """
    if stage not in STAGE_ORDER:
        return []
    dropped = []
    for later in STAGE_ORDER[STAGE_ORDER.index(stage) + 1 :]:
        f = manifest_path(run_path, later)
        if not f.is_file():
            continue
        m = read_manifest(run_path, later)
        quarantine = run_path / "_invalidated" / later
        if m is not None:
            quarantine.mkdir(parents=True, exist_ok=True)
            for name in m.outputs:
                src = run_path / name
                if src.is_file():
                    os.replace(src, quarantine / Path(name).name)
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


def completed_stages(run_path: Path) -> list[tuple[str, StageManifest]]:
    """Every stage in this run that left a completion marker, in pipeline order."""
    found = []
    for stage in STAGE_ORDER:
        m = read_manifest(run_path, stage)
        if m is not None:
            found.append((stage, m))
    return found


def verify_chain(run_path: Path) -> list[str]:
    """Ways the completed stages in this directory fail to describe ONE coherent run.

    Verifying a stage against its own manifest cannot catch a whole bundle -- manifest plus
    outputs -- copied or restored from a different run: internally it is perfectly consistent.
    What ties the stages together is the shared run id, and the upstream hashes each stage
    recorded when it READ the stage before it.
    """
    problems: list[str] = []
    stages = completed_stages(run_path)
    if not stages:
        return problems

    run_ids = {m.run_id for _, m in stages}
    if len(run_ids) > 1:
        listed = ", ".join(f"{s}={m.run_id}" for s, m in stages)
        problems.append(
            f"stages come from different runs (run ids: {listed}).\n"
            "      -> artifacts from separate runs were combined in one directory."
        )

    for stage, m in stages:
        for artifact, recorded in m.upstream.items():
            f = run_path / artifact
            actual = sha256_file(f) if f.is_file() else "absent"
            if actual != recorded:
                problems.append(
                    f"stage '{stage}' read '{artifact}' at a different version than the one\n"
                    f"      present now:\n      recorded {recorded}\n      actual   {actual}"
                )
    return problems


def verify_run(run_path: Path, *, ignore: str | None = None) -> None:
    """Re-verify every completed stage in ``run_path``: its outputs, its inputs, and the chain.

    Independent of any particular caller. Checking only the stage that produced one artifact is
    not enough for anyone acting on a RESULT: the verdict's own inputs can be untouched while the
    config Stage 1 selected under was edited in place, which changes what the result means.

    ``ignore`` skips one stage -- the stage currently being recomputed. Re-running Stage 4 to
    repair a damaged report must be judged on its prerequisites, not on the very output it is
    about to replace, or the repair would publish a FAIL and only succeed on a second run.
    """
    for stage, m in completed_stages(run_path):
        if stage == ignore:
            continue
        if drift := m.verify_outputs(run_path):
            detail = "\n    - ".join(drift)
            raise LineageError(f"stage '{stage}' artifacts changed since it ran:\n    - {detail}")
        if changed := m.verify_inputs():
            detail = "\n    - ".join(changed)
            raise LineageError(f"inputs of stage '{stage}' changed since it ran:\n    - {detail}")
    if incoherent := verify_chain(run_path):
        detail = "\n    - ".join(incoherent)
        raise LineageError(f"the stages do not form one coherent run:\n    - {detail}")


def verify_artifact(run_path: Path, artifact: str, produced_by: str, *, allow_legacy: bool) -> str:
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
        # Legacy acceptance is for a pre-lineage run, never a blanket pass for an unclaimed file
        # inside a run built with lineage. The distinction is which stage produced the manifests:
        # inspecting a legacy run necessarily creates markers for the stages one re-runs, and
        # those must not lock the operator out of the legacy artifacts still ahead of them. A run
        # whose FIRST stage carries lineage, by contrast, was built with it throughout, so an
        # unclaimed file there is a stray.
        built_with_lineage = read_manifest(run_path, STAGE_ORDER[0]) is not None
        if not built_with_lineage:
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
    # Finally: do the completed stages in this directory describe ONE run at all?
    incoherent = verify_chain(run_path)
    if incoherent:
        detail = "\n    - ".join(incoherent)
        raise LineageError(
            f"the stages in {run_path} do not form one coherent run:\n    - {detail}\n"
            "  -> re-run the pipeline in a clean run directory."
        )
    return manifest.outputs[artifact]


def assert_deployable(run_path: Path, *, allow_legacy: bool, ignore: str | None = None) -> None:
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

    # ``ignore`` drops the stage being recomputed from EVERY check below, not just the artifact
    # verification: judging a verdict by the state of the verdict it is replacing is what made
    # repairing a damaged report take two runs.
    stages = [(s, m) for s, m in completed_stages(run_path) if s != ignore]

    # Schema first: it is the most fundamental diagnosis, and every check below reads fields whose
    # meaning it defines. A manifest from an older schema may carry recognizable outputs while
    # omitting the path+hash input records entirely, so verify_inputs() would find nothing to
    # check and "never recorded" would read as "nothing changed".
    stale = [s for s, m in stages if m.schema != SCHEMA_VERSION]
    if stale:
        raise LineageError(
            f"run {run_path} has manifests written by an unsupported schema: {', '.join(stale)}\n"
            f"  (expected schema {SCHEMA_VERSION}).\n"
            "  -> re-run the pipeline; such a run may be inspected but never deployed."
        )

    verify_run(run_path, ignore=ignore)

    # Every record a manifest can carry must actually be present. A missing one verifies
    # vacuously -- there is nothing to compare against -- so "never recorded" would read as
    # "nothing changed". These are all the places that can happen.
    for stage, m in stages:
        labels = {label for label, _ in _walk_inputs(m.inputs)}
        if "study_config" not in labels:
            raise LineageError(
                f"stage '{stage}' recorded no verifiable study config among its inputs.\n"
                "  -> its results cannot be tied to any configuration; re-run the pipeline."
            )
        missing_outputs = [o for o in REQUIRED_OUTPUTS.get(stage, ()) if o not in m.outputs]
        if missing_outputs:
            raise LineageError(
                f"stage '{stage}' did not publish: {', '.join(missing_outputs)}.\n"
                "  -> a completion marker is not evidence the stage produced anything;\n"
                "     re-run it."
            )
        if stage != STAGE_ORDER[0] and not m.upstream:
            raise LineageError(
                f"stage '{stage}' recorded no upstream artifacts.\n"
                "  -> it cannot be tied to the stage before it; re-run the pipeline."
            )

    edge_manifest = dict(stages).get(STAGE_ORDER[0])
    if edge_manifest is not None:
        provenance = edge_manifest.semantics.get("study_provenance")
        if provenance not in (PROVENANCE_COMPUTED, PROVENANCE_RECORDED):
            raise LineageError(
                f"the study behind this run has no usable provenance ({provenance!r}).\n"
                "  -> the hashes describe the files at ingestion time, not the ones that\n"
                "     produced the study. Re-run the study, or ingest one that recorded its own."
            )

    # --config is a supported override, so nothing stopped Stage 3 from being finished with a
    # different study config than Stage 1 selected under. Each manifest then verifies perfectly on
    # its own, and the shared run id is unchanged -- only comparing the stages catches it.
    shared: dict[str, tuple[str, dict[str, str]]] = {}
    for stage, m in stages:
        for label, entry in _walk_inputs(m.inputs):
            if label.startswith("fixed_live_config"):
                continue  # legitimately present in Stage 3/4 only
            if label in shared and shared[label][1]["sha256"] != entry["sha256"]:
                other, prior = shared[label]
                raise LineageError(
                    f"stages of this run used different '{label}':\n"
                    f"    - {other}: {prior['sha256']} ({prior['path']})\n"
                    f"    - {stage}: {entry['sha256']} ({entry['path']})\n"
                    "  -> selection and extraction describe different configurations; such a\n"
                    "     run cannot produce a deployable verdict."
                )
            shared.setdefault(label, (stage, entry))

    # external_inputs() covers configs and data -- never the research code itself. Two stages run
    # from different revisions of the engine can otherwise be combined into a deployable verdict.
    current = git_state()
    # An environment where git cannot be consulted reports the same placeholder for every stage
    # and for the check itself, so the comparison below would agree with itself and certify a
    # code revision nobody can name.
    unknown = [s for s, m in stages if m.git.get("commit", UNKNOWN_GIT) == UNKNOWN_GIT]
    if unknown or current["commit"] == UNKNOWN_GIT:
        raise LineageError(
            "the code revision behind this run cannot be established "
            f"(unreadable for: {', '.join(unknown) or 'the current checkout'}).\n"
            "  -> a deployable verdict must name the code that produced it; run the pipeline\n"
            "     inside the git checkout."
        )
    recorded = {s: m.git for s, m in stages}
    disagreeing = {s: g for s, g in recorded.items() if g != current}
    if disagreeing:
        listed = "\n    - ".join(
            f"{s}: commit {g.get('commit', '?')[:12]} dirty={g.get('dirty', '?')[:19]}"
            for s, g in disagreeing.items()
        )
        raise LineageError(
            "the stages of this run were computed by different code than is checked out now:\n"
            f"    - {listed}\n"
            f"    - now: commit {current['commit'][:12]} dirty={current['dirty'][:19]}\n"
            "  -> a verdict may only deploy results its own code produced; re-run the stages."
        )


def new_run_id() -> str:
    return str(uuid.uuid4())


# --------------------------------------------------------------------------------------------
# the external inputs every stage depends on
# --------------------------------------------------------------------------------------------
def catalog_inputs(instruments: Iterable[str] | None = None) -> dict[str, Any]:
    """Hashes of the catalog markers, scoped to the instruments a stage actually uses.

    A stage that SEEDS the catalog cannot snapshot it beforehand -- seeding is what produces it.
    Such a stage takes this once seeding is done and merges it into the inputs it captured up
    front, so the record still describes the bars its backtests read.

    Scoping matters as much as timing: the source marker is one shared file covering every
    instrument in the catalog, so hashing it whole would make seeding an unrelated instrument
    for another study invalidate finished research that never touched it.
    """
    out: dict[str, Any] = hash_paths({"catalog_frame": REPO_ROOT / "catalog" / ".timestamp_frame"})
    recorded = read_catalog_sources(REPO_ROOT / "catalog")
    wanted = sorted(recorded) if instruments is None else sorted(instruments)
    out["catalog_sources"] = {name: recorded.get(name, "absent") for name in wanted}
    return out


def external_inputs(
    study_config: Path,
    cfg: Any = None,
    fixed_config: Path | None = None,
    *,
    catalog: bool = True,
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
    # The snapshot standard_broker() looks for is recorded ALWAYS, present or not. It falls back
    # to swap-less results when absent, so absence is a real computation state -- globbing alone
    # would record nothing, and pulling the snapshot later would be invisible to lineage while
    # silently changing the realized-cost model.
    canonical = swap_snapshot_path(TTP_MARKETS.name)
    paths[f"swap_snapshot:{canonical.stem}"] = canonical
    for snap in sorted((REPO_ROOT / "core" / "config" / "broker").glob("*.json")):
        paths.setdefault(f"swap_snapshot:{snap.stem}", snap)

    out: dict[str, Any] = hash_paths(paths)
    ids: list[str] = []
    if cfg is not None:  # the raw H4 data the whole study is computed from
        raw: dict[str, str | Path] = {}
        for entry in getattr(cfg, "INSTRUMENTS", []):
            factory, csv_path = entry[0], entry[1]
            instrument = factory()
            raw[str(instrument.raw_symbol)] = REPO_ROOT / str(csv_path)
            ids.append(str(getattr(instrument, "id", instrument.raw_symbol)))
        out["raw_data"] = hash_paths(raw)
    if catalog:
        # Scoped to this config's instruments: the bars these backtests read, and nothing else.
        out.update(catalog_inputs(ids or None))
    return out
