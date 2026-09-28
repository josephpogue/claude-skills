"""Browser-control daemon + client. The daemon owns one long-lived
BrowserSession; the client sends one JSON command per invocation so a
step-by-step agent can drive the page across separate calls."""
from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

# 'shared.profiles' comes from the sibling flight-search folder, in the source
# repo and in the published frontier-go-wild skill alike, so this file is
# mirrored into that skill byte for byte (automations/flight-search/publish_gowild.py).
# A shared/ next to this file is still tried first. (conftest.py only covers
# the pytest process, so the subprocess needs this too.)
_HERE = Path(__file__).resolve().parent
for _root in (_HERE, _HERE.parent / "flight-search"):
    if (_root / "shared" / "profiles.py").exists() and str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

from session import BrowserSession

_DISPATCH = {"open", "snapshot", "click", "type", "keyboard_type", "press", "wait", "screenshot", "save_state", "evaluate", "select", "select_native", "cache_route", "focus_nth", "type_focused", "tree", "act", "pages", "use_page"}


# Commands that drive a control, so a failure may be a moved button rather than
# a real dead end. Give one of these an `intent` and it repairs itself instead
# of raising; without an intent nothing changes.
_INTERACTIVE = {"click", "type", "keyboard_type", "press", "wait", "select", "select_native"}

# What the healer should do once it has found the control the command meant.
_HEAL_METHOD = {"click": "click", "type": "fill", "keyboard_type": "type",
                "press": "press", "wait": "wait", "select": "select",
                "select_native": "select"}


async def _run_command(session, cmd: str, cargs: dict, profile: str, ask=None):
    """Run one command, and repair the step in place if a selector has moved.

    `intent` is what makes this different from a plain call: it is the step said
    in words ("the box where the email address is typed"), which is what the
    healer needs to recognise the control after the page changed. The dead
    selector alone tells it nothing. `key` alone is enough when the recipe
    already carries those words under `intents`."""
    cargs = dict(cargs)
    intent = cargs.pop("intent", None)
    key = cargs.pop("key", None)
    site = cargs.pop("site", None) or profile
    call = getattr(session, cmd)
    if cmd not in _INTERACTIVE or not (intent or key):
        return await call(**cargs)
    try:
        return await call(**cargs)
    except Exception as e:
        # Imported only here: a step with no intent never heals, and the
        # published frontier-go-wild skill ships this file without the healer.
        import heal
        outcome = await heal.heal_step(
            session, site=site, key=key or cargs.get("selector") or cmd,
            intent=intent or "", error=f"{type(e).__name__}: {e}",
            method=_HEAL_METHOD.get(cmd, "click"), value=cargs.get("value"),
            ask=ask,
            run_id=os.environ.get("BROWSER_PILOT_RUN_ID"),
            signals_dir=os.environ.get("BROWSER_PILOT_SIGNALS_DIR"),
            screenshot_dir=os.environ.get("BROWSER_PILOT_SCREENSHOT_DIR"),
        )
        if outcome.get("healed"):
            return outcome
        raise RuntimeError(
            f"{cmd} failed and could not be repaired: {outcome.get('reason')} "
            f"(original error: {type(e).__name__}: {e})"
        )


def _sock_path(profile: str) -> str:
    env = os.environ.get("BROWSER_PILOT_SOCK")
    if env:
        return env
    base = os.environ.get("TMPDIR", "/tmp").rstrip("/")
    return f"{base}/browser-pilot-{profile}.sock"


async def _serve(profile: str, headless: bool, state_file: str | None) -> None:
    sock = _sock_path(profile)
    if os.path.exists(sock):
        os.unlink(sock)
    session = BrowserSession(profile=profile, headless=headless, state_file=state_file)
    await session.start()
    stop_event = asyncio.Event()

    async def handle(reader, writer):
        try:
            line = await reader.readline()
            if not line:
                return
            msg = json.loads(line)
            cmd, cargs = msg.get("cmd"), msg.get("args", {})
            if cmd == "stop":
                resp = {"ok": True, "result": "stopping"}
                stop_event.set()
            elif cmd in _DISPATCH:
                result = await _run_command(session, cmd, cargs, profile)
                resp = {"ok": True, "result": result}
            else:
                resp = {"ok": False, "error": f"unknown cmd: {cmd}"}
        except Exception as e:  # isolate per-command failure
            resp = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        writer.write((json.dumps(resp) + "\n").encode())
        await writer.drain()
        writer.close()

    server = await asyncio.start_unix_server(handle, path=sock)
    # Announce readiness so a caller polling the daemon's log/output can tell the
    # session is live (and logged-in state restored) instead of hanging on a wait.
    print(f"browser-pilot listening on {sock} (profile={profile}, headless={headless})", flush=True)
    async with server:
        await stop_event.wait()
    await session.stop()
    if os.path.exists(sock):
        os.unlink(sock)


