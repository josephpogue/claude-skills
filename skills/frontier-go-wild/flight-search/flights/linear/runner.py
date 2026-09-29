"""The linear run every search skill shares: read the list top to bottom, filter, report.

A skill hands `main` its adapter class. The run reads every item of `reads` in
the order given, one at a time, and never skips, reorders or ranks. A read
that fails is reported as failed and the run goes on to the next. A site that
stops answering (blocked twice, a login that will not hold) ends the run
there: the read it happened on is failed, every read after it is
`not_reached`, and both carry the reason. A SIGTERM or SIGHUP ends a run the
same way: the read it lands on and every read after it are `not_reached`, the
browser is closed, and the document is still written.
"""
from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
import shutil
import signal
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from flights.linear.contract import DROP_REASONS, ReadResult, Request, drop_reason, parse_request
from flights.skill_names import former
from flights.sources.base import SourceUnavailable
from shared.checkout import PROJECT_ROOT, PUBLISHED, PUBLISHED_DATA

REPO_ROOT = PROJECT_ROOT
# In a checkout the result files sit in it; the published skill keeps them out of its own folder.
LOGS_DIR = Path(os.environ.get("FLIGHT_LOGS_DIR")
                or (PUBLISHED_DATA / "logs" if PUBLISHED else REPO_ROOT / ".flight-search-logs")) / "linear"
# One folder for the whole machine, not one per checkout: the site sees one machine.
LOCKS_DIR = Path(os.environ.get("FLIGHT_LOCKS_DIR") or Path.home() / ".claude" / "data" / "flight-search" / "locks")
ALREADY_RUNNING = "another live run of this skill is in progress; wait for it to end, or add --saved-only"

_RUNLOG_BIN = os.environ.get("RUNLOG_BIN") or shutil.which("runlog") or os.path.expanduser("~/.local/bin/runlog")
_RUNLOG_TIMEOUTS = {"start": 60, "done": 60, "error": 60}
# The signals that stop a run and still write its document.
STOP_SIGNALS = (signal.SIGTERM, signal.SIGHUP)
# The longest `Adapter.close` may take before the run gives up on it: the
# Frontier reader's own stop call allows itself 60 seconds.
CLOSE_TIMEOUT_S = 90


def _runlog(*args: str) -> str | None:
    """Best-effort call to the runlog helper: never raises, never blocks the run."""
    if not (os.path.isfile(_RUNLOG_BIN) and os.access(_RUNLOG_BIN, os.X_OK)):
        return None
    try:
        p = subprocess.run([_RUNLOG_BIN, *args], capture_output=True, text=True,
                           timeout=_RUNLOG_TIMEOUTS.get(args[0], 10))
        return p.stdout.strip() if p.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


class Adapter:
    """One site. A subclass sets the three names and implements `read`."""

    skill = ""          # the skill's name, which is also its runlog name
    platform = ""
    price_type = ""

    def __init__(self, request: Request, log: Callable[[str], None]) -> None:
        self.request, self.log = request, log

    @classmethod
    def goes_live(cls, request: Request) -> bool:
        """True when this run may open the site. Only such a run takes the
        skill's one-live-run lock; a run that cannot open it is never held back."""
        return not request.saved_only

    async def read(self, read) -> ReadResult:
        raise NotImplementedError

    async def finish(self) -> dict[int, ReadResult]:
        """After the last read: results that replace earlier ones, by read index.
        For a site whose own reader reads a page a second time; most have none."""
        return {}

    async def close(self) -> None:
        return None


def _entry(read, res: ReadResult, passed: int, dropped: dict[str, int]) -> dict[str, Any]:
    return {"index": read.index, "origin": read.origin, "destination": read.destination,
            "date": read.day.isoformat(), "status": res.status, "source": res.source,
            "saved_age_hours": res.saved_age_hours, "found": len(res.rows), "passed": passed,
            "dropped": dropped, "note": res.note}


def filter_read(read, res: ReadResult, request: Request) -> tuple[list[dict], dict[str, int]]:
    """The rows of one read that pass, in page order, and a count of the rest by filter."""
    kept: list[dict] = []
    dropped = {r: 0 for r in DROP_REASONS}
    for row in res.rows:
        row["read_index"] = read.index
        why = drop_reason(row, request.filters, platform_layover_cap=res.platform_layover_cap)
        if why is None:
            kept.append(row)
        else:
            dropped[why] += 1
    return kept, {k: v for k, v in dropped.items() if v}


