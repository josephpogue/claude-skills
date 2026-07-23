# case-interviewer

Run a **live consulting case interview** in your browser, with you as the
candidate and Claude as the interviewer. Say "case me" and the skill builds a
complete case, launches a local page, and plays a real McKinsey/Bain/BCG-style
interviewer: it states the prompt, holds facts back until you ask, reveals
exhibits at the right beat, gives hints only when you request them, and at the
end drops the persona to score you against a real grading rubric.

The interviewer never hands you the answer key. Every turn routes through the
`claude` CLI on your subscription (no API key), so the interview is a genuine
back-and-forth, not a scripted quiz.

This is a **self-contained, no-install** skill: a Python standard-library server
plus the `claude` CLI you already have. Nothing to `pip install`, no browser
toolkit, no credentials.

---

## What you need first

- **macOS or Linux** with `python3` (3.10+) and the `claude` CLI on your `PATH`
  (you have it — that's what's running this skill).

That's the whole list. The server is pure Python standard library.

---

## Install

### Option A — from the skills registry (recommended)

```bash
npx skills add josephpogue/claude-skills --skill=case-interviewer
```

This copies the skill folder to `~/.claude/skills/case-interviewer`. To update
later:

```bash
npx skills update case-interviewer
```

### Option B — local clone (for development)

```bash
git clone https://github.com/josephpogue/claude-skills.git
cd claude-skills
bash scripts/link-skills.sh   # symlinks every skill into ~/.claude/skills
```

There is no setup step. Once the folder is in `~/.claude/skills/`, the skill
works.

---

## Run it

Ask an agent that has the skill loaded. Five ways to get a case:

> case me                      *(invents a fresh, fully-footed case)*

> give me a hard McKinsey-style market entry case

> run a case interview on this: *(paste a whole case)*

> case me on ~/Downloads/some-case.pdf

> run the case at https://…

The first four words open a browser page at `http://127.0.0.1:4760/`. From
there everything happens on the page: chat with the interviewer, exhibits appear
inline as they're revealed, ask for a hint, upload a photo of your scratch work,
and hit **End interview** for a scored debrief (verdict, four weighted
dimensions with evidence quoted from your transcript, gate checks, a beat-by-beat
"what a strong answer looked like," and drills for next time).

The finished session — transcript plus scorecard — is saved as markdown so you
can review it later (see **Where sessions go** below).

---

## Bring your own case library (optional)

Out of the box the skill **invents** cases and can ingest anything you paste,
link, or point it at. If you keep your own indexed corpus of real cases, the
"named case" path (`run the McKinsey Electro-Light case`) can pull from it too.

Point the skill at your index with an environment variable:

```bash
export CASE_INTERVIEWER_INDEX=~/path/to/your/case-index.md
```

The index is a markdown table mapping a slug/name to a source file (and, for
casebook cases, a PDF page range). Without one, named-case lookups gracefully
fall back to inventing a fresh case in the same style — no error, nothing
breaks.

---

## Where sessions go

When you end an interview, the transcript + scorecard are written to a
**sessions root**, resolved in this order:

1. `$CASE_INTERVIEWER_SESSIONS` if set, else
2. `~/Documents/GitHub/My-Life/Casing/sessions` if that folder exists, else
3. `~/.claude/data/case-interviewer/sessions` (the default on a fresh machine).

---

## What's in this folder

| Path | What it is |
|------|-----------|
| `SKILL.md` | The operating manual the agent follows: parse the ask, build the case packet, launch the server. |
| `interviewer-server.py` | The local interview server (Python stdlib only). Serves the page and plays the interviewer through `claude -p`. |
| `interview.html` | The single-page browser UI: chat, exhibit rendering, hint button, upload, end-interview debrief. |
| `references/interviewer-playbook.md` | How the interviewer behaves in the room — injected into every turn. |
| `references/case-pattern-guide.md` | How to run an existing case faithfully and how to invent new ones that foot. |
| `references/grading-rubric.md` | The scoring rubric the debrief applies. |

---

## Privacy

Everything is local. The server binds to `127.0.0.1` only, and interviewer turns
run through your own `claude` subscription. No case content leaves your machine
except through the `claude` CLI you already use, and this repo contains no
secrets or personal case files.
