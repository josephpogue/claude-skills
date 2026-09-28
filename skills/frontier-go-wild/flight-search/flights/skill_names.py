"""The flight-search skills' names, and the names they had before.

FORMER NAMES LIVE HERE AND NOWHERE ELSE. Until 2026-09-27 the four skills were
called `<name>-v2`. Result files saved before the rename still carry the old
name, in their `"skill"` field and in their file name
(`.flight-search-logs/linear/<skill>-<run id>.json`), and so do their runlog
folders. Every reader passes a name through `current()` before looking it up,
so an old file reads the same as a new one. Nothing writes a former name.
"""
from __future__ import annotations

LINEAR_SKILLS = ("flight-cash-search", "amex-points-search", "frontier-go-wild")
PLANNER = "flight-trip-planner"

# Former name -> current name.
FORMER_NAMES = {
    "flight-cash-search-v2": "flight-cash-search",
    "amex-points-search-v2": "amex-points-search",
    "frontier-go-wild-v2": "frontier-go-wild",
    "flight-trip-planner-v2": "flight-trip-planner",
}


def current(name):
    """The current name for `name`, which may be a former one. Anything else,
    a name this module does not know or a value that is not text, comes back as it was."""
    return FORMER_NAMES.get(name, name) if isinstance(name, str) else name


def former(name: str) -> list[str]:
    """Every former name of the skill now called `name`."""
    return [old for old, new in FORMER_NAMES.items() if new == name]
