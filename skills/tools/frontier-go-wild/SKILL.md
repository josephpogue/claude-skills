---
name: frontier-go-wild
description: Find Go Wild seat availability day-by-day for a Frontier origin and one or MANY destinations (specific cities, states, or semantic groups like "East Coast" / "Beach") over a date range, ranked by fee with preferred transfer cities on top.
---

# frontier-go-wild

**Portability - resolve the browser-pilot toolkit root first.** Every
`browser-pilot` path in this document means `$PILOT_ROOT`. Resolve it as: the
contents of `~/.claude/data/frontier-go-wild/pilot-root` if that file exists,
else `~/Documents/GitHub/My-Life/automations/browser-pilot`, else
`~/.claude/tools/browser-pilot`. Recipes are at `$PILOT_ROOT/recipes/`, shared
auth state at `$PILOT_ROOT/state/frontier.json`, and workers run `control.py`
from `$PILOT_ROOT`. New-machine install: run the `/setup-frontier-go-wild`
skill (or `bash setup.sh` in this folder). It installs the vendored toolkit and
agent that ship alongside this skill and collects the two manual inputs — the
Frontier login and a Gmail OAuth client for the OTP reader, both landing in
`~/.config/credentials/store.toml`.

Given a Frontier origin, a destination list (specific cities, states, and/or
semantic groups), a date (or date range), and routing constraints, produce a
per-destination, day-by-day breakdown of which flights have a **Go Wild** seat
available - direct, or the best multi-hop route Frontier itself sells - ranked
with preferred transfer cities on top. Output is a single JSON object the
Mission Control page renders as a destination scoreboard + per-destination
day grids.

## Inputs (parse these from the request)

- `origin` - IATA code
- `destinations` - a LIST of raw tokens, each one of:
  - a specific city (IATA code or city name): `SFO`, `Boston`
  - a state: `wisconsin` (expands to its Frontier airports, e.g. MKE, MSN)
  - a semantic group: `east-coast`, `west-coast`, `beach`, `ski`, `florida`,
    `caribbean`, `midwest`, `west`, `texas`, `northeast` (see resolution below)
  - back-compat: a legacy single `destination` arg is treated as
    `destinations: [destination]`
- date or date range (`dateStart` … `dateEnd`)
- `maxStops` (0, 1, or 2)
- `layoverMin` / `layoverMax` (minutes) - a connection must fall in this window
- `maxTripHours` - first departure → final arrival must fit under this
- `preferredCities` - ordered list of IATA hubs; routes through earlier-listed
  cities rank higher (soft preference, never a hard filter)
- `cap` (optional) - bound for this run, either `{ "searches": N }` or
  `{ "minutes": N }`. **Default: no cap** - the run takes whatever
  destinations × days requires. A cap NEVER pre-trims the plan: run
  depth-first down the resolved list (step 2) and let the cap decide how far
  you get. Destinations not yet started when the cap expires are reported
  `unsearched` - visible, never silently dropped.
- `workers` - parallel browser workers per wave (default **8**). Auto-backoff:
  if a wave hits a captcha/block page or 2+ workers report logged-out, halve
  the fleet (floor 2) for later waves instead of aborting, and note the
  backoff in a progress event. Go above 8 only when the user explicitly asks -
  more parallel scrapers on one set of cookies = more anti-bot risk on the
  account. Measured limit (2026-07-08 ramp test, 24 GB / 14-core Mac): 16
  workers ran clean; 32 collapsed the fleet via RAM exhaustion (9.7 GB swap,
  daemons crashing) with ZERO anti-bot signals - the binding ceiling is
  machine memory, not Frontier. Treat 16 as the hard max on this machine.

## Step 0 - Resolve destinations (before any account touch)

Load `~/.claude/skills/frontier-go-wild/frontier-network.json` (airports with
state/region/tags, plus explicit `groups` lists).

