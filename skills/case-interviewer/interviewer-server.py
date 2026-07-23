#!/usr/bin/env python3
"""Live case-interview server. Serves one case packet as an interactive browser
page and plays the INTERVIEWER through the `claude` CLI (subscription, no API).
The user is the interviewee; Claude runs the case, reveals exhibits on cue, takes
uploaded scratch work, and scores a debrief against the grading rubric.

Usage:
  python3 interviewer-server.py <packet-dir> [port]   # serve a real interview
  python3 interviewer-server.py --selftest            # scripted round-trip, exit 0/1

Routes (all localhost, no-cache):
  GET  /                -> interview.html with case title/style/difficulty injected
  GET  /exhibit/<n>     -> exhibit image asset for exhibit n (if the packet has one)
  POST /chat            -> {"message","hint"?} => {"reply","exhibits":[{n,title,markdown,hasImage}]}
  POST /upload          -> {"name","data"(base64),"mime","caption"?} => {"reply","exhibits":[...]}
  POST /debrief         -> {} => scorecard JSON; also writes the session file + runlog done

Every turn is appended to <packet>/transcript.md (source of truth for the debrief
and the saved session). claude -p runs headless with cwd = packet dir, resuming one
session per packet (id in <packet>/.chat-session).
"""
import base64
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SKILL_DIR = pathlib.Path(__file__).resolve().parent
REFERENCES = SKILL_DIR / "references"


def _sessions_root() -> pathlib.Path:
    """Where finished sessions are written. Portable across machines:
    an explicit override wins; else reuse a local My-Life Casing library if it's
    here; else fall back to a self-contained data dir under ~/.claude."""
    env = os.environ.get("CASE_INTERVIEWER_SESSIONS")
    if env:
        return pathlib.Path(env).expanduser()
    casing = pathlib.Path.home() / "Documents/GitHub/My-Life/Casing"
    if casing.is_dir():
        return casing / "sessions"
    return pathlib.Path.home() / ".claude/data/case-interviewer/sessions"


SESSIONS = _sessions_root()
ALLOWED_TOOLS = ["Read", "Write", "Edit", "Glob", "Grep"]

# ---------------------------------------------------------------------------
# Interviewer + debrief prompts
# ---------------------------------------------------------------------------

INTERVIEWER_PROMPT = f"""You are a real consulting case interviewer running a live case against a candidate who is talking to you through a chat window. The candidate is the interviewee; you are the interviewer.

BEFORE YOUR FIRST REPLY, read these two files in full and hold them in your head for the whole interview:
- {REFERENCES}/interviewer-playbook.md : exactly how you behave in the room (voice, pushback, hints, progressive disclosure, closing, debrief).
- case.md in your current working directory : THIS case's prompt, clarifying-fact bank, beat arc, exhibits, and (secret) benchmark answers.

Non-negotiables from the playbook:
- Talk like a person across a table: one to four short sentences, no headers, no bullet lists, no essays. React, do not summarize back.
- Reveal nothing early. State only the prompt and the one objective up front. Give a clarifying fact ONLY when the candidate asks something that touches it. Never volunteer scope, cost classification, or segment splits.
- To reveal exhibit N, put the token [EXHIBIT N] on its own line in your reply (e.g. [EXHIBIT 2]). The server renders that exhibit to the candidate at that point. Reveal an exhibit only at its beat (interviewer-led) or when the candidate asks for exactly that data (interviewee-led), one at a time. Never paste an exhibit's numbers into your prose, and never describe an exhibit you have not revealed.
- The benchmark answers in case.md are yours alone. NEVER state the guideline buckets, the worked math, or the target recommendation. If the candidate is wrong, probe; do not hand over the answer key.
- Hints ONLY when the candidate explicitly asks. A hint is a nudge toward the approach, never the answer. Keep a mental ledger of every hint for the debrief.
- Follow the case's prescribed style (interviewer-led vs interviewee-led) from case.md. Guard the stated objective; if the candidate solves the wrong problem, let it run and note it, do not silently rescue.
- If the server tells you the candidate uploaded a file at a path, Read it and react like an interviewer glancing at their scratch work: what's right, what's off, what doesn't follow. Do not solve it for them.

Reply with ONLY what you would say out loud as the interviewer. No preamble about being an AI, no meta commentary, no mention of benchmarks, scores, or that the case may be invented."""

