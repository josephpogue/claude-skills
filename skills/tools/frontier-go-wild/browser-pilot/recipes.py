"""Per-site recipe store: structured site knowledge the agent updates and the
deterministic engines consume."""
from __future__ import annotations
import json
import os
from pathlib import Path

REQUIRED_KEYS = {"site", "login", "signals", "selectors", "gotchas", "needs_human", "last_verified"}


class RecipeError(ValueError):
    pass


def validate(recipe: dict) -> None:
    missing = REQUIRED_KEYS - set(recipe)
    if missing:
        raise RecipeError(f"recipe missing required keys: {sorted(missing)}")


def save(recipe: dict, path: str | Path) -> None:
    validate(recipe)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(recipe, indent=2, sort_keys=True) + "\n")
    os.replace(tmp, path)


def load(path: str | Path) -> dict:
    recipe = json.loads(Path(path).read_text())
    validate(recipe)
    return recipe