- IATA codes and city names → validate against `airports`; pass through.
- State names → all airports whose `state` matches.
- Group tokens → the matching `groups` list.
- Free text that matches nothing (e.g. "somewhere warm") → expand with your own
  judgment, but **only to IATA codes present in the file**, and record the
  expansion in the output like any group.
- Dedupe across tokens (first token to claim a code wins its `resolvedFrom`).
- Drop the origin itself if a group expansion includes it.
- **Intersect group/state expansions with the origin's served markets** so a
  group doesn't balloon into searches Frontier can't sell: fetch
  `flights.flyfrontier.com/en/flights-from-<origin-city>` (public marketing
  page, route links `/en/flights-from-<origin>-to-*`, no login) and keep only
  expanded codes present there. If the fetch fails, keep the full expansion
  (the search itself will mark misses `unserved`). Cities the user named
  explicitly are NEVER dropped by this filter - they get searched as asked.

**Self-heal:** if `updatedAt` is older than `staleAfterDays`, or a token fails
to resolve, fetch Frontier's own route pages (the `sources` in the file - the
city-to-city sitemap lists every route pair on one page, and
`flights.flyfrontier.com/en/flights-from-<origin-city>` lists the origin's
markets) and rewrite `frontier-network.json` with a refreshed `updatedAt`.
If the fetch fails, continue with the cached file - a stale entry costs one
cheap page load and gets flagged, never hidden.

Resolution honesty is part of the contract: the output's
`query.destinationsInput` records every raw token, its kind, and exactly which
codes it resolved to. A destination Frontier turns out not to serve from the
origin is marked `unserved: true` in the result - visible, not dropped.

**Estimate before running:** searches = resolved destinations × days. At ~45-75s
of worker time per search across `workers` parallel workers, wall-clock ≈
searches/workers minutes (+ ~2 min warm-up), with a session re-warm expected
roughly every ~20-25 min. If a cap is set and the estimate exceeds it, emit a
progress event saying how many destinations should complete before expiry and
proceed - never shrink the plan up front.

## Run logging (heartbeat)

Self-emit lifecycle events so a dashboard (e.g. Mission Control) can tell a
working run from a stalled one (absolute path - launchd PATH may be bare). The
`runlog` helper ships with this skill: `setup.sh` installs the vendored copy
(`bin/runlog`) to `~/.local/bin/runlog` when the machine has none. If
`~/.local/bin/runlog` is somehow still missing at run time, skip run-logging
and continue the search - never fail a run over the heartbeat. Find the active
run id first: `$RUNLOG_RUN_ID` if set, else the newest
`~/.claude/run-logs/frontier-go-wild/*.jsonl` containing a `start` but no
`done`/`error`; only if neither exists,
`rid=$(~/.local/bin/runlog start frontier-go-wild --trigger "${RUNLOG_TRIGGER:-manual}")`.

- After EVERY wave and every re-warm:
  `~/.local/bin/runlog progress "$rid" "<label>" --fraction <searchesDone/searchesTotal>`
  with a label like `"BOS done | 3/12 dests | 41/120 searches | 2 requeued"`.
- If the launcher did not log `done`/`error` itself, emit `done` (with a one-line
  `--result`) or `error` (with `--reason`) at the end.

A run that goes more than ~5 minutes without a progress event is
indistinguishable from a dead one on the dashboard - the heartbeat is part of
the contract, not decoration.

## How to get the data (real lookup - do NOT invent availability)

The availability comes from frontier.com via the already-built browser tooling.
**Never fabricate flights, fees, or times.** If you cannot get real data, say so
explicitly (the page will show your message).