def _serve_detached(profile: str, headless: bool, state_file: str | None) -> int:
    """Start the daemon in a detached child and return once it's listening.

    `serve` is a long-running daemon that never exits on its own, so running it
    in the foreground blocks (and hangs) the caller. Detaching makes the invoking
    command return as soon as the socket is up, regardless of how it was launched
    — this is the default so an agent can't accidentally hang a run on it."""
    sock = _sock_path(profile)
    if os.path.exists(sock):
        os.unlink(sock)
    pid = os.fork()
    if pid > 0:
        for _ in range(300):  # wait up to ~30s for the child to bind the socket
            if os.path.exists(sock):
                print(
                    f"browser-pilot listening on {sock} (profile={profile}, headless={headless})",
                    flush=True,
                )
                return 0
            time.sleep(0.1)
        print(f"browser-pilot: daemon for profile={profile} failed to start", file=sys.stderr, flush=True)
        return 1
    # Child: fully detach (new session, stdio → /dev/null) and run the server so it
    # survives the parent returning and never holds the caller's pipes open.
    os.setsid()
    devnull = os.open(os.devnull, os.O_RDWR)
    for fd in (0, 1, 2):
        os.dup2(devnull, fd)
    try:
        asyncio.run(_serve(profile, headless, state_file))
    finally:
        os._exit(0)


async def _client(cmd: str, profile: str, args: dict) -> int:
    reader, writer = await asyncio.open_unix_connection(_sock_path(profile))
    writer.write((json.dumps({"cmd": cmd, "args": args}) + "\n").encode())
    await writer.drain()
    line = await reader.readline()
    writer.close()
    sys.stdout.write(line.decode())
    return 0 if json.loads(line).get("ok") else 1


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("cmd")
    p.add_argument("--profile", default="default")
    p.add_argument("--headed", action="store_true")
    p.add_argument("--headless", dest="headless", action="store_true")
    p.add_argument("--url"); p.add_argument("--selector"); p.add_argument("--value")
    # The session methods already take a timeout_ms (session.py wait/click/press), but
    # the command line had no way to pass one, so every wait, click and press ran on
    # Playwright's 5000 ms default however long the caller meant to wait.
    p.add_argument("--timeout-ms", dest="timeout_ms", type=int,
                   help="how long the command waits in the page, in milliseconds")
    p.add_argument("--key"); p.add_argument("--path"); p.add_argument("--state")
    p.add_argument("--expression"); p.add_argument("--delay-ms", type=int, dest="delay_ms")
    p.add_argument("--pattern")
    p.add_argument("--tag"); p.add_argument("--n", type=int)
    # tree()/act(): the healer drives controls by the id tree() printed,
    # not by a selector it had to guess.
    p.add_argument("--id", dest="element_id"); p.add_argument("--method")
    # An interaction that carries an intent repairs itself when the control
    # has moved, instead of ending the run.
    p.add_argument("--intent", help="what this step is trying to do, in words")
    p.add_argument("--selector-key", dest="selector_key",
                   help="the recipe selector name to repair")
    p.add_argument("--site", help="recipe to repair (default: the profile name)")
    p.add_argument("--foreground", action="store_true",
                   help="run the daemon in the foreground (blocks); default is detached")
    a = p.parse_args()
    if a.cmd == "serve":
        headless = not a.headed
        if a.foreground:
            asyncio.run(_serve(a.profile, headless, a.state))
            return 0
        return _serve_detached(a.profile, headless, a.state)
    args = {k: v for k, v in
            {"url": a.url, "selector": a.selector, "value": a.value,
             "key": a.key, "path": a.path, "expression": a.expression,
             "delay_ms": a.delay_ms, "timeout_ms": a.timeout_ms, "tag": a.tag, "n": a.n,
             "pattern": a.pattern, "element_id": a.element_id,
             "method": a.method, "intent": a.intent, "key": a.selector_key,
             "site": a.site}.items() if v is not None}
    return asyncio.run(_client(a.cmd, a.profile, args))


if __name__ == "__main__":
    raise SystemExit(main())
