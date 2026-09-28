"""Frontier Go Wild for the planner: page parsers here, the browser reader below (Task 12).

Row and pill parsing is a copy of the v1 frontier-go-wild skill's gw_driver.py
(2026-08) so both read the booking grid the same way. New here: the Low Fare
Calendar cell parser (one page answers a whole month at day level, verified
20 of 20 against day reads on 2026-09-15) and the route-page parser that
turns flights.flyfrontier.com/en/flights-from-<city> links into airport codes.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from shared.cache import write_history
from shared.checkout import BROWSER_PILOT, PROJECT_ROOT
from flights.sources.base import BaseSources, SourceUnavailable

if TYPE_CHECKING:       # a type only: importing the planner's trip module is not needed to read a page
    from flights.trip import Trip

TIME = re.compile(r"^\d{1,2}:\d{2} [AP]M$")
CODE = re.compile(r"^[A-Z]{3}$")
DUR = re.compile(r"^(?:(\d+) day\(s\) )?(\d+) hrs? (\d+) min(?: \(\+\d day\))? \| (Nonstop|(\d+) Stops?(.*))$")
MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
NETWORK_FILE = Path(__file__).with_name("frontier-network.json")
DEEP_LINK = "https://booking.flyfrontier.com/Flight/InternalSelect?o1={o}&d1={d}&dd1={day}&ADT=1&mon=true&promo="
# The Low Fare Calendar link on a day page (a#lowfareclendar) sends no request of its own:
# its handler builds this URL from page state and navigates to it (formCalenderUrl and
# switchViewGW in Frontier's js/select bundle, read 2026-09-16). ftype=GW is what the Go
# Wild pill's own navigation uses, so the URL opens the calendar already in Go Wild mode.
CALENDAR_LINK = ("https://booking.flyfrontier.com/Flight/InternalSelect?o1={o}&d1={d}&dd1={day}"
                 "&adt=1&umnr=false&loy=false&mon=true&ftype=GW&s=false&c=true")
ROUTE_PAGE = "https://flights.flyfrontier.com/en/flights-from-{slug}"


def t24(s: str) -> str:
    return datetime.strptime(s, "%I:%M %p").strftime("%H:%M")


def parse_rows(lines: list[str]) -> tuple[list[dict], bool | None]:
    """Rows in Go Wild mode: (time, code)+ pairs, a duration line, '+Details',
    then fare tiles. '$fee' then 'One-way' is a Go Wild seat; 'Unavailable' is
    none; 'One-way' then '$fee' means the page is still in Dollars mode and no
    row may be trusted (mode_ok False)."""
    routes: list[dict] = []
    mode_ok: bool | None = None
    i, n = 0, len(lines)
    while i < n:
        if TIME.match(lines[i]) and i + 1 < n and CODE.match(lines[i + 1]):
            pairs = []
            j = i
            while j + 1 < n and TIME.match(lines[j]) and CODE.match(lines[j + 1]):
                pairs.append((t24(lines[j]), lines[j + 1]))
                j += 2
            m = DUR.match(lines[j]) if j < n else None
            if not m or len(pairs) % 2:
                i = j + 1
                continue
            days, h, mi = int(m.group(1) or 0), int(m.group(2)), int(m.group(3))
            total = days * 1440 + h * 60 + mi
            legs = [{"from": pairs[k][1], "to": pairs[k + 1][1], "dep": pairs[k][0], "arr": pairs[k + 1][0], "flight": ""}
                    for k in range(0, len(pairs), 2)]
            k = j + 1
            while k < n and lines[k] != "+Details":
                k += 1
            fee, status = None, None
            if k + 2 < n:
                a, b = lines[k + 1], lines[k + 2]
                if a == "Unavailable":
                    status, mode_ok = "unavailable", True
                elif a.startswith("$") and b == "One-way":
                    fee, status, mode_ok = int(a[1:].replace(",", "")), "available", True
                elif a == "One-way" and b.startswith("$"):
                    status, mode_ok = "dollar-mode", False
            lays = []
            for x, y in zip(legs, legs[1:]):
                ha, ma = map(int, x["arr"].split(":"))
                hb, mb = map(int, y["dep"].split(":"))
                d = (hb * 60 + mb) - (ha * 60 + ma)
                if d < 0:
                    d += 1440
                lays.append({"airport": x["to"], "minutes": d})
            if status == "available":
                # no stops guard here (v1's gw_driver had stops <= 2): the query's max_stops_each_way is applied by trip._passes when the ticket is built
                routes.append({"stops": len(legs) - 1, "transferCities": [l["to"] for l in legs[:-1]], "goWildFee": fee,
                               "totalMinutes": total, "legs": legs, "layovers": lays})
            i = k + 1
        else:
            i += 1
    return routes, mode_ok


def pill(lines: list[str]) -> str | None:
    for k, l in enumerate(lines):
        if l == "GoWild!™" and k > 0:
            return lines[k - 1]
    return None


def day_from_page(origin: str, dest: str, day_iso: str, lines: list[str]) -> tuple[dict, str]:
    """Classify a booking-page snapshot (after the Go Wild pill click, or before
    it when the pill itself already answers). States: blocked (no 'Departing:'
    header, never a searched day), header (another route rendered), nopill
    (a real answer: no Go Wild seat that day), ok (rows parsed)."""
    day = {"date": day_iso, "weekday": date.fromisoformat(day_iso).strftime("%a"), "available": False, "routes": [], "read": True}
    if "Departing:" not in lines:
        day.update(unfetched=True, note="rate-limit block (no Departing header)")
        return day, "blocked"
    hi = lines.index("Departing:")
    if not (origin in lines[hi:hi + 4] and dest in lines[hi:hi + 6]):
        day.update(unfetched=True, note=f"header mismatch: {lines[hi:hi + 6]}")
        return day, "header"
    p = pill(lines)
    if p is None or p == "--" or not p.startswith("$"):
        day["note"] = "no itineraries sold" if "+Details" not in lines else f"pill {p!r}: no Go Wild seats"
        return day, "nopill"
    day["pillFee"] = int(p[1:].replace(",", ""))
    routes, ok = parse_rows(lines)
    routes = [r for r in routes if r["legs"][0]["from"] == origin and r["legs"][-1]["to"] == dest]
    if not ok:
        day.update(unfetched=True, note="rows not in Go Wild mode")
        return day, "dollars"
    day["routes"] = routes
    day["available"] = bool(routes)
    return day, "ok"


def calendar_from_page(origin: str, dest: str, lines: list[str]) -> str:
    """Classify a Low Fare Calendar snapshot. The calendar page heads its route
    with 'DEPARTING:' in capitals, where a day page says 'Departing:'; a blocked
    page carries neither, exactly as day_from_page reads a block. The route line
    follows the header ('Atlanta, GA (ATL) to Denver, CO (DEN)'). States: blocked,
    header (another route rendered), ok."""
    if "DEPARTING:" not in lines:
        return "blocked"
    hi = lines.index("DEPARTING:")
    route = lines[hi + 1] if hi + 1 < len(lines) else ""
    if f"({origin})" not in route or f"({dest})" not in route:
        return "header"
    return "ok"


def parse_calendar_cells(cells: list[dict], year: int, month: int) -> dict[str, float | str]:
    """Low Fare Calendar cells (day, price, cls, aria) for one month. Cells of
    neighbouring months are filtered by the aria label's month name. A
    'starting at $Not Available' cell is a real answer, "NA"."""
    name = MONTH_NAMES[month - 1]
    out: dict[str, float | str] = {}
    for c in cells:
        aria, day = c.get("aria") or "", c.get("day")
        if day is None or f", {name} " not in aria:
            continue
        m = re.search(r"starting at \$(Not Available|[\d,]+)", aria)
        if not m:
            continue
        out[date(year, month, int(day)).isoformat()] = "NA" if m.group(1) == "Not Available" else float(m.group(1).replace(",", ""))
    return out


def slug(city: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", city.lower()).strip("-")


def network_codes() -> set[str]:
    """Every airport Frontier lists in frontier-network.json."""
    return {a["iata"] for a in json.loads(NETWORK_FILE.read_text()).get("airports", [])}


def city_slugs() -> dict[str, list[str]]:
    """slug -> airport codes from frontier-network.json. Each airport is
    registered under its full city slug, the slug without any parenthetical
    ("Chicago (Midway)" -> chicago) and the part before a hyphen or slash
    ("Dallas-Fort Worth" -> dallas), so chicago -> ORD, MDW and dallas -> DFW.
    san-jose maps to both SJC and SJO; an extra gateway only adds branches."""
    data = json.loads(NETWORK_FILE.read_text())
    out: dict[str, list[str]] = {}
    for a in data.get("airports", []):
        for s in _slug_names(a["city"]):
            if a["iata"] not in out.setdefault(s, []):
                out[s].append(a["iata"])
    return out


def _slug_names(city: str) -> list[str]:
    """The slugs a city may go by, in a fixed order: without any parenthetical,
    then the part before a hyphen or slash, then the full name. A list, not a
    set: a set's order changes from one process to the next, which once sent
    DFW's route page to flights-from-dallas-fort-worth (404) on some runs and
    flights-from-dallas on others."""
    bare = re.sub(r"\(.*?\)", "", city)
    out: list[str] = []
    for s in (slug(bare), slug(re.split(r"[-/]", bare)[0]), slug(city)):
        if s and s not in out:
            out.append(s)
    return out


def origin_slugs(origin: str) -> list[str]:
    """Every slug the origin's route page may live under, in the order to try them."""
    data = json.loads(NETWORK_FILE.read_text())
    return next((_slug_names(a["city"]) for a in data.get("airports", []) if a["iata"] == origin), [])


