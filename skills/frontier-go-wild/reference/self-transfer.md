# Self-transfer mode (two separate bookings)

Disclosed reference for [`frontier-go-wild`](../SKILL.md), reached from step 3
only when the user asks for self-transfer / two-leg / separate-booking options
(or asks "did you check leg pairs?"). This is the one sanctioned exception to
"never synthesize connections" — the user's own filters bound the explosion:

1. **Middle cities** = (origin's served markets) ∩ (markets serving the
   destination), both from the public `flights-from-<city>` pages, **UNION any
   `stitchCities` the user named**. `maxStops 1` = one middle city per route.
   Drop middles equal to origin/destination.
   - A `stitchCities` entry is searched **even when it is not in the
     intersection**. That is the whole point of naming it: the user may know a
     route the cached network file does not, or want it confirmed dead rather
     than assumed. Never silently drop one.
   - If a named city turns out to have no Frontier service on either leg, report
     it as `unserved` on that leg and move on — same honesty contract as an
     unserved destination. Say which leg failed, so "DEN doesn't work" is
     distinguishable from "BOS→DEN works but DEN→LAX doesn't".
   - Named cities are searched FIRST, before the derived ones, so a capped run
     spends its budget on what the user asked for.
2. **Search each leg standalone** — `origin → middle` and `middle → destination`
   are ordinary one-date searches (same worker contract). A leg seen inside a
   through-itinerary does NOT prove standalone Go Wild availability; always
   search the leg itself.
3. **Pair same-date legs**: leg1.arr → leg2.dep gap must fit
   `layoverMin`…`layoverMax`; total first-dep → final-arr under `maxTripHours`.
4. **Fee = leg1 fee + leg2 fee** (each booking pays its own Go Wild fee — this
   IS bookable, unlike summing legs of a through-itinerary).
5. **Mark honestly**: route carries `"selfTransfer": true` and both leg fees
   in a note. Rank below any equal-fee through-itinerary (a through ticket
   has missed-connection protection; a self-transfer does not — Go Wild
   standby is last priority, so a blown leg 1 means eating leg 2). Never
   present a self-transfer as a protected connection.