async def run(adapter: Adapter, request: Request, log: Callable[[str], None],
              on_read: Callable[[int, int, str], None] = lambda done, total, label: None,
              signals: tuple[signal.Signals, ...] = ()) -> dict[str, Any]:
    """`signals` stop the run from inside the event loop: the read (or second
    read) under way is cancelled, and the run closes the adapter while the
    browser's connection is still being served. The handler this replaced
    raised SystemExit from outside the loop; asyncio then cancelled the
    browser's connection along with the run, and `close` waited forever for a
    reply (2026-09-28: a SIGTERM left amex-points-search idle, holding its lock)."""
    started = datetime.now().astimezone().isoformat(timespec="seconds")
    results: dict[int, ReadResult] = {}
    stop_reason: str | None = None
    total = len(request.reads)
    loop, task = asyncio.get_running_loop(), asyncio.current_task()
    signalled: list[signal.Signals] = []
    reading = True

    def _signalled(sig: signal.Signals) -> None:
        # Only the reads are cancelled: a cancel landing in `close` would cut the browser's own shutdown short.
        if not signalled:
            signalled.append(sig)
            if reading:
                task.cancel()

    previous = {sig: signal.getsignal(sig) for sig in signals}
    for sig in signals:
        loop.add_signal_handler(sig, _signalled, sig)
    try:
        for read in request.reads:
            label = f"{read.origin}-{read.destination} {read.day.isoformat()}"
            if stop_reason is not None:
                results[read.index] = ReadResult(status="not_reached", note=stop_reason)
                continue
            on_read(read.index, total, label)
            try:
                results[read.index] = await adapter.read(read)
            except SourceUnavailable as e:
                stop_reason = str(e)
                log(f"stopping at read {read.index} ({label}): {stop_reason}")
                results[read.index] = ReadResult(status="failed", source="live", note=stop_reason)
            except Exception as e:  # noqa: BLE001
                # The contract: a read can fail and the run goes on. The readers
                # catch their own timeouts and layout errors, but a browser error
                # (2026-09-22: Page.goto net::ERR_NETWORK_CHANGED on read 62 of
                # 84) escaped them and took the run down with no document at all.
                why = f"{type(e).__name__}: {e}"[:200]
                log(f"read {read.index} ({label}) failed: {why}")
                results[read.index] = ReadResult(status="failed", source="live", note=why)
        if stop_reason is None:
            try:
                results.update(await adapter.finish())
            except SourceUnavailable as e:
                log(f"second reads stopped: {e}")
    except asyncio.CancelledError:
        if not signalled:
            raise
        task.uncancel()
        stop_reason = f"{signalled[0].name} received"
        log(f"{stop_reason}; closing the browser")
    finally:
        reading = False
        try:
            await _close(adapter, log)
        finally:
            for sig, handler in previous.items():
                loop.remove_signal_handler(sig)
                signal.signal(sig, handler)
    reads_out, flights = [], []
    for read in request.reads:
        # A signal leaves the read it cut off, and every read after it, with no result.
        res = results[read.index] if read.index in results else ReadResult(status="not_reached", note=stop_reason)
        kept, dropped = filter_read(read, res, request)
        flights.extend(kept)
        reads_out.append(_entry(read, res, len(kept), dropped))
    return {"skill": adapter.skill, "platform": adapter.platform, "price_type": adapter.price_type,
            "status": "ok" if stop_reason is None else "stopped", "stop_reason": stop_reason,
            "started": started, "finished": datetime.now().astimezone().isoformat(timespec="seconds"),
            "filters": request.filters.as_dict(), "max_age_hours": request.max_age_hours,
            "saved_only": request.saved_only, "reads": reads_out, "flights": flights}


async def _close(adapter: Adapter, log: Callable[[str], None]) -> None:
    try:
        await asyncio.wait_for(adapter.close(), CLOSE_TIMEOUT_S)
    except TimeoutError:
        log(f"the browser did not close within {CLOSE_TIMEOUT_S}s; it ends with the process")


def refusal(adapter_cls: type[Adapter], reason: str, *, saved_only: bool) -> dict[str, Any]:
    """The document of a run that was refused before its first read: every key
    of a real one in the same order, so a caller parses one shape."""
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    return {"skill": adapter_cls.skill, "platform": adapter_cls.platform, "price_type": adapter_cls.price_type,
            "status": "refused", "stop_reason": reason, "started": now, "finished": now,
            "filters": None, "max_age_hours": None, "saved_only": saved_only,
            "reads": [], "flights": [], "run_id": None}


