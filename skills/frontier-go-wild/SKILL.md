---
name: frontier-go-wild
description: Reads an exact list of one-way Frontier Go Wild pass searches (origin, destination, date) top to bottom on flyfrontier.com and returns only the flights that pass your filters (max stops, max layover, latest arrival date), with the Go Wild fee for each seat. Use when someone with a Frontier Go Wild pass asks which Go Wild seats exist on given routes and days, e.g. "check Go Wild ATL to DEN on Oct 20", "any Go Wild seats MCO to PHL next Friday, nonstop only".
---

# Frontier Go Wild

Reads flyfrontier.com with the Go Wild pass switched on, one day page per item of the list, in the order given. It never skips, reorders, ranks or combines. Deciding what to read and what to do with the flights belongs to the caller: turn the user's request into the list of reads, run it, then present the flights.

## Setup

Run once per machine (installs `uv` if missing, the Python dependency, and a Chromium for the browser; no login, no credentials):

```
bash setup.sh
```

## Run

From this skill's folder:

```
uv run python search.py [--saved-only] < input.json > output.json
```

`--saved-only` answers from pages saved by earlier runs and never opens a browser. `max_age_hours` still applies to it. Progress goes to stderr.

## Input

```json
{
  "reads": [
    {"origin": "MCO", "destination": "PHL", "date": "2030-03-14"},
    {"origin": "PHL", "destination": "MCO", "date": "2030-03-17"}
  ],
  "filters": {"max_stops": 1, "max_layover_minutes": 240, "latest_arrival_date": "2030-03-17", "cabin": "economy"},
  "max_age_hours": 6
}
```

- `reads`: one-way searches, read in exactly this order. Airports are IATA codes.
- `filters`: all four are optional, and the one set applies to every read. `latest_arrival_date` is the local date at the destination. `cabin` is `economy`, `premium`, `business` or `first` (default `economy`).
- `max_age_hours`: how old a saved page may be and still be used. Left out, any age is used; `0` reads everything live.
- Any other key is refused.

## Output

One JSON document on stdout, also saved to `~/.claude/data/frontier-go-wild/logs/linear/`. Read `status` first: `ok`, `stopped` (Frontier blocked twice; everything read so far is kept) or `refused` (bad input, or another live run is going). All three carry the same keys, so an empty `flights` list alone does not mean there were no seats.

- `reads`: one entry per input read, in order, with `status` (`read`, `failed`, `not_reached`, `not_applicable`), `source` (`live` or `saved`), `found`, `passed`, a `dropped` count per filter, and a `note`. `found` is always `passed` plus the sum of `dropped`.
- `flights`: only the flights that passed, read by read, in the order Frontier printed them. Nothing is sorted.

Every flight has these columns: `read_index`, `platform` (`frontier-go-wild`), `price_type` (`gowild`), `origin`, `destination`, `depart_date`, `depart_time`, `arrive_date`, `arrive_time`, `duration_minutes`, `stops`, `routing`, `layovers` (`{airport, airport_name, minutes}` per stop), `layovers_known`, `layover_filter_by`, `airlines`, `flight_numbers`, `segments` (one per flight, clocks local to each airport), `cabin`, `price_usd`, `points`, `fees_usd`, `fees_known`, `program`, `ticketing`, `times_known`, `booking_url`, `source`, `saved_age_hours`. Times are local with their UTC offset when the airport's zone is known.

`price_usd` is the Go Wild fee for the seat: what a pass holder pays. The price of the pass is not in the row. `points`, `fees_usd` and `program` are `null`.

A flight is returned only when it is shown to pass every filter. Filters are tried in this order, and a flight left out counts under the first it failed: `max_stops`, `layover_unknown`, `max_layover`, `arrival_unknown`, `latest_arrival`, `cabin`.

Exit code 0 is a run that reached the end of its list, 1 a stopped run, 2 a refused run. A run can end `ok` with failed reads in it, so check each read's `status`.

## What to know

- A day with no Go Wild seat is a real answer: the read is `read` with zero flights and a `note`.
- The day page shows no flight numbers (Frontier keeps them behind each row's Details link), so `flight_numbers` is empty.
- Go Wild sells economy seats only. With any other cabin every read is `not_applicable` and no browser opens.
- Go Wild seats open close to departure, so a saved page goes stale fast. Set `max_age_hours` low for dates inside the next two weeks.
- A read that fails is marked `failed` with a `note`, and the run goes on to the next read.
- One headless browser, twenty seconds between requests. Frontier blocks an IP after about 35 requests. The reader waits one cooldown (15 minutes) out by itself; a second block stops the run. Keep lists short and never run bursts.
- Only one live run at a time per machine; a second is refused with exit code 2. A `--saved-only` run is never held back.
- Everything it writes (saved pages, price history, the browser profile, result files) lives under `~/.claude/data/`, never in the skill folder.