def parse_route_page(html: str, origin: str) -> list[str]:
    """Destination codes linked from flights.flyfrontier.com/en/flights-from-<origin city>."""
    slugs = city_slugs()
    names = origin_slugs(origin)
    if not names:
        return []
    found = sorted({m for name in names for m in re.findall(rf"flights-from-{re.escape(name)}-to-([a-z0-9-]+)", html)})
    codes: list[str] = []
    for s in found:
        key = re.sub(r"-\d+$", "", s.rstrip("-"))      # "san-jose-3" -> "san-jose"
        for code in slugs.get(key, []):
            if code != origin and code not in codes:
                codes.append(code)
    return codes


# ---------------------------------------------------------------------------
# Live reader (browser-pilot)

REPO_ROOT = PROJECT_ROOT      # where `uv run` starts control.py (see shared/checkout.py)
CONTROL = BROWSER_PILOT / "control.py"
# The saved browser-pilot profile (cookies, Frontier session). Keep the name: renaming it
# would leave the saved profile behind and start a fresh, signed-out browser.
PROFILE = "frontier-v2"
PACE_SECONDS = 20.0           # gw_driver's pace: about 35 requests per window with no block
COOLDOWN_SECONDS = 15 * 60    # a block is waited out once, then the same read asked for once more
CALENDAR_PAINT_SECONDS = 60.0   # the longest the calendar read waits for a cell to paint (the pill waits 75)
CALENDAR_SLOW_SECONDS = 10.0    # a paint slower than this is worth a log line; the fixed sleep it replaced was 10 s
DATA_DIR = Path.home() / ".claude" / "data" / "frontier-go-wild"
DAY_CACHE_DIR = DATA_DIR / "cache"               # the v1 frontier-go-wild skill's folder, still the day cache
CALENDAR_CACHE_DIR = DATA_DIR / "calendar-cache"
HISTORY_DIR = DATA_DIR / "history"                 # every live day and calendar read, never overwritten
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
PILL = "text=GoWild!™"
# source: final-fix4 timed diagnostic 2026-09-16: the grid paints a hidden template and empty placeholders first; labels arrive with the fares
CELL_READY = "div.ibe-calendar-item[aria-label]"
ONE_WAY = 'text="One-way"'
# The cells and the page's own fare type in one read: the calendar's inline script config
# says "fareType":"GW" on a Go Wild calendar and another type on a dollar-mode one, so the
# page, not the URL, is what confirms the fees are Go Wild fees.
CALENDAR_JS = ("({gowild: [...document.querySelectorAll('script')]"
               ".some(s => (s.textContent || '').includes('\"fareType\":\"GW\"')), "
               "cells: [...document.querySelectorAll('div.ibe-calendar-item')].map(e => ({"
               "day: (e.querySelector('.calendar-date')||{}).innerText||null, "
               "price: (e.querySelector('.calendar-price')||{}).innerText||null, "
               "cls: String(e.className), aria: e.getAttribute('aria-label')}))})")