The lookup runs **headless** (e.g. from Mission Control). The unit of work is
**one destination × one day** = one independent search. The one search-flow fact
every worker needs: on `booking.flyfrontier.com/Flight/Select`, click the
`text=GoWild!™` fare pill, then an itinerary has a Go Wild seat when its tiles
show `$<fee> One-way` (anchor `text="One-way"`) and none when they read
`Unavailable`. The GoWild pill itself is a day-level signal: a literal `--`
pill means ZERO Go Wild availability for that whole day - record it and move
on without row parsing. The saved recipe is at
`$PILOT_ROOT/recipes/frontier.json` (resolve `$PILOT_ROOT` per the portability
header above).

1. **Warm one shared session first (one login, never N in parallel).** Dispatch
   a single `browser-pilot` to start a daemon with the saved session
   (`serve --profile frontier --headless --state $PILOT_ROOT/state/frontier.json`),
   confirm it's logged in (snapshot shows "Hi, <account> / a miles balance"), and -
   only if it's logged out ("log in | sign up") - re-login via the recipe (creds
   from the vendored `creds.py` - `uv run python creds.py frontier --field
   username` / `--field password` from `$PILOT_ROOT`; OTP `gmail_otp.py`) and
   `save_state` to refresh
   `state/frontier.json`. This guarantees a single fresh auth file before any
   fan-out, so the parallel workers never trigger competing OTP logins.

2. **Fan out DESTINATION-MAJOR, in waves of ≤ `workers` parallel
   `browser-pilot` workers.** Treat the resolved list as an ordered QUEUE:
   one worker owns ONE destination and loops its dates via the deep link
   (`https://booking.flyfrontier.com/Flight/InternalSelect?o1=<ORIG>&d1=<DEST>&dd1=YYYY-MM-DD&ADT=1&mon=true&promo=`,
   ~6-8s grid render per date), and when it finishes it takes the next
   unstarted destination. **Depth-first completion is the contract:** a
   destination is finished only when EVERY date in the range has a real
   result - its owner retries failed/flaky dates before moving on. Under a
   cap, a fully-finished subset beats universal partials. With fewer
   destinations than workers, day-slice the longest range instead so all
   workers stay busy (the single-destination case degrades to exactly the old
   behavior). Dispatch each wave's workers **in one message so they run
   concurrently**, each:
   - on the **Haiku** model (the per-date scrape+parse is mechanical; the cheap
     model does the token-heavy browser work, this orchestrator stays on its
     model to assemble);
   - with its **own profile** `frontier-w{i}` but restoring the **shared**
     `--state .../state/frontier.json` - different profiles = independent
     daemons/sockets, same auth cookies, so all are logged in from the one warm
     session;
   - told to **NOT attempt an OTP re-login** - the session is already warm. If
     a worker finds itself logged out, it must report that and stop, not log in
     (so N workers can never OTP-storm the account);
   - told to read each date through the recipe flow (deep link → GoWild pill →
     snapshot) and parse the snapshot with judgment. Do NOT write ad-hoc
     scraper scripts - regex-over-snapshot parsing loses flight numbers and
     breaks on layout drift;
   - told flight numbers are OPTIONAL: Frontier renders them in a details
     modal that does not serialize to the text snapshot, so record the
     itinerary with `"flight": ""` when the number is not in the row text -
     never fail a date over flight numbers, and never open details modals for
     them (too slow). Fee, stops, stop cities, and leg dep/arr times are the
     required fields; a date-level pill fee with empty itineraries still beats
     a missing date;
   - told the itinerary SHAPE is a hard contract, checked before the row is
     emitted: a row with N stops serializes to exactly `N+1` legs that chain
     `origin → stop1 → … → destination` (a nonstop is 1 leg `origin →
     destination`; a 1-stop is 2 legs whose middle airport equals the single
     `stopCities` entry), and `stopCities` lists those N stop airports in order.
     Emit every `dep`/`arr` as 24-hour `HH:MM` (convert `5:30 AM` → `05:30`,
     `1:38 PM` → `13:38`). If any segment of a connection can't be read from the
     row, DROP that itinerary and keep the well-formed ones for the same date -
     a clean nonstop plus a dropped bad connection beats a partial 1-leg
     "connection", and the date still counts as fully searched;
   - told to re-issue the full deep link fresh for every date (never navigate
     within the page - destination state drifts) and to verify the header
     shows the assigned city pair before parsing.

   **Wave checkpoint (this is how long runs survive):** between waves, the
   orchestrator health-checks the shared session (cheap snapshot). If it has
   expired, the orchestrator re-warms it exactly as in step 1 - ONE serialized
   re-login + `save_state` - before dispatching the next wave. Re-warms are
   normal on runs past ~20-25 min: a long run costs an extra OTP email or two,
   serialized, never parallel. If a worker reports logged-out mid-wave, absorb
   that wave's losses, re-warm at the checkpoint, and re-run only the missing
   (destination, date) pairs in the next wave.

   **Each worker does ONE search per date - `origin → destination`
   directly.** Frontier's results page already lists the nonstops AND the
   connecting itineraries it actually sells, each as a single row with its own
   Go Wild price and real stop city/cities (e.g. `... 1 Stop RDU ...` with
   `$<fee> One-way`). Do NOT loop over individual legs or per-hub searches.
   Each worker returns, per date, every itinerary Frontier shows with: its Go
   Wild fee (the leftmost/Basic-Fare `$<fee> One-way` tile, or `Unavailable`),
   stop count, stop city/cities, each segment's dep/arr times and flight
   number, and which dates have no Go Wild seat at all.

