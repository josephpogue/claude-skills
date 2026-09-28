"""Per-query search cache.

Caches the parsed itinerary list for each (kind, origin, dest, depart, return,
cabin, adults) tuple. Reading the cache is ON by default (`use_cache: true`), so
rerunning a wide sweep reuses every route it already priced and searches live
only for the origins, destinations and dates it has never seen. Results are
always WRITTEN back, whether or not they were read, so a run cut short leaves
the work it did behind for the next one. Pass `use_cache: false` to force every
search live.

Entries never expire by default: a cached answer is reused until that route is
searched live again. A query can still set `cache_ttl_hours` to opt into
expiry. Per-route targeting is inherent: a
route's file is overwritten only when that route is fetched, so nothing
invalidates a route the user did not search. There is no global invalidation
marker.

The cache lives outside any checkout, so every copy of the repo (main, prod,
worktrees) reads and writes the same saved searches.

The file in CACHE_DIR is the latest copy of a page. Every write that follows a
live read also keeps a copy nobody overwrites, in
HISTORY_DIR/<key without .json>/<UTC time>.json, so a route's price history
survives the next read of it (see `write_history`)."""
from __future__ import annotations
import contextlib
import json
import os
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CACHE_DIR = Path.home() / ".claude" / "data" / "flight-search" / "cache"
HISTORY_DIR = Path.home() / ".claude" / "data" / "flight-search" / "history"


def make_key(kind: str, origin: str, dest: str, depart: str, ret: Optional[str], cabin: str, adults: int) -> str:
    """Stable filename key for cache lookup."""
    safe_cabin = cabin.replace(" ", "-").replace("/", "_").lower()
    parts = [kind, origin, dest, depart, ret or "oneway", safe_cabin, str(adults)]
    return "_".join(parts) + ".json"


def get(key: str, max_age_seconds: Optional[int] = None,
        contract: Optional[str] = None) -> Optional[list[dict]]:
    """Return cached itineraries, or None if missing or older than
    `max_age_seconds`. `None` means the entry never expires.

    `contract` names what the reader needs the bucket to promise, as written by
    `put(..., contract=...)`. An entry written under a different contract, or
    none, is a miss. It lives on the bucket and not on its records because an
    empty list is a real answer ("no flights found") that must still be
    servable. Without `contract` every entry is served, as before.

    Reading the cache is opt-in: callers only call this when the user passed
    `use_cache: true`. A fresh-by-default run skips the read entirely and
    fetches live."""
    path = CACHE_DIR / key
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    cached_at = data.get("cached_at_epoch", 0)
    if max_age_seconds is not None and time.time() - cached_at > max_age_seconds:
        return None
    if contract is not None and data.get("contract") != contract:
        return None
    return data.get("itineraries", [])


BUCKET_KEYS = ("cached_at_epoch", "cached_at_iso", "itineraries", "contract")


def put(key: str, itineraries: list[dict], contract: Optional[str] = None,
        marks: Optional[dict] = None, history: bool = True) -> None:
    """Store itineraries to cache, under `contract` when the writer makes one
    (see `get`). `marks` are facts about how the bucket was read, kept beside
    the itineraries and read back with `mark`.

    Every caller writes right after a live read, so the same text is also kept
    in the price history. `history=False` is for a rewrite of a page already
    read, which is not a new read."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / key
    payload = {
        "cached_at_epoch": time.time(),
        "cached_at_iso": datetime.now().isoformat(),
        "itineraries": itineraries,
    }
    if contract is not None:
        payload["contract"] = contract
    for name, value in (marks or {}).items():
        if name not in BUCKET_KEYS:
            payload[name] = value
    text = json.dumps(payload, default=str)
    path.write_text(text)
    if history:
        write_history(HISTORY_DIR, key, text)


def write_history(root: Path, key: str, text: str, now: Optional[datetime] = None) -> Optional[Path]:
    """Keep `text` as root/<key without .json>/<UTC time>.json and return its path.

    A copy is never overwritten: a name already taken gets -1, -2 and so on.
    The text goes to a temp file in the same folder first and is then linked
    under its name, which fails instead of replacing a file that is there, so
    a reader never sees half a copy. A failure here must never fail the read
    that produced the page: it is logged to stderr and None comes back."""
    try:
        name = key[:-len(".json")] if key.endswith(".json") else key
        folder = Path(root) / name
        folder.mkdir(parents=True, exist_ok=True)
        stamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        fd, tmp = tempfile.mkstemp(dir=folder, prefix=".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                f.write(text)
            n = 0
            while True:
                target = folder / (f"{stamp}.json" if n == 0 else f"{stamp}-{n}.json")
                try:
                    os.link(tmp, target)
                    return target
                except FileExistsError:
                    n += 1
        finally:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
    except Exception as e:  # noqa: BLE001
        print(f"[history] no history copy of {key}: {type(e).__name__}: {e}", file=sys.stderr)
        return None


def mark(key: str, name: str):
    """A mark `put` stored on the bucket, or None."""
    path = CACHE_DIR / key
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text()).get(name)
    except (json.JSONDecodeError, OSError):
        return None


def age_hours(key: str) -> Optional[float]:
    """Age of a cached entry in hours, or None if missing."""
    path = CACHE_DIR / key
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    return (time.time() - data.get("cached_at_epoch", 0)) / 3600


def update_in_bucket(key: str, predicate, new_entry: dict) -> bool:
    """Find the first entry in the cached bucket where predicate(entry) is
    True, replace it with new_entry, and write the bucket back. Returns True
    if an entry was updated, False otherwise (key absent or no match).

    Used to persist enrichment-stage data (per-segment detail, fixed-up
    airlines/routing) back to cache so future replays don't re-do enrichment.
    Enrichment only adds to an entry, so the bucket keeps its contract and marks."""
    path = CACHE_DIR / key
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    entries = data.get("itineraries", [])
    for i, entry in enumerate(entries):
        if predicate(entry):
            entries[i] = new_entry
            put(key, entries, contract=data.get("contract"),
                marks={k: v for k, v in data.items() if k not in BUCKET_KEYS}, history=False)
            return True
    return False
