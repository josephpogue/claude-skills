"""Tickets: the one shape every scraped flight becomes, and the Go Wild builder.

Split out of flights/trip.py so a Go Wild read needs nothing from the trip
planner (trip.py re-exports every name here). Arrival clocks are recomputed as
departure plus total duration in the destination zone, as trip.py explains.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")
_ET, _CT, _MT, _PT = "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"
TZ: dict[str, str] = {
    # Eastern
    "ATL": _ET, "MCO": _ET, "PHL": _ET, "CLE": _ET, "CVG": _ET, "DTW": _ET, "TPA": _ET, "RSW": _ET,
    "MIA": _ET, "FLL": _ET, "JFK": _ET, "LGA": _ET, "EWR": _ET, "BOS": _ET, "BWI": _ET, "IAD": _ET,
    "DCA": _ET, "RDU": _ET, "CLT": _ET, "JAX": _ET, "PBI": _ET, "BUF": _ET, "PIT": _ET, "CMH": _ET,
    "IND": _ET, "BDL": _ET, "ISP": _ET, "RIC": _ET, "ORF": _ET, "CHS": _ET, "MYR": _ET, "SAV": _ET,
    "SJU": _ET, "YYZ": _ET, "YUL": _ET, "SYR": _ET, "SRQ": _ET, "TYS": _ET, "GRR": "America/Detroit",
    # Central
    "DFW": _CT, "ORD": _CT, "MDW": _CT, "IAH": _CT, "HOU": _CT, "MSP": _CT, "AUS": _CT, "SAT": _CT,
    "MSY": _CT, "STL": _CT, "MCI": _CT, "MKE": _CT, "BNA": _CT, "MEM": _CT, "OKC": _CT, "OMA": _CT,
    "PNS": _CT, "CID": _CT, "DSM": _CT, "MSN": _CT, "FSD": _CT, "XNA": _CT, "CRP": _CT,
    # Mountain and Arizona
    "DEN": _MT, "SLC": _MT, "ABQ": _MT, "PHX": "America/Phoenix", "ELP": _MT, "TUS": "America/Phoenix",
    "BOI": "America/Boise",
    # Pacific
    "LAX": _PT, "SFO": _PT, "LAS": _PT, "SAN": _PT, "SJC": _PT, "SEA": _PT, "PDX": _PT, "OAK": _PT,
    "ONT": _PT, "SNA": _PT, "SMF": _PT, "RNO": _PT, "BUR": _PT, "YVR": _PT, "GEG": _PT,
    # Caribbean, Central America and Mexico (Frontier's leisure network)
    "BQN": "America/Puerto_Rico", "PSE": "America/Puerto_Rico", "MBJ": "America/Jamaica",
    "PUJ": "America/Santo_Domingo", "SDQ": "America/Santo_Domingo", "AUA": "America/Aruba",
    "SXM": "America/Lower_Princes", "NAS": "America/Nassau", "PLS": "America/Grand_Turk",
    "SJO": "America/Costa_Rica", "GUA": "America/Guatemala", "SAL": "America/El_Salvador",
    "SAP": "America/Tegucigalpa",
    # Other
    "HNL": "Pacific/Honolulu", "ANC": "America/Anchorage",
    "OKA": "Asia/Tokyo", "NRT": "Asia/Tokyo", "HND": "Asia/Tokyo", "KIX": "Asia/Tokyo", "NGO": "Asia/Tokyo",
    "FUK": "Asia/Tokyo", "ICN": "Asia/Seoul", "TPE": "Asia/Taipei", "HKG": "Asia/Hong_Kong",
    "MNL": "Asia/Manila", "SIN": "Asia/Singapore", "BKK": "Asia/Bangkok", "PVG": "Asia/Shanghai",
    "PEK": "Asia/Shanghai", "SYD": "Australia/Sydney", "LHR": "Europe/London", "CDG": "Europe/Paris",
    "AMS": "Europe/Amsterdam", "FRA": "Europe/Berlin", "MUC": "Europe/Berlin", "IST": "Europe/Istanbul",
    "DOH": "Asia/Qatar", "DXB": "Asia/Dubai", "MEX": "America/Mexico_City", "CUN": "America/Cancun",
}


def tz_of(code: str) -> ZoneInfo | None:
    name = TZ.get(code)
    return ZoneInfo(name) if name else None



def _date(v: Any) -> date | None:
    if v is None or v == "":
        return None
    return v if isinstance(v, date) else date.fromisoformat(str(v))


@dataclass(frozen=True)
class Ticket:
    kind: str                       # cash | points | gowild | package
    origin: str
    dest: str
    depart_date: date
    dep: datetime                   # aware
    arr: datetime                   # aware, destination zone when known
    cost: float                     # cash-equivalent at the valuation
    cash: float
    points: int
    fees: float
    duration: int
    stops: int
    airlines: tuple[str, ...]
    routing: tuple[str, ...]
    detail: str
    dep_known: bool                 # departure clock is in a known zone
    arr_known: bool                 # arrival clock recomputed in a known zone
    source: dict | None = field(default=None, compare=False, hash=False)
    # point.me prints "Check program" where some cards' fees go: `fees` is then
    # 0.0 and `cost` is the points alone, a lower bound on the real price.
    fees_known: bool = True
    # A connecting award whose detail panel was not read has no layovers to
    # check, so the layover cap could not be applied to it.
    layovers_known: bool = True


def _localize(naive: datetime, code: str) -> tuple[datetime, bool]:
    z = tz_of(code)
    if z is None:
        return naive.replace(tzinfo=UTC), False
    return naive.replace(tzinfo=z), True


def _passes(stops: int, layovers: list[dict] | None, cons: dict[str, Any]) -> bool:
    max_stops = cons.get("max_stops_each_way")
    if max_stops is not None and stops > int(max_stops):
        return False
    max_lay = cons.get("max_layover_minutes")
    if max_lay is not None:
        for lay in layovers or []:
            m = lay.get("minutes")
            if m is not None and int(m) > int(max_lay):
                return False
    return True


def gowild_tickets(day: dict, cons: dict[str, Any]) -> list[Ticket]:
    out: list[Ticket] = []
    ddate = _date(day.get("date"))
    if ddate is None:
        return out
    for r in day.get("routes") or []:
        legs = r.get("legs") or []
        if not legs or r.get("goWildFee") is None:
            continue
        stops = int(r.get("stops", len(legs) - 1))
        if not _passes(stops, r.get("layovers"), cons):
            continue
        o, d = legs[0]["from"], legs[-1]["to"]
        hh, mm = (int(x) for x in str(legs[0]["dep"]).split(":")[:2])
        dep, known_o = _localize(datetime.combine(ddate, time(hh, mm)), o)
        dur = int(r.get("totalMinutes") or 0)
        zd = tz_of(d)
        arr = (dep + timedelta(minutes=dur)).astimezone(zd) if zd else dep + timedelta(minutes=dur)
        fee = float(r["goWildFee"])
        out.append(Ticket(kind="gowild", origin=o, dest=d, depart_date=ddate, dep=dep, arr=arr,
                          cost=fee, cash=fee, points=0, fees=0.0, duration=dur, stops=stops,
                          airlines=("Frontier",), routing=(o, *[l["to"] for l in legs[:-1]], d),
                          detail="Frontier Go Wild", dep_known=known_o, arr_known=known_o and zd is not None, source=r))
    return out
