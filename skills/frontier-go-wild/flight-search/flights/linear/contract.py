"""The contract the three linear search skills share.

One input: a list of reads (origin, destination, date) and one set of filters
(max stops, max layover, latest arrival date, cabin). One output: the same
columns from every skill, whatever the site does inside. One filter: a flight
is returned only when it is shown to pass, so a flight whose layovers or
arrival could not be read is dropped and counted, never passed on trust.

Nothing here ranks, reorders or picks. That belongs to the caller.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

CABINS = ("economy", "premium", "business", "first")

# Every flight row carries exactly these keys, in this order.
COLUMNS = (
    "read_index",          # position of the read in the input list, from 0
    "platform",            # google-flights | amex-point-me | frontier-go-wild
    "price_type",          # cash | points | gowild
    "origin",              # airport flown from (a metro code is resolved to its airport)
    "destination",         # airport flown to
    "depart_date",         # YYYY-MM-DD, local at the origin
    "depart_time",         # ISO local clock, with its UTC offset when the zone is known
    "arrive_date",         # YYYY-MM-DD, local at the destination; null when it could not be established
    "arrive_time",         # ISO local clock at the destination; null when it could not be established
    "duration_minutes",
    "stops",
    "routing",             # airports in travel order; [origin, destination] when the site names no stop airports
    "layovers",            # [{airport, airport_name, minutes}], one per stop the site described
    "layovers_known",      # true when every stop has its minutes in `layovers`
    "layover_filter_by",   # measured | platform | null: how the row passed the max layover filter
    "airlines",
    "flight_numbers",      # in travel order; empty when the site did not print them
    "segments",            # [{origin, destination, depart_time, arrive_time, duration_minutes, airline,
                           #   flight_number, aircraft}], one per flight in travel order, clocks local at
                           #   each airport; empty when the site prints no per-flight detail
    "cabin",
    "price_usd",           # cash price; the Go Wild fee; null on an award
    "points",              # award points; null otherwise
    "fees_usd",            # taxes and fees on an award; null when the site printed "Check program"
    "fees_known",
    "program",             # loyalty program pricing the award; null otherwise
    "ticketing",           # single | self_transfer | separate_tickets
    "times_known",         # depart and arrive clocks are both in a known time zone
    "booking_url",
    "source",              # live | saved
    "saved_age_hours",     # age of the saved page; null on a live read
)

# Why a flight was left out, in the order the filters are tried.
DROP_REASONS = ("max_stops", "layover_unknown", "max_layover", "arrival_unknown", "latest_arrival", "cabin")


@dataclass(frozen=True)
class Read:
    index: int
    origin: str
    destination: str
    day: date


@dataclass(frozen=True)
class Filters:
    max_stops: int | None = None
    max_layover_minutes: int | None = None
    latest_arrival_date: date | None = None
    cabin: str = "economy"

    def as_dict(self) -> dict[str, Any]:
        return {"max_stops": self.max_stops, "max_layover_minutes": self.max_layover_minutes,
                "latest_arrival_date": self.latest_arrival_date.isoformat() if self.latest_arrival_date else None,
                "cabin": self.cabin}


@dataclass(frozen=True)
class Request:
    reads: tuple[Read, ...]
    filters: Filters
    max_age_hours: float | None = None      # None: a saved page of any age is reused; 0: every read is live
    saved_only: bool = False                # never open a browser; a read with no saved page fails


@dataclass
class ReadResult:
    """What one read gave back, before the filters."""
    status: str = "read"                    # read | failed | not_reached | not_applicable
    source: str | None = None               # live | saved
    saved_age_hours: float | None = None
    rows: list[dict] = field(default_factory=list)
    note: str | None = None
    # The max layover the site itself applied to this page, confirmed on the page (see drop_reason).
    platform_layover_cap: int | None = None


def _code(v: Any, where: str) -> str:
    s = str(v or "").strip().upper()
    if len(s) != 3 or not s.isalpha():
        raise ValueError(f"{where}: expected a 3-letter airport code, got {v!r}")
    return s


def _day(v: Any, where: str) -> date:
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        raise ValueError(f"{where}: expected a date as YYYY-MM-DD, got {v!r}") from None


def _count(v: Any, where: str) -> int | None:
    if v is None:
        return None
    if isinstance(v, bool) or not isinstance(v, int) or v < 0:
        raise ValueError(f"{where}: expected a whole number of 0 or more, got {v!r}")
    return v


def parse_request(raw: dict[str, Any], *, saved_only: bool = False) -> Request:
    """The input JSON as a Request. Raises ValueError naming the field that is wrong."""
    if not isinstance(raw, dict):
        raise ValueError("input: expected a JSON object with `reads` and `filters`")
    unknown = set(raw) - {"reads", "filters", "max_age_hours"}
    if unknown:
        raise ValueError(f"input: unknown keys {sorted(unknown)}")
    items = raw.get("reads")
    if not isinstance(items, list) or not items:
        raise ValueError("reads: expected a list with at least one read")
    reads = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"reads[{i}]: expected an object with origin, destination and date")
        extra = set(item) - {"origin", "destination", "date"}
        if extra:
            raise ValueError(f"reads[{i}]: unknown keys {sorted(extra)}")
        reads.append(Read(i, _code(item.get("origin"), f"reads[{i}].origin"),
                          _code(item.get("destination"), f"reads[{i}].destination"),
                          _day(item.get("date"), f"reads[{i}].date")))
    f = raw.get("filters") or {}
    if not isinstance(f, dict):
        raise ValueError("filters: expected an object")
    extra = set(f) - {"max_stops", "max_layover_minutes", "latest_arrival_date", "cabin"}
    if extra:
        raise ValueError(f"filters: unknown keys {sorted(extra)}")
    cabin = str(f.get("cabin") or "economy").strip().lower()
    if cabin not in CABINS:
        raise ValueError(f"filters.cabin: expected one of {list(CABINS)}, got {f.get('cabin')!r}")
    latest = f.get("latest_arrival_date")
    filters = Filters(max_stops=_count(f.get("max_stops"), "filters.max_stops"),
                      max_layover_minutes=_count(f.get("max_layover_minutes"), "filters.max_layover_minutes"),
                      latest_arrival_date=_day(latest, "filters.latest_arrival_date") if latest else None,
                      cabin=cabin)
    age = raw.get("max_age_hours")
    if age is not None and (isinstance(age, bool) or not isinstance(age, (int, float)) or age < 0):
        raise ValueError(f"max_age_hours: expected a number of 0 or more, got {age!r}")
    return Request(tuple(reads), filters, None if age is None else float(age), saved_only)


def make_row(**values: Any) -> dict[str, Any]:
    """A flight row with every column, in column order. `read_index` is set by the runner."""
    unknown = set(values) - set(COLUMNS)
    if unknown:
        raise KeyError(f"not a column: {sorted(unknown)}")
    return {c: values.get(c) for c in COLUMNS}


def local_iso(clock: datetime, zone_known: bool) -> str:
    """The clock as the row prints it: with its offset only when the zone is known."""
    return (clock if zone_known else clock.replace(tzinfo=None)).isoformat(timespec="minutes")


def drop_reason(row: dict[str, Any], f: Filters, *, platform_layover_cap: int | None = None) -> str | None:
    """None when the row is shown to pass every filter, else the first filter it fails.

    `platform_layover_cap` is the layover cap the site itself applied to the
    page this row came from, confirmed on the page. A connecting row whose
    layovers the site never printed passes on that, and says so in
    `layover_filter_by`; without it the row is dropped as `layover_unknown`."""
    if f.max_stops is not None and int(row["stops"]) > f.max_stops:
        return "max_stops"
    row["layover_filter_by"] = None
    if f.max_layover_minutes is not None and int(row["stops"]) > 0:
        if row["layovers_known"]:
            if any(int(l["minutes"]) > f.max_layover_minutes for l in row["layovers"]):
                return "max_layover"
            row["layover_filter_by"] = "measured"
        elif platform_layover_cap is not None and platform_layover_cap <= f.max_layover_minutes:
            row["layover_filter_by"] = "platform"
        else:
            return "layover_unknown"
    if f.latest_arrival_date is not None:
        if not row["arrive_date"]:
            return "arrival_unknown"
        if row["arrive_date"] > f.latest_arrival_date.isoformat():
            return "latest_arrival"
    if row["cabin"] != f.cabin:
        return "cabin"
    return None
