"""Where browser profiles live, and the identity a page is opened with.

Split out of shared/browser.py so the browser-pilot daemon (session.py) can
import it without the launchers, which the published frontier-go-wild skill
does not ship. shared/browser.py re-exports every name here.
"""
from __future__ import annotations

import os
from pathlib import Path

from shared.checkout import PROJECT_ROOT, PUBLISHED, PUBLISHED_DATA

REPO_ROOT = PROJECT_ROOT
# A checkout keeps its profiles in it; the published skill keeps them out of its own folder.
PROFILES_DIR = PUBLISHED_DATA / "browser-profiles" if PUBLISHED else REPO_ROOT / ".browser-profiles"


def _main_checkout(root: Path) -> Path | None:
    """The main checkout when `root` is a linked worktree (its `.git` is a file
    reading `gitdir: <main>/.git/worktrees/<name>`), else None."""
    try:
        text = (root / ".git").read_text().strip()
    except (OSError, UnicodeDecodeError):
        return None
    if not text.startswith("gitdir:"):
        return None
    gitdir = Path(text.split(":", 1)[1].strip())
    main = (gitdir if gitdir.is_absolute() else root / gitdir).resolve().parent.parent.parent
    return main if (main / ".git").is_dir() else None


def profile_dir(name: str) -> Path:
    """Where the persistent profile `name` lives. A linked worktree of the
    source repo has no profiles of its own, so a profile it never created is
    the main checkout's: that is where the logged-in sessions are. On
    2026-09-17 a worktree run opened a fresh profile, logged in from scratch
    and hit a reCAPTCHA while the main checkout's session was alive. The
    published skill has no checkout, so it only ever uses its own folder.
    BROWSER_PROFILES_DIR overrides all of it."""
    env = os.environ.get("BROWSER_PROFILES_DIR")
    if env:
        return Path(env).expanduser() / name
    local = PROFILES_DIR / name
    main = None if PUBLISHED else _main_checkout(REPO_ROOT)
    if main is not None and not local.exists() and (main / ".browser-profiles" / name).exists():
        return main / ".browser-profiles" / name
    return local


UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
)
VIEWPORT = {"width": 1440, "height": 900}
LOCALE = "en-US"
TIMEZONE = "America/Los_Angeles"