3. **Merge per destination**, then from those **itineraries Frontier
   returned**, build each destination's route list - do not synthesize
   connections yourself. First **validate each row's shape as a backstop** (the
   workers are on a cheap model and occasionally emit a malformed connection):
   drop any itinerary whose leg count ≠ `stops + 1` or whose legs don't chain
   `origin → … → destination`, and normalize any non-`HH:MM` times before
   ranking. A dropped malformed row never hides a real option, since a genuine
   nonstop for that date is cheaper and survives the check. Then:
   - Nonstops with a Go Wild seat (always rank above connections).
   - For `maxStops ≥ 1`, keep each connecting itinerary Frontier returned whose
     stop count ≤ `maxStops`, whose layover (its segments' arr→dep gap) falls in
     `layoverMin`…`layoverMax`, and whose first-dep→final-arr fits
     `maxTripHours`.
   - The route's Go Wild fee is the **itinerary's own single Go Wild fee as
     shown by Frontier** - never a sum of separate legs (Frontier through-prices
     the connection; summing invents a fare that isn't bookable).
   - `transferCities` = the stop city/cities from that itinerary's row.
4. **Rank** within each destination: per day, direct first; then routes whose
   connecting city appears earliest in `preferredCities`; then fewer stops;
   then shorter total time. Mark the rank-1 route per day and keep at most the
   **top 4 routes per day per destination** (bounds the output JSON). Pick each
   destination's `best` (lowest fee across its range, ties broken by
   preferred-hub then time) and the single `overallBest` across all
   destinations. **Order the `destinations` array cheapest-first** (by that
   best fee); destinations with zero availability go after all available ones;
   `unserved` entries last.
5. **Cross-check blackout dates - once for the whole run** (dates are shared
   across destinations). Load the bundled list at
   `~/.claude/skills/frontier-go-wild/blackout-dates.json`. For each day of
   each destination, set `blackout: true` when the day's date (the flight's
   **departure** date) is in `blackoutDates` - a red-eye departing on a
   blackout date is flagged even though it lands the next day. Blackout **never
   removes** a day's routes: if Frontier showed a Go Wild fare on a blackout
   date, keep it and let the warning stand beside it (that discrepancy is the
   point). Fill the top-level `blackoutInRange` (every blacked-out date inside
   the search range) and `blackoutMeta` (`passLabel`, `source`, `stale`).
   **Self-heal when the list runs out:** if any searched date is later than the
   config's `coversThrough` (or the file is missing), do a quick web lookup of
   Frontier's current published GoWild blackout dates, use those for this run,
   and **rewrite `blackout-dates.json`** with the new window. If the lookup
   can't be done, still emit results but set `blackoutMeta.stale: true` -
   never silently drop the check.

