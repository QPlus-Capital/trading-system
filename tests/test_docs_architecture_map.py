"""Guard against a stale architecture map: every module path named in docs/architecture.md
must exist. A file deleted or renamed without updating the map fails CI here."""

import re

from core.paths import REPO_ROOT


def test_architecture_map_paths_exist() -> None:
    doc = (REPO_ROOT / "docs" / "architecture.md").read_text(encoding="utf-8")
    # Backtick-quoted module paths under one of the four packages, e.g. `research/portfolio/risk.py`.
    paths = set(re.findall(r"`((?:core|research|live|monitoring)/[\w/]+\.py)`", doc))
    assert paths, "no module paths parsed from architecture.md -- has the format changed?"
    missing = sorted(p for p in paths if not (REPO_ROOT / p).is_file())
    assert not missing, f"architecture.md references files that no longer exist: {missing}"
