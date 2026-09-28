# frontier-go-wild

Check Frontier **Go Wild** pass seats for an exact list of one-way searches.
Give it origin, destination and date for each search, plus optional filters
(max stops, max layover, latest arrival date). It reads each day on
flyfrontier.com with the Go Wild pass switched on, top to bottom, and returns
only the flights that pass, each with the Go Wild fee for the seat.

It drives a real headless browser, so it reports only what Frontier shows. It
needs **no Frontier account, no login and no credentials**.

## What you need

- macOS or Linux with `bash` and `curl`. Setup installs the rest: `uv`, Python
  if needed, the `patchright` package and a Chromium build.

## Install

```bash
npx skills add josephpogue/claude-skills --skill=frontier-go-wild
```

Then run the setup once, from the installed folder (usually
`~/.claude/skills/frontier-go-wild`):

```bash
bash ~/.claude/skills/frontier-go-wild/setup.sh
```

It installs the dependencies and Chromium, checks the skill loads, and checks
the headless browser can open a page. Re-running it is safe.

## Use it

Ask your agent, for example:

> check Go Wild MCO to PHL on March 14, nonstop only

The agent turns that into a list of reads and runs the skill. To run it by
hand, from the skill folder:

```bash
uv run python search.py < examples/input.json > output.json
```

`SKILL.md` documents the input, the output columns and the run in full.

## Be gentle with Frontier

The skill paces itself at one request every twenty seconds with one browser.
Frontier blocks an IP after about 35 requests in a window; the skill waits one
15 minute cooldown out by itself and stops the run on a second block, keeping
everything it read. Keep lists short, and only one live run can go at a time
per machine.

## Where it writes

Everything goes under `~/.claude/data/`, never into the skill folder:

| Path | What |
|------|------|
| `~/.claude/data/frontier-go-wild/cache/` | The latest saved copy of each day page (reused within `max_age_hours`) |
| `~/.claude/data/frontier-go-wild/history/` | Every live read, kept as price history |
| `~/.claude/data/frontier-go-wild/browser-profiles/` | The browser profile |
| `~/.claude/data/frontier-go-wild/logs/linear/` | One result file per run |
| `~/.claude/data/flight-search/locks/` | The one-live-run lock |

Set `BROWSER_PROFILES_DIR`, `FLIGHT_LOGS_DIR` or `FLIGHT_LOCKS_DIR` to move
those. If a `runlog` command is on your `PATH` the run reports its progress to
it; without one it simply runs.

## What's in this folder

| Path | What |
|------|------|
| `SKILL.md` | The operating manual the agent follows |
| `setup.sh` | One-time setup |
| `search.py` | The entry point |
| `flight-search/` | The linear run, the Go Wild reader and the output columns |
| `browser-pilot/` | The small browser daemon the reader drives |
| `pyproject.toml`, `uv.lock` | Python dependencies |
| `examples/input.json` | A sample input |

The code in `search.py`, `flight-search/` and `browser-pilot/` is generated
from the maintainer's source repo and is not edited here.