DEBRIEF_INSTRUCTION = f"""[END OF INTERVIEW. Drop the interviewer persona and become the evaluator now.]

Score this candidate's whole performance against the rubric in {REFERENCES}/grading-rubric.md. Read that file, apply the four dimensions and the gate checks, then place the candidate on the verdict tiers. Base every score on what actually happened in this interview: quote the candidate's real words from the transcript as evidence. Read transcript.md in your current directory if you need the full record.

Respond with ONLY a single JSON object, no prose before or after, no code fence, in exactly this shape:
{{
  "verdict": "Strong hire | Hire | Round 1 pass, final-round fail | No hire",
  "clientTest": "one sentence answering: would you put this person in front of a client, and why",
  "dimensions": [
    {{"name": "Structure", "weight": 30, "score": <1-10>, "evidence": ["quote or moment", "..."]}},
    {{"name": "Quantitative accuracy", "weight": 20, "score": <1-10>, "evidence": ["...", "..."]}},
    {{"name": "Insight", "weight": 25, "score": <1-10>, "evidence": ["...", "..."]}},
    {{"name": "Communication", "weight": 25, "score": <1-10>, "evidence": ["...", "..."]}}
  ],
  "gates": {{
    "misreadMath": "pass | tripped | n/a, with one line of why",
    "illogicalClaim": "pass | tripped | n/a, with one line",
    "wrongProblem": "pass | tripped | n/a, with one line",
    "hintLedger": "count and what the candidate did with each hint, or 'no hints requested'",
    "interventionCount": "number of interviewer rescues and whether the same failure repeated"
  }},
  "strongAnswer": "A beat-by-beat walkthrough of the case done well, in markdown: the opening structure a 9 would lay out (as an issue tree), the key data requests in order, the surprise moment and the dig it deserved, the math with worded formulas, and the verbatim top-down closing synthesis. Concrete to THIS case, not generic advice.",
  "drills": ["specific behavioral drill", "another", "optional third"]
}}

Every score must be justified by the evidence quotes. Do not invent moments that did not happen. If the interview was very short, score what you have and say so in clientTest."""

# ---------------------------------------------------------------------------
# claude plumbing
# ---------------------------------------------------------------------------

def run_claude(packet: pathlib.Path, message: str, timeout: int = 600) -> str:
    claude = shutil.which("claude") or str(pathlib.Path.home() / ".claude/local/claude")
    session_file = packet / ".chat-session"
    cmd = [claude, "-p", message, "--output-format", "json",
           "--append-system-prompt", INTERVIEWER_PROMPT,
           "--permission-mode", "acceptEdits",
           "--add-dir", str(SKILL_DIR),
           "--allowedTools", *ALLOWED_TOOLS]
    if session_file.exists():
        cmd += ["--resume", session_file.read_text().strip()]
    proc = subprocess.run(cmd, cwd=packet, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "claude failed")
    data = json.loads(proc.stdout)
    if data.get("session_id"):
        session_file.write_text(data["session_id"])
    return (data.get("result") or "").strip()


