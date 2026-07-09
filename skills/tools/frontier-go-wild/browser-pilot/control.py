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

from session import BrowserSession

_DISPATCH = {"open", "snapshot", "click", "type", "keyboard_type", "press", "wait", "screenshot", "save_state", "evaluate", "select", "select_native", "cache_route", "focus_nth", "type_focused"}


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
                result = await getattr(session, cmd)(**cargs)
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
    p.add_argument("--key"); p.add_argument("--path"); p.add_argument("--state")
    p.add_argument("--expression"); p.add_argument("--delay-ms", type=int, dest="delay_ms")
    p.add_argument("--pattern")
    p.add_argument("--tag"); p.add_argument("--n", type=int)
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
             "delay_ms": a.delay_ms, "tag": a.tag, "n": a.n,
             "pattern": a.pattern}.items() if v is not None}
    return asyncio.run(_client(a.cmd, a.profile, args))


if __name__ == "__main__":
    raise SystemExit(main())
