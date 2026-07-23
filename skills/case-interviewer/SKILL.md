---
name: case-interviewer
description: Run a live consulting case interview with the user as the interviewee and you as the interviewer, on an interactive browser page. Use when they say "case me", "run a case interview", "give me a mock case", "practice casing" (as the candidate), or name/paste a case to be interviewed on. Resolves or invents the case, then serves it.
---

# Case interviewer

You run a real consulting case interview. The user is the candidate; you are the interviewer. The interview happens on a local browser page that routes every interviewer turn through `claude -p` on the subscription. Your job in this skill is the setup: turn the ask into a complete **case packet**, then launch the server and hand the user the URL. Once the page is up, the interview runs there, not in this session.

Everything about HOW the interviewer behaves in the room lives in `references/interviewer-playbook.md` (the server injects it into every turn, so you do not perform the interview here). How to invent or absorb a case lives in `references/case-pattern-guide.md`. How the debrief is scored lives in `references/grading-rubric.md`.

**No install step.** This skill is self-contained: a Python standard-library server plus the `claude` CLI you already have. There is nothing to `pip install`. It writes sessions to a data directory it resolves at runtime (see Step 2), so it works on a fresh machine with zero setup.

## Step 1: Parse the ask

Classify the case **source** from the user's request:
- **Pasted text** in the message: an entire case written out.
- **File path**: a local file (PDF, markdown, image) holding a case.
- **URL**: a link to a case.
- **Named case**: a case title or slug from a personal case library. This path is **optional** — it only works if the user keeps their own indexed corpus. Resolve the index path as `$CASE_INTERVIEWER_INDEX` if set, else `~/Documents/GitHub/My-Life/Casing/resources/case-index.md`. If that index exists, grep it by keyword or slug to get the source file (and, for casebook cases, the PDF page). If no index is configured, tell the user you don't have that case indexed and offer to **invent** a fresh case in the same firm/style, or ask them to paste or link it.
- **No input**: they just want a case. You will invent one.

Read these optional args from the request, else default:
- **difficulty**: easy | medium | hard (default **medium**).
- **style**: interviewer-led (default) | interviewee-led (only if they ask). A supplied or indexed case keeps its OWN prescribed style regardless of this arg.
- **who**: the candidate name for the session filename (default **candidate**).

**Completion criterion**: source is classified into exactly one of the five kinds above, and difficulty/style/who are pinned to concrete values.

## Step 2: Build the case packet

First resolve the **sessions root** `<SESSIONS>` (this must match what the server uses):
1. `$CASE_INTERVIEWER_SESSIONS` if set, else
2. `~/Documents/GitHub/My-Life/Casing/sessions` if `~/Documents/GitHub/My-Life/Casing` exists, else
3. `~/.claude/data/case-interviewer/sessions`.

Create the packet directory `<SESSIONS>/.live/<YYYY-MM-DD>-<who>-<slug>/` (today's date; `<slug>` is the case's kebab-case slug, or an invented `<industry>-<type>` slug). Inside it author `case.md`, and `exhibits/` only if a source case ships image exhibits.

Resolve the source into `case.md`:
- **Named/indexed case**: read the source file named in the index. For a casebook PDF, Read only the case's page range. Restructure it faithfully into the `case.md` format below, keeping its prescribed style and its real numbers. Extract image exhibits into `exhibits/<n>.png` only when the source is genuinely a picture that cannot be a table; otherwise transcribe the exhibit as a markdown table.
- **Pasted / file / URL**: ingest it and restructure into `case.md` faithfully, preserving its own style, numbers, and exhibits.
- **No input**: **invent a brand-new case** with `references/case-pattern-guide.md` section 3. Follow it in order: pick a fresh industry (vary from recent picks, favor its underused list), pick type and the requested difficulty, invent a client, then choose the verdict first and build every number backward so the whole thing foots. Plant exactly one non-obvious insight, design 2 to 4 exhibits, and write benchmark answers for every beat. Before writing the file, **recompute every number independently and confirm it foots** (section 3.8 checklist); adjust an input if any answer lands ugly.

Write `case.md` in this structure so the server can address exhibits by number and the interviewer can find its benchmarks:

```
---
title: <client / case name>
style: interviewer-led | interviewee-led
difficulty: easy | medium | hard
---

# <Case title>

## Prompt
<2-5 sentences: client, industry, the decision, and the ONE explicit objective with a target number where natural.>

## Clarifying facts
<3-6 facts held back until asked; flag the load-bearing ones (scope, cost classification). Reveal-only-if-asked.>

## Beats
1. Structure: <the ask>
2. <first quant or exhibit read> (reveals Exhibit 1)
3. <brainstorm / judgment>
4. <optional second quant> (reveals Exhibit 2)
5. Synthesis / recommendation

## Exhibit 1: <title>
<markdown table with exact values>

## Exhibit 2: <title>
<markdown table>

## Benchmark: Beat 1
<guideline buckets; tiered good vs outstanding for structure and recommendation>

## Benchmark: Beat 2
<worded formula, then plugged-in arithmetic, then the so-what and a sense-check line>

<... one Benchmark section per beat ...>
```

Every `## Exhibit N` referenced by a beat must exist, and every exhibit must be referenced by exactly one beat. The `## Benchmark` sections are the interviewer's secret answer key; they must never leak to the candidate (the server never ships them to the page, and the playbook forbids stating them).

**Completion criterion**: `case.md` exists at the packet path with frontmatter (title, style, difficulty), a prompt with a stated objective, a clarifying-fact bank, a beat arc, one `## Exhibit N` section per exhibit referenced in the beats, and one `## Benchmark` section per beat. For an invented case, the math has been recomputed and foots, and exactly one insight is planted.

## Step 3: Launch the interview

Launch the server in the background and hand over the page:

```bash
cd ~/.claude/skills/case-interviewer
RUNLOG_TRIGGER=manual nohup python3 interviewer-server.py "<packet-dir>" 4760 > "<packet-dir>/server.log" 2>&1 &
```

The server opens the browser to `http://127.0.0.1:4760/` and serves the page. (If `runlog` is installed it also emits a `runlog start case-interviewer` heartbeat; if not, it silently skips it — the interview is unaffected.) Poll `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4760/` until it returns `200` (give it a couple of seconds; if the port is busy, relaunch on 4761 and adjust the URL). If it never comes up, read `<packet-dir>/server.log` for the error.

Then stop working and tell the user the case is live at the URL, naming the case title, style, and difficulty, and reminding them the interview (chat, exhibit reveals, hints, upload, and the End-interview debrief) all happen on the page. The saved session lands in `<SESSIONS>/` when they end the interview.

**Completion criterion**: `curl` returns 200 from the server and the user has the URL.
