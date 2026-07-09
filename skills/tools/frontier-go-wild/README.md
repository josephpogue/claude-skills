# frontier-go-wild

Find Frontier **Go Wild** seat availability day-by-day for one origin and one or
many destinations (specific cities, whole states, or semantic groups like
"east-coast" or "beach") across a date range, ranked cheapest-first with your
preferred transfer cities on top.

It drives a real headless browser into frontier.com, so it reports only real
availability and never invents fares. Output is a JSON scoreboard plus a
self-contained HTML report you can open without a server.

This is a **self-bootstrapping** skill: everything it needs to install ships in
this one folder. There is no separate setup skill. On a fresh machine you run
`setup.sh` once; after that, runs just work.

---

## What you need first

- **macOS or Linux** with `git`, `bash`, and `curl`. The installer pulls in
  everything else (`uv`, Python deps, Chromium) on its own.
- **A Frontier account** with a Go Wild pass (the account you want to search).
- **A Gmail inbox that receives your Frontier login codes**, plus a Google Cloud
  OAuth client with `gmail.readonly` scope for it. Frontier emails a fresh
  6-digit code on every login, and the skill reads it via the Gmail API. This is
  the one fiddly prerequisite (walkthrough below). The OTP reader is Gmail-only
  today; if your codes arrive at a non-Gmail address this path needs adapting.

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
   it reuses that (keeping its warm session); otherwise it vendors a copy to
   `~/.claude/tools/browser-pilot`. Either way it records the location in
   `~/.claude/data/frontier-go-wild/pilot-root` so the skill finds it on any
   machine.
2. Drops the `browser-pilot` agent definition at `~/.claude/agents/browser-pilot.md`
   and the `runlog` helper at `~/.local/bin/runlog` (only if you don't already
   have one).
3. Installs `uv`, the Python dependencies, and Chromium (first run takes a few
   minutes).
4. Prompts for the **two credentials** below.
5. Runs a headless smoke test and prints `✓ browser toolkit works`.

### The two credentials

Both are written only to your local, `chmod 600` `~/.config/credentials/store.toml`.
Nothing is ever committed to this repo or leaves your machine.

**1. Frontier login** — when prompted, enter the account email and password.
Lands in `[logins.frontier]`.

**2. Gmail OTP reader** — for the inbox that receives your Frontier codes you
need, from the Google Cloud Console:

- a project with the **Gmail API enabled**,
- an **OAuth client** (client id + secret),
- a **refresh token** minted with scope
  `https://www.googleapis.com/auth/gmail.readonly` — easiest via the
  [OAuth Playground](https://developers.google.com/oauthplayground) (in its
  settings, tick "Use your own OAuth credentials" and paste your client id/secret,
  authorize the `gmail.readonly` scope, then exchange for a refresh token).

Paste the Gmail address, client id, client secret, and refresh token when
prompted. They land in `[google.frontier_otp_gmail]` (the namespace the OTP
reader looks up by default).

If the smoke test fails, the usual cause is the Chromium install. Re-run
`setup.sh`.

---

## Run it

Once setup is done, just ask an agent that has the skill loaded:

> frontier go wild ATL to Boston next weekend

> frontier go wild DEN to the northeast, Aug 1-7, max 1 stop

The first real search warms the session with one OTP email (~1-2 minutes) and
caches the login. Later runs reuse the warm session and only re-authenticate
every ~20-25 minutes. If a run ever reports it needs a headed re-login, do one
interactive login and it re-caches.

You get back a per-destination, day-by-day scoreboard (JSON) and a self-contained
HTML report.

---

## For Claude / coding agents

If you're an agent asked to install and set this up end to end:

1. **Install** the folder (Option A or B above). Confirm `~/.claude/skills/frontier-go-wild/SKILL.md`
   exists.
2. **Run** `bash ~/.claude/skills/frontier-go-wild/setup.sh`. It is interactive:
   it prompts for the Frontier password and the Gmail OAuth values on stdin, so
   it needs a real terminal. If you're running non-interactively, do NOT try to
   pipe secrets in blind — instead tell the human exactly which four Gmail values
   and Frontier login to have ready, and have them run the one command themselves
   (in this harness they can type `! bash ~/.claude/skills/frontier-go-wild/setup.sh`).
3. **Never** write credentials anywhere except by letting `setup.sh` collect
   them into `~/.config/credentials/store.toml`. Don't echo them into logs.
4. **Verify** setup by confirming the installer printed `✓ browser toolkit works`
   and that `~/.claude/data/frontier-go-wild/pilot-root` exists and points at a
   real directory.
5. To actually run a search, follow `SKILL.md` in this folder — it's the full
   operating manual (destination resolution, worker fan-out, output schema).

---

## What's in this folder

| Path | What it is |
|------|-----------|
| `SKILL.md` | The operating manual the agent follows to run a search, including the `## Setup` section. |
| `setup.sh` | The one-time installer (toolkit + Chromium + credentials + smoke test). |
| `browser-pilot/` | The vendored browser-automation toolkit (`control.py`, Frontier recipe, deps). |
| `agent/browser-pilot.md` | The `browser-pilot` subagent definition the installer drops into `~/.claude/agents/`. |
| `bin/runlog` | Vendored run-logging helper installed to `~/.local/bin/`. |
| `frontier-network.json` | Airport metadata (state/region/tags) + semantic group lists used to resolve destinations. |
| `blackout-dates.json` | Known Go Wild blackout dates. |
| `render_report.py` | Builds the self-contained HTML report from the run's JSON. |
| `reference/` | Supporting reference material for the skill. |

---

## Where your credentials live

Everything sensitive stays in `~/.config/credentials/store.toml` on your machine
(mode `600`), written by `setup.sh`. This repo never contains secrets, and the
warm browser session lives under the toolkit's `state/` directory, not here.
