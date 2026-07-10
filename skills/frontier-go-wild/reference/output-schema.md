# Output schema — `FrontierMultiResultData`

Disclosed reference for [`frontier-go-wild`](../SKILL.md), reached from the
`## Output` step when assembling the final message. The output contract itself
(final message is only the fenced json block, no prose, always the multi shape)
lives in SKILL.md; this file is the concrete example and the per-field notes.

```json
{
  "query": {
    "origin": "ATL",
    "destinationsInput": [
      { "input": "SFO", "kind": "city", "resolved": ["SFO"] },
      { "input": "east-coast", "kind": "group", "resolved": ["BOS", "PHL", "BWI"] },
      { "input": "wisconsin", "kind": "state", "resolved": ["MKE", "MSN"] }
    ],
    "dateStart": "2026-07-11", "dateEnd": "2026-07-13",
    "maxStops": 1, "layoverMin": 60, "layoverMax": 300,
    "maxTripHours": 12, "preferredCities": ["DEN", "LAS"],
    "cap": null
  },
  "overallBest": {
    "destination": "BOS", "date": "2026-07-11", "weekday": "Sat",
    "summary": "ATL → BOS", "goWildFee": 16, "totalMinutes": 167,
    "reason": "Cheapest Go Wild fare across all destinations in the range."
  },
  "blackoutInRange": ["2026-07-13"],
  "blackoutMeta": { "passLabel": "GoWild Annual 2026–27", "source": "https://www.flygowild.com/guides/frontier-gowild-blackout-dates", "stale": false },
  "destinations": [
    {
      "code": "BOS", "city": "Boston", "resolvedFrom": "east-coast",
      "best": { "date": "2026-07-11", "weekday": "Sat", "summary": "ATL → BOS", "goWildFee": 16, "totalMinutes": 167, "reason": "Nonstop, cheapest in range." },
      "days": [
        {
          "date": "2026-07-11", "weekday": "Sat", "available": true, "blackout": false,
          "routes": [
            { "rank": 1, "type": "nonstop", "stops": 0, "preferred": false,
              "transferCities": [], "goWildFee": 16, "totalMinutes": 167,
              "legs": [ { "from": "ATL", "to": "BOS", "dep": "22:40", "arr": "01:27", "flight": "F9 3086" } ],
              "layovers": [] }
          ]
        },
        { "date": "2026-07-12", "weekday": "Sun", "available": false, "blackout": false, "routes": [] },
        { "date": "2026-07-13", "weekday": "Mon", "available": false, "blackout": true, "routes": [] }
      ]
    },
    {
      "code": "SFO", "city": "San Francisco", "resolvedFrom": "direct",
      "best": { "date": "2026-07-12", "weekday": "Sun", "summary": "ATL → DEN → SFO", "goWildFee": 158, "totalMinutes": 460, "reason": "Routes through your preferred hub (DEN)." },
      "days": [
        {
          "date": "2026-07-12", "weekday": "Sun", "available": true, "blackout": false,
          "routes": [
            { "rank": 1, "type": "connecting", "stops": 1, "preferred": true,
              "transferCities": ["DEN"], "goWildFee": 158, "totalMinutes": 460,
              "legs": [
                { "from": "ATL", "to": "DEN", "dep": "07:40", "arr": "09:05", "flight": "F9 1820" },
                { "from": "DEN", "to": "SFO", "dep": "10:30", "arr": "12:20", "flight": "F9 415" }
              ],
              "layovers": [ { "airport": "DEN", "minutes": 85 } ] }
          ]
        },
        { "date": "2026-07-11", "weekday": "Sat", "available": false, "blackout": false, "routes": [] },
        { "date": "2026-07-13", "weekday": "Mon", "available": false, "blackout": true, "routes": [] }
      ]
    },
    {
      "code": "MSN", "city": "Madison", "resolvedFrom": "wisconsin", "unserved": true,
      "best": null,
      "days": [
        { "date": "2026-07-11", "weekday": "Sat", "available": false, "blackout": false, "routes": [], "note": "Frontier sells no ATL → MSN itineraries on this date." },
        { "date": "2026-07-12", "weekday": "Sun", "available": false, "blackout": false, "routes": [] },
        { "date": "2026-07-13", "weekday": "Mon", "available": false, "blackout": true, "routes": [] }
      ]
    }
  ]
}
```

Field notes: `type` is `"nonstop"` or `"connecting"`; `stops` is the connection
count; `preferred` is true if any `transferCities` entry is in
`preferredCities`; `weekday` is the 3-letter day; a nonstop route has one leg
and `layovers: []`. Per-day `blackout` is true when the date is in your pass's
blackout list — keep the fare AND the flag, surfacing the discrepancy.
`resolvedFrom` is `"direct"` for a city the user named, else the group/state
token that produced it. `unserved: true` marks a destination the search proved
Frontier doesn't sell from the origin (all days empty). If the cap expired
before a destination was started, list it at the end with `"unsearched": true`
and empty days; a day fetched by no worker carries `"unfetched": true`.
`days` inside each destination are ordered available-first is NOT required —
keep chronological order; the `destinations` array itself is ordered
cheapest-first as described in step 4.
