Quickstart:

```bash
npx skills add josephpogue/claude-skills --skill=case-interviewer
```

```bash
npx skills update case-interviewer
```

[Source](https://github.com/josephpogue/claude-skills/tree/main/skills/case-interviewer)

## What it does

`case-interviewer` runs a live consulting case interview in your browser — you're
the candidate, Claude is the interviewer. Ask an agent that has the skill loaded
to "case me" and it builds a complete case, launches a local page, and plays a
real McKinsey/Bain/BCG-style interviewer: states the prompt, holds facts back
until you ask, reveals exhibits at the right beat, gives hints only on request,
and at the end scores you against a grading rubric with evidence quoted from your
own transcript.

Five ways to seed a case: **invent** a fresh one on demand, **paste** a case into
chat, hand it a **file path** (PDF/markdown/image), give it a **URL**, or — if
you keep your own indexed case library — name a specific case.

## Before you run it

Nothing to install. This is a self-contained skill: a Python standard-library
server plus the `claude` CLI you already have. No `pip install`, no browser
toolkit, no credentials, no setup script. Once the folder is in
`~/.claude/skills/`, it works.

## Run it

> case me

> give me a hard McKinsey-style market entry case

> run a case interview on this: *(paste a case)*

It opens a page at `http://127.0.0.1:4760/` where the whole interview happens —
chat, exhibit reveals, hints, uploads, and the End-interview debrief. The saved
session (transcript + scorecard) lands under a local sessions directory
(`~/.claude/data/case-interviewer/sessions` by default; override with
`$CASE_INTERVIEWER_SESSIONS`). To wire in your own case corpus for named-case
lookups, set `$CASE_INTERVIEWER_INDEX`.