**Reliability:** Frontier sessions are short-lived, so the warm-up in step 1
often has to re-login (~1-2 min OTP) - that's normal, not a failure. On
multi-wave runs, expect a re-warm roughly every 20-25 minutes at a wave
checkpoint; that is designed-for behavior, not an error. A single worker dying
(or reporting logged-out) must not sink the run: take what returned, re-warm,
and keep re-queuing the missing (destination, date) pairs at each wave
checkpoint until they fetch or the cap expires. Still emit valid JSON covering
**every** resolved destination and **every** date in the range. A date that
was never actually fetched is `available: false` PLUS `"unfetched": true` and
a `note` - never disguised as a searched no-availability day. A destination
never started gets `"unsearched": true`, empty days, and a note.

## Self-transfer mode (two separate bookings)

When the user asks for self-transfer / two-leg / separate-booking options (or
asks "did you check leg pairs?"), ALSO search synthesized connections — the one
sanctioned exception to "never synthesize connections." Follow the full branch
in [`reference/self-transfer.md`](reference/self-transfer.md): it defines the
middle-city intersection, the standalone per-leg searches, same-date pairing,
the additive `leg1 + leg2` fee, and the `"selfTransfer": true` marking and
ranking. Ordinary runs skip this section entirely.

## Output (REQUIRED - this is what renders)

Your final message MUST be **only** a ```json fenced block containing one object
matching this exact `FrontierMultiResultData` schema (no prose before or after -
the page parses it). **Always emit this multi shape, even for a single
destination.** Use real values from the lookup. `totalMinutes` is the whole trip
in minutes; times are `"HH:MM"`; include every date in the range for every
destination, with `available: false, routes: []` for days with no Go Wild seat.

**Do NOT narrate in the final turn.** All merging, constraint-filtering, and
ranking reasoning happens in your working turns (tool calls) - never in the
final message. The last message opens with ```` ```json ```` and closes with
```` ``` ```` and contains nothing else. A prose preamble is a contract
violation even though the page tolerates it.

The full `FrontierMultiResultData` example object and the per-field notes live
in [`reference/output-schema.md`](reference/output-schema.md) — load it when you
assemble the final message and match it exactly. It documents every field
(`type`, `stops`, `preferred`, `weekday`, `resolvedFrom`, `blackout`,
`unserved`, `unsearched`, `unfetched`), the cheapest-first `destinations`
ordering, and the chronological `days` ordering.

## Local HTML report (works without Mission Control)

After emitting the final JSON, ALSO persist and render it (this never replaces
the final-message contract above - the page still parses the chat output):

1. Write the result JSON to
   `~/.claude/data/frontier-go-wild/runs/<run-id>.json` (use the runlog run id).
2. Render the self-contained report:
   `python3 ~/.claude/skills/frontier-go-wild/render_report.py <that>.json`
   (writes the sibling `.html` - all CSS/JS/data inline, no server needed).
3. When the run is interactive (trigger `manual`, not `dashboard`/`scheduled`),
   `open` the HTML so the user sees the scoreboard immediately; otherwise just
   log the path in the runlog `done` result.

The report renders the same story as Mission Control: summary hero, partial-
coverage banner (unfetched/unsearched are labeled, never hidden), cheapest-first
destination scoreboard, per-destination day grids, blackout flags, and the
`limitTest` panel when present.

## If the lookup can't run

If login/availability can't be retrieved (e.g. the browser session needs a
one-time headed re-login), do **not** emit fake data. Instead return a short,
plain explanation of what blocked it and what's needed - the Mission Control
page surfaces that message to the user instead of showing a blank panel.