def extract_json(text: str) -> dict:
    """Pull a JSON object out of a model reply that may wrap it in a code fence
    or stray prose."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else None
    if candidate is None:
        start, end = text.find("{"), text.rfind("}")
        candidate = text[start:end + 1] if start != -1 and end > start else text
    return json.loads(candidate)


# ---------------------------------------------------------------------------
# packet parsing (case metadata + exhibits)
# ---------------------------------------------------------------------------

def parse_frontmatter(case_md: str) -> dict:
    meta = {}
    if case_md.startswith("---"):
        end = case_md.find("\n---", 3)
        if end != -1:
            for line in case_md[3:end].splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip().lower()] = v.strip()
    if "title" not in meta:
        m = re.search(r"^#\s+(.+)$", case_md, re.MULTILINE)
        meta["title"] = m.group(1).strip() if m else "Case interview"
    return meta


def resolve_exhibit(packet: pathlib.Path, n: int) -> dict | None:
    """Return {n, title, markdown, hasImage} for exhibit n by reading its
    '## Exhibit N' section from case.md. Never returns benchmark content."""
    case_md = (packet / "case.md").read_text()
    pattern = re.compile(
        rf"^##\s+Exhibit\s+{n}\b[:.\-\s]*(?P<title>[^\n]*)\n(?P<body>.*?)(?=^#{{1,3}}\s|\Z)",
        re.MULTILINE | re.DOTALL)
    m = pattern.search(case_md)
    if not m:
        return None
    title = (m.group("title") or "").strip() or f"Exhibit {n}"
    body = m.group("body").strip()
    img = exhibit_image_path(packet, n)
    return {"n": n, "title": title, "markdown": body, "hasImage": img is not None}


def exhibit_image_path(packet: pathlib.Path, n: int) -> pathlib.Path | None:
    exdir = packet / "exhibits"
    if not exdir.is_dir():
        return None
    for ext in ("png", "jpg", "jpeg", "gif", "webp"):
        for name in (f"{n}.{ext}", f"exhibit-{n}.{ext}", f"exhibit{n}.{ext}"):
            p = exdir / name
            if p.is_file():
                return p
    return None


EXHIBIT_TOKEN = re.compile(r"^\s*\[EXHIBIT\s+(\d+)\]\s*$", re.MULTILINE)


def split_exhibits(packet: pathlib.Path, reply: str):
    """Strip [EXHIBIT n] tokens from the reply and resolve each to its content."""
    ns = [int(x) for x in EXHIBIT_TOKEN.findall(reply)]
    clean = EXHIBIT_TOKEN.sub("", reply).strip()
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    exhibits = []
    seen = set()
    for n in ns:
        if n in seen:
            continue
        seen.add(n)
        ex = resolve_exhibit(packet, n)
        if ex:
            exhibits.append(ex)
    return clean, exhibits


# ---------------------------------------------------------------------------
# runlog self-emit (degrades gracefully if the binary is missing)
# ---------------------------------------------------------------------------

class Runlog:
    def __init__(self):
        self.bin = shutil.which("runlog") or str(pathlib.Path.home() / ".local/bin/runlog")
        self.rid = None
        if not pathlib.Path(self.bin).exists():
            self.bin = None

    def _call(self, *args) -> str:
        if not self.bin:
            return ""
        try:
            return subprocess.run([self.bin, *args], capture_output=True, text=True,
                                  timeout=15).stdout.strip()
        except Exception:
            return ""

    def start(self, trigger: str):
        if self.bin:
            self.rid = self._call("start", "case-interviewer", "--trigger", trigger) or None

    def progress(self, label: str, fraction=None):
        if self.bin and self.rid:
            args = ["progress", self.rid, label]
            if fraction is not None:
                args += ["--fraction", str(fraction)]
            self._call(*args)

    def done(self, result: str):
        if self.bin and self.rid:
            self._call("done", self.rid, "--result", result)

    def error(self, reason: str):
        if self.bin and self.rid:
            self._call("error", self.rid, "--reason", reason)


# ---------------------------------------------------------------------------
# transcript + session file
# ---------------------------------------------------------------------------

def append_transcript(packet: pathlib.Path, role: str, text: str):
    f = packet / "transcript.md"
    if not f.exists():
        meta = parse_frontmatter((packet / "case.md").read_text())
        f.write_text(f"# Transcript: {meta.get('title','case')}\n\n"
                     f"Style: {meta.get('style','?')} | Difficulty: {meta.get('difficulty','?')} "
                     f"| Started: {date.today().isoformat()}\n\n")
    with f.open("a") as fh:
        fh.write(f"\n**{role}:** {text}\n")


def write_session_file(packet: pathlib.Path, scorecard: dict) -> pathlib.Path:
    """Persist the finished interview to Casing/sessions/<packet-name>.md."""
    SESSIONS.mkdir(parents=True, exist_ok=True)
    dest = SESSIONS / f"{packet.name}.md"
    meta = parse_frontmatter((packet / "case.md").read_text())
    transcript = (packet / "transcript.md")
    transcript_body = transcript.read_text() if transcript.exists() else "(no transcript)"
    uploads = sorted((packet / "uploads").glob("*")) if (packet / "uploads").is_dir() else []

    lines = [f"# {meta.get('title','Case')}: interview session", ""]
    lines.append(f"- Date: {date.today().isoformat()}")
    lines.append(f"- Style: {meta.get('style','?')} | Difficulty: {meta.get('difficulty','?')}")
    lines.append(f"- Packet: `{packet}`")
    lines.append("")
    lines.append("## Scorecard")
    lines.append("")
    lines.append(f"**Verdict: {scorecard.get('verdict','?')}** - {scorecard.get('clientTest','')}")
    lines.append("")
    for d in scorecard.get("dimensions", []):
        lines.append(f"### {d.get('name','?')}: {d.get('score','?')}/10 (weight {d.get('weight','?')}%)")
        for ev in d.get("evidence", []):
            lines.append(f"- {ev}")
        lines.append("")
    gates = scorecard.get("gates", {})
    if gates:
        lines.append("### Gate checks")
        for k, v in gates.items():
            lines.append(f"- **{k}:** {v}")
        lines.append("")
    if scorecard.get("strongAnswer"):
        lines.append("## What a strong answer would have looked like")
        lines.append("")
        lines.append(scorecard["strongAnswer"])
        lines.append("")
    if scorecard.get("drills"):
        lines.append("## Drills for next time")
        for dr in scorecard["drills"]:
            lines.append(f"- {dr}")
        lines.append("")
    if uploads:
        lines.append("## Uploads")
        for u in uploads:
            lines.append(f"- `{u.name}`")
        lines.append("")
    lines.append("## Full transcript")
    lines.append("")
    lines.append(transcript_body)
    dest.write_text("\n".join(lines))
    return dest


# ---------------------------------------------------------------------------
# HTTP handler
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    packet: pathlib.Path
    runlog: Runlog
    started_flag = {"v": False}

    def _send(self, code, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj).encode(), "application/json")

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw or b"{}")

    # -- GET --------------------------------------------------------------
    def do_GET(self):
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self._serve_page()
        m = re.fullmatch(r"/exhibit/(\d+)", path)
        if m:
            return self._serve_exhibit(int(m.group(1)))
        self._send(404, b"not found", "text/plain")

    def _serve_page(self):
        html = (SKILL_DIR / "interview.html").read_text()
        meta = parse_frontmatter((self.packet / "case.md").read_text())
        html = (html.replace("{{CASE_TITLE}}", meta.get("title", "Case interview"))
                    .replace("{{CASE_STYLE}}", meta.get("style", "interviewer-led"))
                    .replace("{{CASE_DIFFICULTY}}", meta.get("difficulty", "medium")))
        self._send(200, html.encode(), "text/html; charset=utf-8")

    def _serve_exhibit(self, n: int):
        img = exhibit_image_path(self.packet, n)
        if not img:
            return self._send(404, b"no image for exhibit", "text/plain")
        ctype = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                 "gif": "image/gif", "webp": "image/webp"}.get(img.suffix[1:].lower(),
                                                               "application/octet-stream")
        self._send(200, img.read_bytes(), ctype)

    # -- POST -------------------------------------------------------------
    def do_POST(self):
        try:
            if self.path == "/chat":
                return self._chat()
            if self.path == "/upload":
                return self._upload()
            if self.path == "/debrief":
                return self._debrief()
        except Exception as e:  # noqa: BLE001
            self.runlog.error(f"{self.path}: {e}")
            return self._json(500, {"error": str(e)})
        self._send(404, b"not found", "text/plain")

    def _mark_started(self):
        if not self.started_flag["v"]:
            self.started_flag["v"] = True
            self.runlog.progress("interview started", 0.1)

    def _chat(self):
        body = self._read_body()
        message = (body.get("message") or "").strip()
        if not message:
            return self._json(400, {"error": "empty message"})
        self._mark_started()
        if body.get("hint"):
            append_transcript(self.packet, "Candidate (hint request)", message)
            message = ("[The candidate is explicitly asking for a hint.] " + message)
        else:
            append_transcript(self.packet, "Candidate", message)
        reply = run_claude(self.packet, message)
        clean, exhibits = split_exhibits(self.packet, reply)
        note = f"  _[revealed exhibit {', '.join(str(e['n']) for e in exhibits)}]_" if exhibits else ""
        append_transcript(self.packet, "Interviewer", clean + note)
        if exhibits:
            self.runlog.progress(f"revealed exhibit {exhibits[-1]['n']}", 0.5)
        self._json(200, {"reply": clean, "exhibits": exhibits})

    def _upload(self):
        body = self._read_body()
        name = pathlib.Path(body.get("name") or "upload.png").name
        data = body.get("data") or ""
        caption = (body.get("caption") or "").strip()
        if "," in data and data.strip().startswith("data:"):
            data = data.split(",", 1)[1]
        try:
            blob = base64.b64decode(data)
        except Exception:
            return self._json(400, {"error": "bad base64 upload"})
        updir = self.packet / "uploads"
        updir.mkdir(exist_ok=True)
        dest = updir / f"{int(time.time())}-{name}"
        dest.write_bytes(blob)
        self._mark_started()
        label = f"[uploaded file: {name}]" + (f" {caption}" if caption else "")
        append_transcript(self.packet, "Candidate", label)
        instr = (f"[The candidate just uploaded a file. Read it at {dest} and react to it as their "
                 f"interviewer.]")
        if caption:
            instr += f" They said: {caption}"
        reply = run_claude(self.packet, instr)
        clean, exhibits = split_exhibits(self.packet, reply)
        append_transcript(self.packet, "Interviewer", clean)
        self._json(200, {"reply": clean, "exhibits": exhibits, "saved": dest.name})

    def _debrief(self):
        self.runlog.progress("debrief", 0.9)
        raw = run_claude(self.packet, DEBRIEF_INSTRUCTION)
        scorecard = extract_json(raw)
        dest = write_session_file(self.packet, scorecard)
        scorecard["savedTo"] = str(dest)
        self.runlog.done(str(dest))
        self._json(200, scorecard)

    def log_message(self, fmt, *args):  # quiet, but surface POSTs to stderr
        line = args[0] if args else ""
        if "POST" in line:
            sys.stderr.write("case-interviewer: %s\n" % line)


# ---------------------------------------------------------------------------
# server bootstrap
# ---------------------------------------------------------------------------

def serve(packet: pathlib.Path, port: int, open_browser=True):
    if not (packet / "case.md").exists():
        sys.exit(f"no case.md in packet {packet}")
    Handler.packet = packet
    Handler.runlog = Runlog()
    Handler.runlog.start(os.environ.get("RUNLOG_TRIGGER", "manual"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"case-interviewer: {packet.name} -> {url}  (ctrl-c to stop)")
    if open_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        Handler.runlog.error("interrupted")


def selftest() -> int:
    """Build a throwaway packet, start the server on an ephemeral port, drive one
    scripted /chat round-trip through real claude -p, assert a reply came back."""
    import tempfile
    import urllib.request

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="case-selftest-"))
    packet = tmp / f"{date.today().isoformat()}-selftest-tiny-widget"
    packet.mkdir(parents=True)
    (packet / "case.md").write_text(
        "---\ntitle: Tiny Widget Co\nstyle: interviewer-led\ndifficulty: easy\n---\n\n"
        "# Tiny Widget Co\n\n"
        "## Prompt\nWidgetCo wants to know if it should raise price. Objective: grow profit.\n\n"
        "## Exhibit 1: Unit economics\n\n| Metric | Value |\n|---|---|\n| Price | $10 |\n"
        "| Variable cost | $6 |\n\n"
        "## Benchmark\nContribution is $4/unit. (Secret: do not reveal.)\n")

    Handler.packet = packet
    Handler.runlog = Runlog()
    Handler.runlog.start("selftest")
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    ok = False
    try:
        # page renders
        page = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10).read().decode()
        assert "Tiny Widget Co" in page, "case title not injected into page"
        # one real chat round-trip
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/chat",
            data=json.dumps({"message": "Hi, I'm ready. Please give me the prompt."}).encode(),
            headers={"Content-Type": "application/json"})
        resp = json.loads(urllib.request.urlopen(req, timeout=600).read().decode())
        reply = resp.get("reply", "")
        print("selftest reply:", reply[:280])
        assert reply.strip(), "empty reply from interviewer"
        assert (packet / "transcript.md").exists(), "transcript not written"
        ok = True
    except Exception as e:  # noqa: BLE001
        print("selftest FAILED:", e)
    finally:
        httpd.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    print("selftest:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        sys.exit(__doc__)
    if args[0] == "--selftest":
        sys.exit(selftest())
    packet = pathlib.Path(args[0]).expanduser().resolve()
    port = int(args[1]) if len(args) > 1 else 4760
    serve(packet, port)


if __name__ == "__main__":
    main()
