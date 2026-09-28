"""What the engine may ask a source for, and the bookkeeping every source shares.

One method per page kind. Every public read is memoised per process so the
engine can ask twice without paying twice; `fresh=True` bypasses the memo for
the verify pass. `counters.loads` counts memo misses by kind (what the run
asked for), `counters.live` counts real page reads (what the run paid for);
the difference is cache hits. `searches` is the v1 `work.searches` list that
Mission Control renders, one entry per read.

Subclasses implement the `_read_*` twins. `has(kind)` says which the source
can answer at all; the engine builds branches only for kinds the source has.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Awaitable, Callable

from shared.coverage import record_search

KINDS = ("cash", "points", "gowild", "calendar", "rt", "grid", "multi", "routes")


def browser_closed(e: BaseException) -> bool:
    """True when the browser itself went away under a read: Playwright's
    TargetClosedError, or any error that says the page, context or browser
    has been closed. A reader opens a new browser once on it; the run does
    not fail every read that follows in seconds (2026-09-22: 77 of 168)."""
    return type(e).__name__ == "TargetClosedError" or "has been closed" in str(e)


class SourceUnavailable(RuntimeError):
    """A reader that waited out a block and still got no answer. The engine
    stops the search there and reports it as not proved, with the read that
    failed named in the report; nothing retries in a loop."""

    def __init__(self, source: str, why: str) -> None:
        super().__init__(f"{source}: {why}")
        self.source, self.why = source, why


@dataclass
class Counters:
    loads: dict[str, int] = field(default_factory=dict)
    live: dict[str, int] = field(default_factory=dict)
    frontier_requests: int = 0
    windows: int = 0
    blocks: int = 0

    def bump(self, table: str, kind: str, n: int = 1) -> None:
        d = getattr(self, table)
        d[kind] = d.get(kind, 0) + n

    def as_dict(self) -> dict[str, Any]:
        return {"loads": dict(self.loads), "live": dict(self.live), "frontier_requests": self.frontier_requests,
                "windows": self.windows, "blocks": self.blocks}


class BaseSources:
    def __init__(self) -> None:
        self._memo: dict[tuple, Any] = {}
        self.counters = Counters()
        self.searches: list[dict] = []
        self.failed: list[dict] = []           # the subset of searches whose page never read

    def has(self, kind: str) -> bool:
        return False

    def record(self, kind: str, origin: str, dest: str, depart: str, *, ret: str | None = None,
               source: str = "live", found: int = 0, best: dict | None = None, failed: bool = False,
               reason: str | None = None, cached_age_hours: float | None = None, pages: int = 1) -> dict:
        rec = record_search(self.searches, kind, origin, dest, depart, ret=ret, done=not failed,
                            cached_age_hours=cached_age_hours, failed=failed, reason=reason,
                            pages=pages, found=found, best=best)
        rec["source"] = source
        if failed:
            self.failed.append(rec)
        return rec

    async def _memoized(self, key: tuple, fn: Callable[[], Awaitable[Any]], fresh: bool = False) -> Any:
        if not fresh and key in self._memo:
            return self._memo[key]
        self.counters.bump("loads", key[0])
        val = await fn()
        self._memo[key] = val
        return val

    # ------------------------------------------------------------ public reads

    async def cash_oneway(self, o: str, d: str, day: date, fresh: bool = False) -> list[dict]:
        return await self._memoized(("cash", o, d, day), lambda: self._read_cash(o, d, day, fresh), fresh)

    async def cash_roundtrip(self, o: str, d: str, day: date, ret: date, fresh: bool = False) -> list[dict]:
        return await self._memoized(("rt", o, d, day, ret), lambda: self._read_roundtrip(o, d, day, ret, fresh), fresh)

    async def cash_grid(self, o: str, d: str, day: date, ret: date) -> dict[tuple[date, date], float]:
        return await self._memoized(("grid", o, d, day, ret), lambda: self._read_grid(o, d, day, ret))

    async def cash_multicity(self, legs: tuple[tuple[date, str, str], ...], fresh: bool = False) -> list[dict]:
        legs = tuple(legs)
        return await self._memoized(("multi", legs), lambda: self._read_multicity(legs, fresh), fresh)

    async def award_oneway(self, o: str, d: str, day: date, fresh: bool = False) -> list[dict]:
        return await self._memoized(("points", o, d, day), lambda: self._read_award(o, d, day, fresh), fresh)

    async def gowild_calendar(self, o: str, d: str, month: str) -> dict[str, float | str]:
        return await self._memoized(("calendar", o, d, month), lambda: self._read_calendar(o, d, month))

    async def gowild_day(self, o: str, d: str, day: date, fresh: bool = False) -> dict | None:
        return await self._memoized(("gowild", o, d, day), lambda: self._read_gowild_day(o, d, day, fresh), fresh)

    async def frontier_routes(self, origin: str) -> list[str]:
        return await self._memoized(("routes", origin), lambda: self._read_routes(origin))

    async def recheck_awards(self) -> int:
        """Read again the award pages that miss a program their route's other
        pages show. Returns how many pages gained fares; a source with no live
        award reader has nothing to read again."""
        return 0

    async def close(self) -> None:
        return None

    # ------------------------------------------------------------ to implement

    async def _read_cash(self, o: str, d: str, day: date, fresh: bool) -> list[dict]:
        raise NotImplementedError

    async def _read_roundtrip(self, o: str, d: str, day: date, ret: date, fresh: bool) -> list[dict]:
        raise NotImplementedError

    async def _read_grid(self, o: str, d: str, day: date, ret: date) -> dict[tuple[date, date], float]:
        raise NotImplementedError

    async def _read_multicity(self, legs: tuple[tuple[date, str, str], ...], fresh: bool) -> list[dict]:
        raise NotImplementedError

    async def _read_award(self, o: str, d: str, day: date, fresh: bool) -> list[dict]:
        raise NotImplementedError

    async def _read_calendar(self, o: str, d: str, month: str) -> dict[str, float | str]:
        raise NotImplementedError

    async def _read_gowild_day(self, o: str, d: str, day: date, fresh: bool) -> dict | None:
        raise NotImplementedError

    async def _read_routes(self, origin: str) -> list[str]:
        raise NotImplementedError


def best_cash(recs: list[dict]) -> dict | None:
    vals = [float(r["total_cash"]) for r in recs if r.get("total_cash") is not None]
    return {"cash": min(vals)} if vals else None


def best_points(recs: list[dict]) -> dict | None:
    vals = [(int(r["points_cost"]), float(r.get("cash_component") or 0.0)) for r in recs if r.get("points_cost") is not None]
    if not vals:
        return None
    p, f = min(vals)
    return {"points": p, "fees": f}
