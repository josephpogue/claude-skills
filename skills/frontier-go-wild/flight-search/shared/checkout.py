"""Where this code is running from, so every path it uses resolves the same way.

Two layouts carry these files. In the source repo the code sits at
automations/flight-search, beside automations/browser-pilot, and the repo root
holds the pyproject.toml, the result logs and the browser profiles. The
published frontier-go-wild skill ships the same files in its own folder: a
flight-search/ and a browser-pilot/ beside its SKILL.md and pyproject.toml,
with no checkout around them. There everything a run writes goes under
~/.claude/data/frontier-go-wild, never into the skill folder.
"""
from __future__ import annotations

from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parents[1]           # the flight-search folder
PUBLISHED = (CODE_ROOT.parent / "SKILL.md").is_file()     # beside a SKILL.md: the published skill
PROJECT_ROOT = CODE_ROOT.parent if PUBLISHED else CODE_ROOT.parents[1]   # holds pyproject.toml
BROWSER_PILOT = CODE_ROOT.parent / "browser-pilot"        # a sibling in both layouts
PUBLISHED_DATA = Path.home() / ".claude" / "data" / "frontier-go-wild"
