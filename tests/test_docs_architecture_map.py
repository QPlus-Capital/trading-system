"""Guard against a stale architecture map, in both directions.

Forward: every module path named in docs/architecture.md must exist — a file deleted or renamed
without updating the map fails here. Reverse: every production module on disk must be named in the
map — an undocumented module passes forever otherwise, and a map that *reads* complete while three
load-bearing tools are missing is worse than one that reads incomplete. Both directions cover all
five packages, including workflow/.
"""

import re
import subprocess

from core.paths import REPO_ROOT

_PACKAGES = ("core", "research", "live", "monitoring", "workflow")


def _map_paths() -> set[str]:
    doc = (REPO_ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    pattern = rf"`((?:{'|'.join(_PACKAGES)})/[\w/]+\.py)`"
    paths = set(re.findall(pattern, doc))
    assert paths, "no module paths parsed from architecture.md -- has the format changed?"
    return paths


def _tracked_modules() -> set[str]:
    listing = subprocess.run(
        ["git", "ls-files", "-z", *(f"{pkg}/*.py" for pkg in _PACKAGES)],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
    ).stdout.decode("utf-8")
    return {
        path
        for path in listing.split("\0")
        if path and not path.endswith("__init__.py")
    }


def test_architecture_map_paths_exist() -> None:
    missing = sorted(p for p in _map_paths() if not (REPO_ROOT / p).is_file())
    assert not missing, f"architecture.md references files that no longer exist: {missing}"


def test_every_production_module_is_in_the_map() -> None:
    undocumented = sorted(_tracked_modules() - _map_paths())
    assert not undocumented, (
        "modules on disk that docs/architecture.md never names -- an agent orienting from the map "
        f"concludes they do not exist: {undocumented}"
    )
