Quickstart:

```bash
npx skills add josephpogue/claude-skills --skill=frontier-go-wild
```

```bash
npx skills update frontier-go-wild
```

[Source](https://github.com/josephpogue/claude-skills/tree/main/skills/tools/frontier-go-wild)

## What it does

`frontier-go-wild` finds Frontier **Go Wild** seat availability day-by-day for
one origin and one or many destinations (specific cities, states, or semantic
groups like "northeast" or "beach") across a date range, ranked cheapest-first
with your preferred transfer cities on top. It drives a real headless browser
into frontier.com, so it reports only real availability and never invents fares.

## Before you run it

This is not a pure-prompt skill. It needs a browser toolkit and two
credentials, so run its onboarding skill once first:

```bash
npx skills add josephpogue/claude-skills --skill=setup-frontier-go-wild
```

Then run `/setup-frontier-go-wild` in your agent. It installs the browser
toolkit and collects your Frontier login plus a Gmail OAuth client for reading
the login OTP. All credentials stay in your local `~/.config/credentials/store.toml`.

## Run it

> frontier go wild ATL to the northeast next week

It returns a per-destination, per-day scoreboard and also writes a
self-contained HTML report you can open without any server.
