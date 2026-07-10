# frontier-go-wild

Find Frontier **Go Wild** seat availability day-by-day for one origin and one or
many destinations (specific cities, whole states, or semantic groups like
"east-coast" or "beach") across a date range, ranked cheapest-first with your
preferred transfer cities on top.

It drives a real headless browser into frontier.com, so it reports only real
availability and never invents fares. Output is a JSON scoreboard plus a
self-contained HTML report you can open without a server.

This is a **self-bootstrapping** skill: everything it needs to install ships in
this one folder. There is no separate setup skill, **no login, and no
credentials** - Go Wild availability renders on frontier.com's public booking
page for logged-out visitors (verified 2026-07-09). On a fresh machine you run
`setup.sh` once to install the browser toolkit; after that, runs just work.

---

## What you need first

- **macOS or Linux** with `git`, `bash`, and `curl`. The installer pulls in
  everything else (`uv`, Python deps, Chromium) on its own.

That's it. No Frontier account, no login, and no Gmail/OAuth setup - the skill
reads the public Go Wild fare grid without signing in.

---

## Install

### Option A — from the skills registry (recommended)

```bash
npx skills add josephpogue/claude-skills --skill=frontier-go-wild
```

This copies the skill folder to `~/.claude/skills/frontier-go-wild`. To update
later:

```bash
npx skills update frontier-go-wild
```

### Option B — local clone (for development)

```bash
git clone https://github.com/josephpogue/claude-skills.git
cd claude-skills
bash scripts/link-skills.sh   # symlinks every skill into ~/.claude/skills
```

Either way, installing only copies files. Do the one-time setup next.

---

## Setup (run once per machine)

```bash
bash ~/.claude/skills/frontier-go-wild/setup.sh
```

The installer is idempotent: re-running it skips anything already in place, so
it's safe to run again if a step fails partway. It:

1. Installs the `browser-pilot` toolkit (the `control.py` daemon + Frontier
   recipe). If you already have a live `~/Documents/GitHub/My-Life/automations/browser-pilot`,
   it reuses that (without clobbering your existing install); otherwise it
   vendors a copy to `~/.claude/tools/browser-pilot`. Either way it records the
   location in `~/.claude/data/frontier-go-wild/pilot-root` so the skill finds it
   on any machine.
2. Drops the `browser-pilot` agent definition at `~/.claude/agents/browser-pilot.md`
   and the `runlog` helper at `~/.local/bin/runlog` (only if you don't already
   have one).
3. Installs `uv`, the Python dependencies, and Chromium (first run takes a few
   minutes).
4. Runs a headless smoke test and prints `✓ browser toolkit works`.

There are **no prompts** - the skill reads Go Wild availability off the public
booking page logged out, so no login or credentials are collected. If the smoke
test fails, the usual cause is the Chromium install. Re-run `setup.sh`.

---

## Run it

Once setup is done, just ask an agent that has the skill loaded:

> frontier go wild ATL to Boston next weekend

> frontier go wild DEN to the northeast, Aug 1-7, max 1 stop

There's no warm-up and no login step - each search hits the public booking page
directly, so results start coming back right away.

You get back a per-destination, day-by-day scoreboard (JSON) and a self-contained
HTML report.

---

## For Claude / coding agents

If you're an agent asked to install and set this up end to end:

1. **Install** the folder (Option A or B above). Confirm `~/.claude/skills/frontier-go-wild/SKILL.md`
   exists.
2. **Run** `bash ~/.claude/skills/frontier-go-wild/setup.sh`. It is
   non-interactive - no prompts, no credentials. It installs the toolkit +
   Chromium and runs a smoke test. It just needs network access and a few
   minutes for the first Chromium download.
3. **Verify** setup by confirming the installer printed `✓ browser toolkit works`
   and that `~/.claude/data/frontier-go-wild/pilot-root` exists and points at a
   real directory.
4. To actually run a search, follow `SKILL.md` in this folder — it's the full
   operating manual (destination resolution, worker fan-out, output schema).
   Workers run logged out against the public booking page; there is no login to
   perform or session to warm.

---

## What's in this folder

| Path | What it is |
|------|-----------|
| `SKILL.md` | The operating manual the agent follows to run a search, including the `## Setup` section. |
| `setup.sh` | The one-time installer (toolkit + Chromium + smoke test; no credentials). |
| `browser-pilot/` | The vendored browser-automation toolkit (`control.py`, Frontier recipe, deps). |
| `agent/browser-pilot.md` | The `browser-pilot` subagent definition the installer drops into `~/.claude/agents/`. |
| `bin/runlog` | Vendored run-logging helper installed to `~/.local/bin/`. |
| `frontier-network.json` | Airport metadata (state/region/tags) + semantic group lists used to resolve destinations. |
| `blackout-dates.json` | Known Go Wild blackout dates. |
| `render_report.py` | Builds the self-contained HTML report from the run's JSON. |
| `reference/` | Supporting reference material for the skill. |

---

## Privacy

The skill needs no login and stores no credentials - it only reads the public
Go Wild fare grid on frontier.com. Nothing sensitive is written anywhere, and
this repo contains no secrets.
