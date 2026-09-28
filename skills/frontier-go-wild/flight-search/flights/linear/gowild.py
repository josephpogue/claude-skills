"""Frontier Go Wild: one read is one day page. This skill never opens the
month calendar or a route page; which days to read is the caller's job, set
in the input `reads` list.

Frontier prints each leg's own clock as HH:MM with no date, and the layover
between two legs only as minutes, so a leg's `segments` entry is worked out,
not read: `_chain` walks the legs from the ticket's own departure, placing
each landing at the first moment its airport's clock reads the printed `arr`,
then each next leg's departure that many layover minutes later. It trusts
none of that until the last landing it builds lands on the ticket's own
arrival (`gowild_tickets`' independent totalMinutes) to the instant; short of
that, or an airport with no known zone, every leg in the row falls back to
its origin, destination and flight number with the clocks left null.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from flights.linear.contract import ReadResult, Request, local_iso
from flights.linear.rows import NO_SAVED_PAGE, no_sleep, outcome, reader_trip, ticket_row
from flights.linear.runner import Adapter
from flights.sources.base import BaseSources
from flights.sources.frontier import DEEP_LINK, FrontierReader
from flights.tickets import Ticket, gowild_tickets, tz_of

NOT_ECONOMY = "Go Wild sells economy seats only"


def _hhmm(clock: str) -> tuple[int, int]:
    h, m = clock.split(":")
    return int(h), int(m)


def _next_local(after: datetime, zone, hh: int, mm: int) -> datetime:
    """The first instant strictly after `after` whose clock in `zone` reads hh:mm."""
    candidate = after.astimezone(zone).replace(hour=hh, minute=mm, second=0, microsecond=0)
    return candidate if candidate > after else candidate + timedelta(days=1)


def _chain(t: Ticket, r: dict) -> list[dict] | None:
    """Every leg's departure and landing, aware and local to its own airport,
    or None when the chain cannot be proven (see the module docstring)."""
    if not t.dep_known:
        return None
    legs, layovers = r.get("legs") or [], r.get("layovers") or []
    dep, out = t.dep, []
    for i, leg in enumerate(legs):
        zone = tz_of(leg["to"])
        if zone is None:
            return None
        arr = _next_local(dep, zone, *_hhmm(leg["arr"]))
        out.append({"dep": dep, "arr": arr})
        if i < len(legs) - 1:
            nxt = arr + timedelta(minutes=int(layovers[i]["minutes"]))
            if (nxt.astimezone(zone).hour, nxt.astimezone(zone).minute) != _hhmm(legs[i + 1]["dep"]):
                return None      # a DST change inside the layover, or the page's own numbers disagree
            dep = nxt
    return out if out[-1]["arr"] == t.arr else None


def _segments(t: Ticket, r: dict) -> list[dict]:
    """One entry per leg in travel order. The clocks are filled only when
    `_chain` proves the whole route; a leg still carries its airports, airline
    and flight number when they are not."""
    legs, chain = r.get("legs") or [], _chain(t, r)
    out = []
    for i, leg in enumerate(legs):
        seg = {"origin": leg["from"], "destination": leg["to"], "airline": "Frontier",
              "flight_number": leg.get("flight") or None}
        if chain is not None:
            dep, arr = chain[i]["dep"], chain[i]["arr"]
            seg.update(depart_time=local_iso(dep, True), arrive_time=local_iso(arr, True),
                      duration_minutes=round((arr - dep).total_seconds() / 60))
        out.append(seg)
    return out


async def _saved_only_ctl(profile: str, verb: str, *args: str, timeout: float = 90) -> dict:
    """--saved-only's ctl: `serve` and `stop` are bookkeeping FrontierReader
    does on every call and cost nothing to answer; every other verb is a real
    page load, refused so a cache miss fails instead of opening a browser."""
    if verb in ("serve", "stop"):
        return {"ok": True}
    return {"ok": False, "error": NO_SAVED_PAGE}


class GoWildAdapter(Adapter):
    skill = "frontier-go-wild"
    platform = "frontier-go-wild"
    price_type = "gowild"

    def __init__(self, request: Request, log) -> None:
        super().__init__(request, log)
        self.sink = BaseSources()
        trip = reader_trip(request)
        kwargs = {"ctl": _saved_only_ctl, "sleep": no_sleep} if request.saved_only else {}
        self.reader = FrontierReader(trip, self.sink, log=log, **kwargs)

    @classmethod
    def goes_live(cls, request: Request) -> bool:
        # Any other cabin makes every read not_applicable, and no browser opens.
        return not request.saved_only and request.filters.cabin == "economy"

    async def read(self, read) -> ReadResult:
        if self.request.filters.cabin != "economy":
            return ReadResult(status="not_applicable", note=NOT_ECONOMY)
        before = len(self.sink.searches)
        day = await self.reader.day(read.origin, read.destination, read.day)
        res = outcome(self.sink, before, self.request.max_age_hours)
        if day is None or day.get("unfetched"):
            return res       # already recorded as failed; no rows to build from
        url = DEEP_LINK.format(o=read.origin, d=read.destination, day=read.day.isoformat())
        res.rows = [
            ticket_row(t, platform=self.platform, cabin="economy", layovers=t.source.get("layovers") or [],
                      layovers_known=True, source=res.source, saved_age_hours=res.saved_age_hours,
                      flight_numbers=[l["flight"] for l in t.source.get("legs", []) if l.get("flight")],
                      ticketing="single", booking_url=url, segments=_segments(t, t.source))
            for t in gowild_tickets(day, {})       # {}: the linear filter applies the caps, not the ticket builder
        ]
        if not res.rows:
            res.note = day.get("note")       # e.g. "pill '--': no Go Wild seats", a real answer with nothing to show
        return res

    async def close(self) -> None:
        await self.reader.close()
