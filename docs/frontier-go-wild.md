Quickstart:

```bash
npx skills add josephpogue/claude-skills --skill=frontier-go-wild
```

```bash
npx skills update frontier-go-wild
```

[Source](https://github.com/josephpogue/claude-skills/tree/main/skills/frontier-go-wild)

## What it does

`frontier-go-wild` checks Frontier **Go Wild** pass seats for an exact list of
one-way searches. Each search is an origin, a destination and a date; one set
of optional filters (max stops, max layover, latest arrival date) applies to
all of them. It reads each day on flyfrontier.com with the Go Wild pass
switched on, in the order given, and returns only the flights that pass, with
the Go Wild fee for each seat. It drives a real headless browser, so it never
invents fares.

## Before you run it

This is not a pure-prompt skill. On a new machine, run the included setup once:

```bash
bash ~/.claude/skills/frontier-go-wild/setup.sh
```

It installs `uv`, the Python dependency and Chromium, then checks the skill
loads and the browser opens a page. There is **no login and no credentials**.

## Run it

> check Go Wild MCO to PHL on March 14, nonstop only

The agent builds the list of reads, runs the skill and gets back one JSON
document: a status per read and the flights that passed, in 29 fixed columns.