UNREADABLE = "rows not in Go Wild mode"


class PilotFailure(Exception):
    """browser-pilot answered `ok: false` on a control verb: the driver failed, so
    the page was never read. Not a Frontier block and never a cooldown."""


def page_lines(text: str) -> list[str]:
    """Snapshot text as the parsers want it (gw_driver splits the same way)."""
    return [l.strip() for l in (text or "").split("\n")]


def origin_slug(origin: str) -> str | None:
    return next(iter(origin_slugs(origin)), None)


async def pilot_ctl(profile: str, verb: str, *args: str, timeout: float = 90) -> dict:
    """One browser-pilot command; its last stdout line is the JSON answer."""
    env = dict(os.environ, BROWSER_PILOT_MAX_TEXT="80000")
    proc = await asyncio.create_subprocess_exec(
        "uv", "run", "python", str(CONTROL), verb, "--profile", profile, *args,
        cwd=str(REPO_ROOT), env=env, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return {"ok": False, "error": f"{verb} timed out after {timeout:.0f}s"}
    lines = [l for l in out.decode(errors="replace").splitlines() if l.strip()]
    if not lines:
        return {"ok": False, "error": err.decode(errors="replace").strip()[-300:] or "no output"}
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        # serve (detached, the default) answers with a plain readiness line, never JSON:
        # control.py _serve_detached prints "browser-pilot listening on <sock> (...)" and returns 0 once the socket is up
        if verb == "serve" and lines[-1].startswith("browser-pilot listening on"):
            return {"ok": True, "result": lines[-1]}
        return {"ok": False, "error": "unparsed output", "raw": lines[-1][:300]}


async def fetch_html(url: str) -> str:
    """The marketing site's route page over plain HTTP (not the booking engine)."""
    def _get() -> str:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.read().decode("utf-8", errors="replace")
    return await asyncio.to_thread(_get)


class FrontierReader:
    """Go Wild reads for LiveSources through one browser-pilot profile.

    Every booking-engine page load counts in `counters.frontier_requests`; a
    load after a cooldown (or the first) opens a new window. A block (a page
    with no 'Departing:' header) is waited out once and the read asked for
    once more; a second block raises SourceUnavailable('gowild').

    Day reads share the v1 frontier-go-wild skill's day cache; month reads keep
    their own calendar cache. Each live day or month read also keeps a copy in
    the price history (`history_dir`, see shared/cache.py `write_history`).
    Route pages come from the marketing site and are not booking-engine
    requests."""

    def __init__(self, trip: Trip, sink: BaseSources, *, log: Callable[[str], None] = print,
                 set_label: Callable[[str], None] = lambda s: None, ctl=None, sleep=asyncio.sleep,
                 now=time.monotonic, today=date.today, fetch=None, cal_dir: Path = CALENDAR_CACHE_DIR,
                 day_dir: Path = DAY_CACHE_DIR, profile: str = PROFILE,
                 history_dir: Path | None = None) -> None:
        self.trip, self.sink, self.log, self.set_label = trip, sink, log, set_label
        self._ctl = ctl or pilot_ctl
        self._fetch = fetch or fetch_html
        self._sleep, self._now, self._today = sleep, now, today
        self.cal_dir, self.day_dir, self.profile = Path(cal_dir), Path(day_dir), profile
        self.history_dir = Path(history_dir) if history_dir is not None else HISTORY_DIR
        q = trip.query
        self.ttl_hours = q.cache_ttl_hours
        self.use_cache = bool(q.use_cache)
        self._served = False
        self._window_open = False
        self._last: float | None = None

    # ------------------------------------------------------------ plumbing

    async def close(self) -> None:
        if self._served:
            await self._ctl(self.profile, "stop", timeout=60)
            self._served = False

    async def _ensure_served(self) -> None:
        if self._served:
            return
        r = await self._ctl(self.profile, "serve", timeout=120)
        if not r.get("ok"):
            why = r.get("error") or r
            if r.get("raw"):
                why = f"{why}: {r['raw']}"
            raise SourceUnavailable("gowild", f"browser-pilot could not start: {why}")
        self._served = True

    async def _pace(self) -> None:
        if self._last is not None:
            wait = PACE_SECONDS - (self._now() - self._last)
            if wait > 0:
                await self._sleep(wait)

    def _count_request(self) -> None:
        self.sink.counters.frontier_requests += 1
        if not self._window_open:
            self.sink.counters.windows += 1
            self._window_open = True

    async def _blocked(self, what: str, attempt: int) -> None:
        """Count the block; on the first, wait it out; on the second, stop the source."""
        self.sink.counters.blocks += 1
        if attempt == 2:
            raise SourceUnavailable("gowild", f"Frontier blocked twice on {what}")
        resume = time.strftime("%H:%M", time.localtime(time.time() + COOLDOWN_SECONDS))
        self.set_label(f"Frontier cooling down, resumes at {resume}")
        self.log(f"frontier: blocked on {what}; waiting {COOLDOWN_SECONDS // 60} min, resumes at {resume}")
        await self._sleep(COOLDOWN_SECONDS)
        self._window_open = False

    async def _ask(self, verb: str, *args: str, timeout: int) -> dict:
        """One browser-pilot call whose answer must be `ok`. A driver failure is
        not a Frontier answer, so it raises instead of reading as an empty page."""
        r = await self._ctl(self.profile, verb, *args, timeout=timeout)
        if not r.get("ok"):
            raise PilotFailure(r.get("error") or f"{verb} failed")
        return r

    async def _snapshot(self) -> list[str]:
        r = await self._ask("snapshot", timeout=60)
        return page_lines((r.get("result") or {}).get("text", ""))

    async def _open_day(self, o: str, d: str, day_iso: str) -> list[str]:
        """Load the one-way deep link (one request) and return the page lines."""
        await self._ensure_served()
        await self._pace()
        self._count_request()
        try:
            await self._ask("open", "--url", DEEP_LINK.format(o=o, d=d, day=day_iso), timeout=120)
            # A pill that never paints is a page state, not a driver fault: a block page
            # carries no booking header and no pill. Take the snapshot and let it decide.
            # --timeout-ms is what browser-pilot waits in the page; the `timeout` here is
            # only how long its subprocess may live, so it has to be the larger of the two
            # or the wait is killed before the page answers. Without the flag every wait
            # ran on Playwright's 5000 ms default, whatever the caller asked for.
            await self._ctl(self.profile, "wait", "--selector", PILL,
                            "--timeout-ms", "75000", timeout=90)
            return await self._snapshot()
        finally:
            self._last = self._now()

    async def _click_pill(self) -> None:
        """Tolerant on purpose: a click that misses leaves the page in Dollars mode,
        which the next page read reports as the state it is in."""
        await self._ctl(self.profile, "click", "--selector", PILL, timeout=60)
        await self._ctl(self.profile, "wait", "--selector", ONE_WAY, timeout=45)

    @staticmethod
    def _read_json(path: Path) -> dict | None:
        try:
            return json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None

    def _write_json(self, path: Path, doc: dict) -> None:
        """Save a live read: the latest copy at `path`, and the same text in the history."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        text = json.dumps(doc, indent=1)
        tmp.write_text(text)
        os.replace(tmp, path)
        write_history(self.history_dir, path.name, text)

    @staticmethod
    def _age_hours(cached_at: str | None) -> float | None:
        if not cached_at:
            return None
        try:
            ts = datetime.fromisoformat(cached_at)
        except ValueError:
            return None
        if ts.tzinfo is None:
            ts = ts.astimezone()
        return (datetime.now().astimezone() - ts).total_seconds() / 3600

    def _fresh_enough(self, doc: dict) -> tuple[bool, float]:
        age = self._age_hours(doc.get("cachedAt"))
        if self.ttl_hours is None:
            return True, age or 0.0
        return age is not None and age <= self.ttl_hours, age or 0.0

    @staticmethod
    def _best_fee(rec: dict) -> dict | None:
        fees = [r["goWildFee"] for r in rec.get("routes") or [] if r.get("goWildFee") is not None]
        return {"gowild": min(fees)} if fees else None

    @staticmethod
    def _best_day(days: dict) -> dict | None:
        vals = [v for v in days.values() if isinstance(v, (int, float))]
        return {"gowild": min(vals)} if vals else None

    # ------------------------------------------------------------ day

    async def day(self, o: str, d: str, day: date, fresh: bool = False) -> dict | None:
        day_iso = day.isoformat()
        path = self.day_dir / f"{o}_{d}_{day_iso}.json"
        hit = None if (fresh or not self.use_cache) else self._read_json(path)
        if hit is not None and not hit.get("unfetched"):
            ok, age = self._fresh_enough(hit)
            if ok:
                self.sink.record("gowild", o, d, day_iso, source="cache", found=len(hit.get("routes") or []),
                                 best=self._best_fee(hit), cached_age_hours=age)
                return hit
        what = f"{o}-{d} {day_iso}"
        try:
            for attempt in (1, 2):
                rec, state = await self._read_day_once(o, d, day_iso)
                if state != "blocked":
                    break
                await self._blocked(what, attempt)
        except PilotFailure as e:
            self.sink.record("gowild", o, d, day_iso, failed=True, reason=f"browser-pilot: {e}")
            return None
        if state == "header":
            self.sink.record("gowild", o, d, day_iso, failed=True, reason=rec.get("note"))
            return rec
        if state == "dollars":
            self.sink.record("gowild", o, d, day_iso, failed=True, reason=UNREADABLE)
            return rec
        self._write_json(path, dict(rec, cachedAt=datetime.now().astimezone().isoformat(timespec="seconds")))
        self.sink.record("gowild", o, d, day_iso, found=len(rec["routes"]), best=self._best_fee(rec))
        return rec

    async def _read_day_once(self, o: str, d: str, day_iso: str) -> tuple[dict, str]:
        lines = await self._open_day(o, d, day_iso)
        rec, state = day_from_page(o, d, day_iso, lines)
        for attempt in (1, 2, 3):
            if state != "dollars":
                break
            await self._click_pill()
            await self._sleep(2 + attempt)
            rec, state = day_from_page(o, d, day_iso, await self._snapshot())
        return rec, state

    # ------------------------------------------------------------ calendar

    async def calendar(self, o: str, d: str, month: str) -> dict[str, float | str]:
        path = self.cal_dir / f"{o}_{d}_{month}.json"
        first_iso = f"{month}-01"
        what_cal = f"Low Fare Calendar {month}"
        hit = self._read_json(path) if self.use_cache else None
        if hit is not None:
            ok, age = self._fresh_enough(hit)
            if ok:
                days = hit.get("days") or {}
                self.sink.record("gowild", o, d, first_iso, source="cache", found=len(days), pages=1,
                                 reason=what_cal, best=self._best_day(days), cached_age_hours=age)
                return days
        y, m = int(month[:4]), int(month[5:7])
        first = max(date(y, m, 1), self._today())
        if (first.year, first.month) != (y, m):
            self.sink.record("gowild", o, d, first_iso, failed=True, reason="month has passed")
            return {}
        what = f"calendar {o}-{d} {month}"
        try:
            for attempt in (1, 2):
                cells, state = await self._read_calendar_once(o, d, first.isoformat())
                if state != "blocked":
                    break
                await self._blocked(what, attempt)
        except PilotFailure as e:
            self.sink.record("gowild", o, d, first_iso, failed=True, reason=f"browser-pilot: {e}")
            return {}
        if state != "ok":
            reason = UNREADABLE if state == "dollars" else f"calendar page unreadable ({state})"
            self.sink.record("gowild", o, d, first_iso, failed=True, reason=reason)
            return {}
        days = parse_calendar_cells(cells, y, m)
        if not days:
            self.sink.record("gowild", o, d, first_iso, failed=True, reason="no calendar cells", pages=1)
            return {}
        self._write_json(path, {"origin": o, "dest": d, "month": month, "days": days,
                                "cachedAt": datetime.now().astimezone().isoformat(timespec="seconds")})
        self.sink.record("gowild", o, d, first_iso, found=len(days), best=self._best_day(days), pages=1,
                         reason=what_cal)
        return days

    async def _read_calendar_once(self, o: str, d: str, first_iso: str) -> tuple[list[dict], str]:
        """Read the Low Fare Calendar for the month the first day belongs to. The
        calendar link is opened directly with ftype=GW, so the month is one booking
        request and no in-page click can be lost on a page that is still navigating.
        The page itself says which mode it is in, so the URL alone never skips the
        check: only a calendar whose config says fareType GW has Go Wild fees in its
        cells. States: blocked and header as on a day page, dollars when the page
        came back in fares, ok."""
        await self._ensure_served()
        await self._pace()
        self._count_request()
        started = self._now()
        try:
            await self._ask("open", "--url", CALENDAR_LINK.format(o=o, d=d, day=first_iso), timeout=120)
            # The cells paint after the page, so wait for the first cell that carries a fare
            # label, the tolerant way the pill is waited for on the day page, then read once.
            # An unlabelled cell is the hidden template or an empty placeholder, so waiting on
            # it reads the month before the fares arrive. The wait asks the booking engine for
            # nothing, so it costs no request. A fixed sleep read a calendar that painted late
            # as an empty month: the 2026-09-16 acceptance run lost 2 of 19 that way.
            await self._ctl(self.profile, "wait", "--selector", CELL_READY,
                            "--timeout-ms", str(int(CALENDAR_PAINT_SECONDS * 1000)),
                            timeout=CALENDAR_PAINT_SECONDS + 15)
            state = calendar_from_page(o, d, await self._snapshot())
            if state != "ok":
                return [], state
            r = await self._ask("evaluate", "--expression", CALENDAR_JS, timeout=60)
        finally:
            self._last = self._now()
        painted = self._last - started
        if painted > CALENDAR_SLOW_SECONDS:
            self.log(f"frontier: calendar {o}-{d} {first_iso}: cells after {painted:.0f} s")
        res = r.get("result") if isinstance(r.get("result"), dict) else {}
        if not res.get("gowild"):
            return [], "dollars"
        cells = res.get("cells")
        return (cells if isinstance(cells, list) else []), "ok"

    # ------------------------------------------------------------ routes

    async def routes(self, origin: str) -> list[str]:
        names = origin_slugs(origin)
        if not names:
            # Not recorded in `searches`: the work list holds searches, and this is a
            # marketing page. It stays in counters.loads as "routes".
            self.log(f"frontier: {origin} not in frontier-network.json; no route page to read")
            return []
        for i, s in enumerate(names):
            try:
                html = await self._fetch(ROUTE_PAGE.format(slug=s))
            except urllib.error.HTTPError as e:
                # a city page under another of its names (Dallas-Fort Worth is /flights-from-dallas)
                if e.code == 404 and i < len(names) - 1:
                    continue
                self.log(f"frontier: route page for {origin} failed: {type(e).__name__}: {e}"[:200])
                return []
            except (OSError, ValueError) as e:
                self.log(f"frontier: route page for {origin} failed: {type(e).__name__}: {e}"[:200])
                return []
            return parse_route_page(html, origin)
        return []