def _refuse(adapter_cls: type[Adapter], reason: str, *, saved_only: bool) -> int:
    print(json.dumps(refusal(adapter_cls, reason, saved_only=saved_only), indent=1))
    return 2


class _Locks:
    """The lock files one live run holds; `close` lets go of all of them."""

    def __init__(self, handles: list) -> None:
        self.handles = handles

    def close(self) -> None:
        for h in self.handles:
            h.close()


def live_lock(skill: str):
    """The one live run a skill may have on this machine, or None when another
    run holds it. Each site paces one reader, and two would burst it. The lock
    is the operating system's, so it is let go when the process ends, however
    it ends, and no stale lock can be left behind. The lock under the skill's
    former name is taken too, so a checkout still on the old name and one on
    the new name cannot both read the same site at once."""
    LOCKS_DIR.mkdir(parents=True, exist_ok=True)
    handles = []
    for name in (skill, *former(skill)):
        handle = open(LOCKS_DIR / f"{name}.lock", "w")
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            for h in handles:
                h.close()
            return None
        handles.append(handle)
    return _Locks(handles)


def main(adapter_cls: type[Adapter], argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=f"{adapter_cls.skill}: read a list of flights top to bottom.")
    ap.add_argument("--saved-only", action="store_true",
                    help="answer from saved pages only and never open a browser; a read with no saved page fails")
    args = ap.parse_args(argv)
    skill = adapter_cls.skill
    try:
        request = parse_request(json.load(sys.stdin), saved_only=args.saved_only)
    except (ValueError, json.JSONDecodeError) as e:
        return _refuse(adapter_cls, str(e), saved_only=args.saved_only)
    # A run that opens no browser takes no lock, so any number of them may overlap.
    live = adapter_cls.goes_live(request)
    lock = live_lock(skill) if live else None
    if live and lock is None:
        return _refuse(adapter_cls, ALREADY_RUNNING, saved_only=False)
    try:
        return _run_logged(adapter_cls, request)
    finally:
        if lock is not None:
            lock.close()


def _run_logged(adapter_cls: type[Adapter], request: Request) -> int:
    skill = adapter_cls.skill

    def log(s: str) -> None:
        print(s, file=sys.stderr, flush=True)

    first, last = request.reads[0], request.reads[-1]
    title = f"{len(request.reads)} reads, {first.origin}-{first.destination} {first.day} to {last.origin}-{last.destination} {last.day}"
    rid = os.environ.get("RUNLOG_RUN_ID") or f"{datetime.now():%Y%m%d-%H%M%S}-{os.urandom(4).hex()}"
    logged = _runlog("start", skill, "--run-id", rid, "--trigger", os.environ.get("RUNLOG_TRIGGER", "manual"),
                     "--meta", f"title={title}") is not None

    def on_read(done: int, total: int, label: str) -> None:
        log(f"read {done + 1} of {total}: {label}")
        if logged:
            _runlog("progress", rid, f"read {done + 1} of {total}: {label}", "--fraction", f"{done / total:.2f}")

    def _terminated(signum, _frame) -> None:
        # Outside the event loop only (runlog start, writing the document): inside it `run` owns these signals.
        raise SystemExit(f"stopped by signal {signum}")

    for sig in STOP_SIGNALS:
        signal.signal(sig, _terminated)
    try:
        doc = asyncio.run(run(adapter_cls(request, log), request, log, on_read, signals=STOP_SIGNALS))
        doc["run_id"] = rid
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        path = LOGS_DIR / f"{skill}-{rid}.json"
        path.write_text(json.dumps(doc, indent=1))
    except BaseException as e:
        if logged:
            _runlog("error", rid, "--reason", f"{type(e).__name__}: {e}"[:200])
        raise
    if logged and doc["status"] == "ok":
        _runlog("done", rid, "--result", str(path))
    elif logged:    # a run the site cut short is not a good run, even though what it read is kept
        _runlog("error", rid, "--reason", f"stopped: {doc['stop_reason']}; reads so far in {path}"[:200])
    print(json.dumps(doc, indent=1))
    log(f"{len(doc['flights'])} flights passed from {len(doc['reads'])} reads; saved to {path}")
    return 0 if doc["status"] == "ok" else 1
