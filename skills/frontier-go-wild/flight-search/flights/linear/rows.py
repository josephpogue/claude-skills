"""What the three adapters share: the stand-in trip the planner's readers want, and ticket to row.

The planner's readers (`flights/sources/google.py`, `pointme.py`, `frontier.py`) were built
for the planner and take its `Trip`. A linear run has no trip, only a cabin and
a cache age, so `reader_trip` carries just the fields those readers read.
"""
from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from flights.linear.contract import ReadResult, Request, local_iso, make_row
from flights.sources.base import BaseSources
from flights.tickets import Ticket

NO_SAVED_PAGE = "no saved page (run without --saved-only to read it live)"


def no_saved_page_note(max_age_hours: float | None) -> str:
    """Why a --saved-only read opened nothing. With an age cap the page may be
    there and too old, so the note names the cap instead of saying there is none."""
    if max_age_hours is None:
        return NO_SAVED_PAGE
    return f"no saved page within max_age_hours {max_age_hours:g} (run without --saved-only to read it live)"


def reader_trip(request: Request, constraints: dict[str, Any] | None = None) -> SimpleNamespace:
    """The fields of `Trip` a planner reader reads. `constraints` are the page-side
    filters a reader may set on the site itself (Google's stops and layover)."""
    query = SimpleNamespace(cabins=[request.filters.cabin], travelers={"adults": 1},
                            cache_ttl_hours=request.max_age_hours, use_cache=True)
    leg = SimpleNamespace(origins=[], destinations=[], constraints=dict(constraints or {}))
    return SimpleNamespace(query=query, legs=[leg])


async def no_sleep(_seconds: float) -> None:
    """The pace of a saved-only run, which loads nothing."""
    return None


def outcome(sink: BaseSources, before: int, max_age_hours: float | None = None) -> ReadResult:
    """A ReadResult whose status, source and age come from what the reader
    recorded since `before` (the length of `sink.searches` before the read).
    A page read twice records twice; the last entry is the one that was served.
    `max_age_hours` is the request's, for the note of a read with no usable saved page."""
    entries = sink.searches[before:]
    if not entries:
        return ReadResult(status="failed", note="the reader recorded nothing for this read")
    last = entries[-1]
    res = ReadResult(source="saved" if last["source"] == "cache" else "live",
                     saved_age_hours=last["cache_age_hours"], note=last.get("reason"))
    if last["failed"]:
        res.status = "failed"
        if NO_SAVED_PAGE in (res.note or ""):
            res.source = None       # --saved-only opened nothing, so there is no live read to name
            res.note = no_saved_page_note(max_age_hours)    # one wording from all three, no reader's prefix
    return res


def ticket_row(t: Ticket, *, platform: str, cabin: str, layovers: list[dict], layovers_known: bool,
               source: str | None, saved_age_hours: float | None, flight_numbers: list[str] | None = None,
               program: str | None = None, ticketing: str = "single", booking_url: str | None = None,
               stated_arrival: datetime | None = None, segments: list[dict] | None = None,
               airlines: list[str] | None = None) -> dict[str, Any]:
    """One flight row from a planner `Ticket` (its clocks are the planner's: arrival
    is departure plus duration in the destination's zone when both zones are
    known). `stated_arrival` is a local arrival clock the site itself printed
    with its date; it is used only when the zones are not known. `airlines`
    replaces the ticket's own list when the adapter has names for it (see
    `flights/linear/airlines.py`)."""
    arrive = t.arr if t.arr_known else stated_arrival
    points = t.kind == "points"
    depart_time = local_iso(t.dep, t.dep_known)
    arrive_time = local_iso(arrive, t.arr_known) if arrive else None
    names = list(t.airlines if airlines is None else airlines)
    if not segments and t.stops == 0:
        # A nonstop is one flight, so the row itself is its one segment.
        segments = [{"origin": t.origin, "destination": t.dest, "depart_time": depart_time,
                     "arrive_time": arrive_time, "duration_minutes": t.duration,
                     "airline": names[0] if len(names) == 1 else None}]
    return make_row(
        platform=platform, price_type=t.kind, origin=t.origin, destination=t.dest,
        depart_date=t.depart_date.isoformat(), depart_time=depart_time,
        arrive_date=arrive.date().isoformat() if arrive else None, arrive_time=arrive_time,
        duration_minutes=t.duration, stops=t.stops, routing=list(t.routing),
        layovers=[{"airport": l.get("airport"), "airport_name": l.get("airport_name"), "minutes": l.get("minutes")}
                  for l in layovers],
        layovers_known=layovers_known, airlines=names, flight_numbers=list(flight_numbers or []),
        segments=[segment(**s) for s in segments or []],
        cabin=cabin, price_usd=None if points else t.cash, points=t.points if points else None,
        fees_usd=(t.fees if t.fees_known else None) if points else None, fees_known=t.fees_known,
        program=program, ticketing=ticketing, times_known=t.dep_known and t.arr_known,
        booking_url=booking_url, source=source, saved_age_hours=saved_age_hours)


SEGMENT_KEYS = ("origin", "destination", "depart_time", "arrive_time", "duration_minutes", "airline",
                "flight_number", "aircraft")


def segment(**values: Any) -> dict[str, Any]:
    """One flight of a row's `segments`, every key present, in key order."""
    unknown = set(values) - set(SEGMENT_KEYS)
    if unknown:
        raise KeyError(f"not a segment key: {sorted(unknown)}")
    return {k: values.get(k) for k in SEGMENT_KEYS}


def layovers_complete(stops: int, layovers: list[dict]) -> bool:
    """True when every stop has its minutes."""
    return stops == 0 or (len(layovers) >= stops and all(l.get("minutes") is not None for l in layovers))
