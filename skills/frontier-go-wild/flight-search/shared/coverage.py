"""Per-route search coverage: what was actually looked at, route by route.

The sweeps already publish one aggregate coverage record ("28 of 28 searches
done"). On a query with one route that is enough. On a query with fourteen
destinations it is not: an aggregate cannot say that Denver to San Diego was
searched on two dates and Denver to Boston on twenty-three, so an empty points
list for one of them is indistinguishable from an empty points list for the
other, and neither can be checked.

This module owns the per-route record and the one sentence that describes it.
Nothing else formats coverage, so the report and the dashboard cannot drift
into describing the same run two different ways.

A cached answer is called out on purpose. It read no page, so a reader who is
told only "searched" has no way to tell a fresh look from a replay of a result
that is days old, and that is exactly the doubt this is here to remove.
"""
from __future__ import annotations

from typing import Any

# A cache entry older than this is worth naming in the sentence rather than
# just counting: within a day, "from cache" is a detail; at four days it is the
# reason a reader should consider rerunning.
STALE_CACHE_HOURS = 24


def blank(route: str) -> dict[str, Any]:
    """A fresh per-route record. `route` is "ORIGIN-DEST"."""
    return {
        "route": route,
        "searches_total": 0,
        "searches_done": 0,
        "from_cache": 0,
        "cache_age_hours": None,   # the OLDEST cache entry used, in hours
        "failed": 0,
        "pages_read": 0,
        "dates": [],
        "found": 0,
    }


def record(
    by_route: dict[str, dict[str, Any]],
    origin: str,
    dest: str,
    depart: str,
    *,
    done: bool = False,
    cached_age_hours: float | None = None,
    failed: bool = False,
    pages: int = 0,
    found: int = 0,
) -> None:
    """Fold one search's outcome into its route's record.

    Counted once per search, whatever produced it. `cached_age_hours` is set
    only when the search was answered from cache; a live search leaves it None
    and contributes a page instead.
    """
    key = f"{origin}-{dest}"
    rec = by_route.setdefault(key, blank(key))
    rec["searches_total"] += 1
    if done:
        rec["searches_done"] += 1
    if failed:
        rec["failed"] += 1
    if cached_age_hours is not None:
        rec["from_cache"] += 1
        prior = rec["cache_age_hours"]
        rec["cache_age_hours"] = (cached_age_hours if prior is None
                                  else max(prior, cached_age_hours))
    rec["pages_read"] += pages
    rec["found"] += found
    if depart and depart not in rec["dates"]:
        rec["dates"].append(depart)
        rec["dates"].sort()


def record_search(
    searches: list[dict[str, Any]],
    kind: str,
    origin: str,
    dest: str,
    depart: str,
    *,
    ret: str | None = None,
    done: bool = False,
    cached_age_hours: float | None = None,
    failed: bool = False,
    reason: str | None = None,
    pages: int = 0,
    found: int = 0,
    best: dict[str, Any] | None = None,
    dropped: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Append one search to the run's work list and return the entry.

    Called beside every `record()` call, with the same outcome values, so the
    per-route counts and the per-search list cannot disagree. The entry shape
    is what Mission Control's "Show the work" section reads: keep the keys and
    their order as they are.

    `source` makes the same split `record()` makes. A cache age means the
    answer was replayed; a search that finished or failed went to the site;
    anything else was asked for and never run. `leg` is always None here, and
    the trip planner fills it in on multi-city queries. The returned dict is
    the one in the list, so a caller that filters after the sweep can still
    set `best` and add to `dropped`."""
    if cached_age_hours is not None:
        source = "cache"
    elif done or failed:
        source = "live"
    else:
        source = "not_reached"
    entry: dict[str, Any] = {
        "kind": kind,
        "leg": None,
        "origin": origin,
        "dest": dest,
        "depart": depart,
        "return": ret,
        "source": source,
        "cache_age_hours": (round(cached_age_hours, 1)
                            if cached_age_hours is not None else None),
        "failed": bool(failed),
        "reason": reason,
        "pages": pages,
        "found": found,
        "best": best,
        "dropped": dict(dropped or {}),
    }
    searches.append(entry)
    return entry


def best_cash(records: list[dict[str, Any]]) -> dict[str, float] | None:
    """The cheapest fare among these cash itinerary dicts, as a work-list `best`."""
    prices = [r["total_cash"] for r in records if r.get("total_cash") is not None]
    return {"cash": min(prices)} if prices else None


def best_points(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The cheapest award among these itinerary dicts, as a work-list `best`:
    fewest points, and the lower fees when two tie."""
    offers = [(r["points_cost"], r.get("cash_component") or 0.0)
              for r in records if r.get("points_cost") is not None]
    if not offers:
        return None
    points, fees = min(offers)
    return {"points": points, "fees": fees}


def _dates_clause(rec: dict[str, Any]) -> str:
    dates = rec.get("dates") or []
    if not dates:
        return "no dates"
    if len(dates) == 1:
        return f"the one date {dates[0]}"
    return f"{len(dates)} dates, {dates[0]} to {dates[-1]}"


def _cache_clause(rec: dict[str, Any]) -> str:
    """How much of this route came from cache, and how old the oldest was."""
    used = rec.get("from_cache") or 0
    if not used:
        return ""
    age = rec.get("cache_age_hours")
    total = rec.get("searches_done") or used
    how_many = "all" if used >= total else f"{used} of {total}"
    if age is None:
        return f", {how_many} answered from cache"
    if age >= STALE_CACHE_HOURS:
        return (f", {how_many} answered from a cache up to "
                f"{round(age)} hours old")
    return f", {how_many} answered from a cache under a day old"


def sentence(rec: dict[str, Any] | None, kind: str, noun: str) -> str:
    """One plain sentence naming what this route's `kind` search covered.

    Written so it can be read on its own, without the table above it: a card in
    the dashboard shows only this line, and it has to answer "was this actually
    searched" by itself.
    """
    if not rec or not rec.get("searches_total"):
        return (f"no {kind} search ran for this route, so this says nothing "
                f"about {noun}.")

    total = rec["searches_total"]
    done = rec.get("searches_done") or 0
    failed = rec.get("failed") or 0

    if failed >= total:
        return (f"all {total} {kind} searches for this route failed, so "
                f"nothing was searched and this says nothing about {noun}.")

    if not done:
        # Asked for, never answered: the sweep stopped, the login was refused,
        # or the budget ran out before this route came up. Reads like the
        # never-searched case on purpose, because that is what it is.
        return (f"none of the {total} {kind} searches for this route finished, "
                f"so this says nothing about {noun}.")

    covered = f"searched {_dates_clause(rec)}{_cache_clause(rec)}"

    if done < total:
        return (f"{covered}, but only {done} of {total} searches finished, so "
                f"this covers part of what you asked for.")
    if failed:
        return (f"{covered}, with {failed} of {total} searches failing, so "
                f"this covers part of what you asked for.")
    if rec.get("found"):
        return f"{covered}, and found {rec['found']} {noun} options."
    return f"{covered}, and found no {noun}."


def summarize(by_route: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Roll the per-route records back up, so the aggregate the sweeps already
    publish and this never disagree about the same run."""
    routes = list(by_route.values())
    return {
        "searches_total": sum(r["searches_total"] for r in routes),
        "searches_done": sum(r["searches_done"] for r in routes),
        "from_cache": sum(r["from_cache"] for r in routes),
        "failed": sum(r["failed"] for r in routes),
        "routes": len(routes),
    }
