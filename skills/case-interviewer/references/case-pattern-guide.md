# Case pattern guide

Operating manual for an AI interviewer that must do two jobs: (1) RUN an existing case from a local case library faithfully, and (2) INVENT brand-new cases that are indistinguishable from real ones. Written for an LLM, so it favors rules and reusable patterns over prose. Its patterns were distilled from a ~195-case corpus of real firm and prep-site cases; example slugs below point at cases in that library, so if you don't keep one, treat them as illustrative and lean on the INVENT path.

Terminology: **interviewer-led** = the interviewer drives, handing the candidate one discrete question (beat) at a time (McKinsey house style, most PrepLounge "interviewer-led"). **Interviewee-led** = the candidate drives the structure and asks for data; the interviewer feeds numbers on request (Bain/BCG house style, most casebooks framed candidate-led). Everything below applies to both unless a rule is tagged to one.

---

## 1. Anatomy of a case

Every case in the corpus, regardless of source, decomposes into the same skeleton. When inventing, build these parts in order. When running, know which part you are in at all times.

### 1.1 The universal skeleton

1. **Prompt / background paragraph.** 2-5 sentences: who the client is, what industry, what decision or problem, and the explicit objective. Real prompts name a concrete client (`SuperSoda`, `GlobaPharm`, `TexGroup`, `Sosland Sports`) and state ONE objective, sometimes with a target number (`AlpenGlide`: "+5% total revenue"; `GlobalAccess Health`: "60% cost recovery in 5 years"; `Salty Sole`: "20% ROI / double-digit returns"). The objective is the spine; every later beat ties back to it.
2. **Clarifying-facts bank.** Facts the interviewer holds back and reveals ONLY if the candidate asks. In casebooks this is an explicit "Clarifying information" slide (`Salty Sole`: market-leader-US-only, outsourced manufacturing counts as fixed cost, "me-too" fashion follower). In web cases it is embedded ("The case narrows scope to Cambridge residents only"). A strong case has 3-6 such facts; some are load-bearing (scope limits, cost classification) and some are texture.
3. **Question arc (the beats).** Typically 3-5 beats in a fixed shape:
   - **Beat 1 - Structure/framework.** "What factors would you consider?" / "How would you structure this?" Always first. Interviewer-led gives a guideline list of buckets; interviewee-led expects the candidate to draw the tree.
   - **Beat 2 - First quant or exhibit read.** A market size, break-even, or exhibit interpretation.
   - **Beat 3 - Brainstorm / qualitative judgment.** "How would they gain that share?" / "What are the risks?" / "How would you differentiate?"
   - **Beat 4 - Second quant or a twist.** A payback, a TCO, a deeper calculation, or a sensitivity. Not always present in easy cases.
   - **Beat 5 - Synthesis / recommendation.** "What do you tell the client?" Always last.
4. **Exhibits with planted insights.** 0-4 data objects (tables, charts described as tables, segment splits). Each exhibit carries ONE non-obvious takeaway the candidate is meant to extract (see 2 for type-specific planted insights). Exhibits are revealed at their beat, never up front.
5. **Benchmark answers.** For every beat, the "guideline answer" (qual buckets) or worked solution (quant). Casebooks add tiered anchors: "Good answer" vs "Outstanding/Excellent answer" (`Salty Sole` Part 5, `Sosland` Part 1/3), and sense-check callouts (`Sosland` 2b: "Are you sure this is annual not weekly?").
6. **Closing.** The recommendation benchmark: a top-down answer (decision first, then 2-3 reasons grounded in the surfaced numbers, then risks/next steps).

### 1.2 Interviewer-led vs interviewee-led, operationally

| | Interviewer-led (McKinsey style) | Interviewee-led (Bain/BCG style) |
|---|---|---|
| Who transitions beats | Interviewer announces each beat | Candidate drives; interviewer only feeds data when asked |
| Beat 1 | Give guideline buckets after candidate answers | Candidate must produce the full structure unprompted |
| Each beat is | A self-contained mini-case with its own sub-structure | A step the candidate chose to take |
| Data delivery | Interviewer pushes the exhibit at the planned beat | Interviewer waits for the candidate to request the number |
| Scoring focus | Sub-structure of the live question | Full blueprint quality up front (see grading-rubric.md D1) |
| Corpus examples | `mckinsey-electro-light`, `mckinsey-globapharm`, `mckinsey-beautify`, `mckinsey-diconsa`, most `web-preplounge-*` tagged interviewer-led | `bain-coffee-shop-co`, `bain-fashionco`, `web-preplounge-coral-reefs`, `web-preplounge-stern-stewart-texgroup`, `oliverwyman-poseidon-water-park` |

School casebooks (`kellogg-*`, `stern-*`, `wharton-*`, etc.) are mostly interviewer-led on the page even when the underlying case is candidate-led: they print an "Interviewer guide" with numbered steps, "Provide Exhibit A" cues, and tiered answer keys. Treat the casebook format as a runbook for the interviewer, not a script for the candidate.

---

## 2. Patterns by case type

For each type: the typical beat sequence, the quant block with actual formula shapes, typical exhibits, the classic planted insight, and 2-3 real corpus slugs.

### 2.1 Profitability / turnaround
- **Sequence:** structure (profit = revenue - cost tree) -> isolate whether revenue or cost side is the problem -> exhibit read to localize the driver -> quant to size it -> fix + recommendation.
- **Quant shapes:** `Profit = (Price x Volume) - (Fixed + Variable x Volume)`. Isolate a driver by holding others constant across years. Margin walk: compare COGS/unit, SG&A %, utilization vs prior year and vs competitor. Reverse a target: `required EBITDA = target sale value / sale multiple`, then `required volume = (target EBITDA + fixed) / unit contribution`.
- **Exhibits:** multi-year income statement (`Salty Sole` Exhibit A: sales, discounts, COGS, fixed, EBITDA by year); competitor benchmark table; stacked market-share bar chart.
- **Planted insight:** the obvious driver is a decoy; the real cause is elsewhere. `Salty Sole`: cost and price are both fixed/optimized, so volume is the ONLY lever, and it must more than double, which is the punchline. `kearney-promotion-planning`: the problem is not price but in-stock execution. `bain-fashionco`: the higher-headline program (rewards) loses to intermittent sales by $50M.
- **Slugs:** `bain-fashionco`, `web-preplounge-stern-stewart-texgroup`, `kellogg-casebook-2020-salty-sole-shoe`, `loms-case-5-steel`, `loms-case-3-signs`.

### 2.2 Market entry / new product
- **Sequence:** structure (market attractiveness + ability to win + economics) -> market sizing -> break-even or profitability of entry -> go-to-market / how-to-win brainstorm -> go/no-go recommendation.
- **Quant shapes:** **break-even market share = fixed investment / contribution-per-unit / market size.** Worked in `mckinsey-electro-light`: $40M fixed / $0.10 per unit = 400M units; x 1/8 gallon = 50M gallons; / 400M gallon market = **12.5% share**. Market sizing top-down: `population x penetration x frequency x price`. Break-even volume: `fixed / (price - variable)` (`bain-coffee-shop-co`: 409,350 / 2 = 204,675 cups).
- **Exhibits:** market-size buildup table, competitor share split, cost-structure table.
- **Planted insight:** the required break-even share, benchmarked against incumbents, tells the story. 12.5% would make Electro-Light the #2 player from a standing start (hard); 2-3% of city coffee demand is achievable (easy, but flag payback + competition). The candidate must judge feasibility, not just compute the number.
- **Slugs:** `mckinsey-electro-light`, `bain-coffee-shop-co`, `web-preplounge-tkmc-lithium-market-entry`, `web-preplounge-rwe-floating-wind-japan`, `kellogg-casebook-2020-sosland-sports`.

### 2.3 M&A / investment decision
- **Sequence:** structure (strategic fit + target value + price/ROI + alternatives to acquiring) -> value the target's assets (pipeline, capacity, customers) -> a break-even or ROI calculation on the deal -> integration/synergy risks -> buy/pass recommendation.
- **Quant shapes:** expected-value chains through probability stages: `value x P(stage1) x P(stage2) x ...`. `mckinsey-globapharm`: find the Phase II success rate that makes a $150M trial investment break even against a $1.2B drug value (answer: 40% -> 80%). Payback: `cumulative business cash flow crosses zero`; `BCF = EBITDA +/- NWC delta - investment` (`tkMC`: 3-year payback, both organic and acquisition). ROI: `(exit value - entry) / entry`; exit value = `EBITDA x multiple`.
- **Exhibits:** pipeline/stage table with success rates, cash-flow projection by year, deposits/market map.
- **Planted insight:** two options can tie on the headline metric but diverge on a second axis. `tkMC`: organic and LiCo acquisition both pay back in 3 years, but LiCo generates higher LATER cash flow via recycling (100% deferred payment reduces NWC). The recommendation hinges on the second-order difference, not the tie.
- **Slugs:** `mckinsey-globapharm`, `web-preplounge-tkmc-lithium-market-entry`, `kellogg-casebook-2020-plastic-world`, `kellogg-casebook-2020-zephyr-beverages`.

### 2.4 Pricing
- **Sequence:** structure (cost-plus vs value vs competitive anchors + segment willingness-to-pay + cannibalization) -> read current price/volume by segment -> model a new pricing scheme -> compare to target -> recommend with acceptance risks.
- **Quant shapes:** segment revenue buildup `sum over segments of (volume_seg x price_seg)`; then re-price and re-total. `alpenglide`: dynamic weather-tiered pricing recomputes daily-ticket revenue by adult/junior x good/moderate weather x volume split, yields +4% vs +5% target. `globalaccess-health`: solve for required volume at a new price to hit a revenue target: `(target - fixed revenue) / new price` = 3M tests = 50% growth.
- **Exhibits:** channel/segment mix table with volume and per-unit price, showing a cross-subsidy.
- **Planted insight:** the model gets you MOST of the way but deliberately falls short of the target, forcing the candidate to name additional levers (`alpenglide` +4% vs +5%). Or: a minority of volume drives the majority of revenue (`globalaccess-health`: NGOs + private labs = 1/3 of volume, ~80% of revenue), so protect the low-price segments and grow the high-price ones.
- **Slugs:** `web-preplounge-simon-kucher-alpenglide`, `web-preplounge-globalaccess-health`, `stern-mca-casebook-2019-the-pricing-games`.

### 2.5 Growth / revenue
- **Sequence:** structure (grow existing vs new products vs new geographies/segments) -> size the growth opportunity -> unit economics of the growth lever -> risks (cannibalization, capability) -> recommendation.
- **Quant shapes:** total cost of ownership comparisons (`mckinsey-talbot-trucks`: diesel TCO of €106k/yr built from driver + depreciation + fuel + maintenance + other; solve max eTruck price so eTruck TCO = diesel: required depreciation budget €47k/yr x 4-yr life = **€188k max price**). Incremental revenue: `base x growth %`; payback = `upfront / annual incremental profit`.
- **Exhibits:** cost-driver breakdown table, segment attractiveness matrix, revenue-by-segment projection.
- **Planted insight:** the growth lever only pays if a specific condition holds (eTrucks win on cost-per-km for long-haul, so target high-mileage fleets, not owner-operators). Or a plateau has a single hidden cause (`loms-case-2-internet`: growth stalled for a diagnosable reason).
- **Slugs:** `mckinsey-talbot-trucks`, `web-preplounge-bcg-fashion-startup`, `web-preplounge-mbmc-amg-individualization-hubs`, `loms-case-2-internet`, `loms-case-8-fashion`.

### 2.6 Operations / cost reduction
- **Sequence:** structure (process map: inputs -> throughput -> output, or cost stack) -> find the bottleneck or cost concentration -> quantify the fix -> implementation risks -> recommendation.
- **Quant shapes:** throughput = `capacity x utilization`; `units = hours x rate`. Payback on an efficiency investment = `capex / annual savings` (`revolut`: ~2-year payback on an AI chatbot). Capacity buildup like `Sosland`: hours = opening hours x days x courts; usable = utilization x hours; members = usable hours x players/hour.
- **Exhibits:** process-step table, utilization/capacity table, cost-per-unit stack.
- **Planted insight:** the metric being optimized is the wrong one (`revolut`: call center rewards volume over resolution, so CSAT tanks; fixing the incentive, not adding headcount, is the answer). Or a "price" problem is really an execution problem (`kearney-promotion-planning`).
- **Slugs:** `web-preplounge-revolut-mock-interview`, `kellogg-casebook-2020-money-bank-call-center`, `web-preplounge-bcg-platinion-erp-dekokonzept`, `loms-case-4-storage`.

### 2.7 Market sizing / guesstimate
- **Sequence:** clarify scope -> pick top-down or bottom-up -> build the estimate in layers -> sanity-check -> state the number and what it implies.
- **Quant shapes:** bottom-up from a capacity constraint: `oliverwyman-poseidon-water-park`: slides x hours x throughput/hour = rider-slots; / rides-per-visitor = visitors; x ticket mix = revenue; + ancillary (spend x purchase probability). Top-down: `population x segment % x usage rate x price`.
- **Exhibits:** usually none; the candidate builds the table. If present, a single reference figure (population, EV production).
- **Planted insight:** the binding constraint is not the obvious one (park revenue is capped by SLIDE THROUGHPUT, not gate size). Choosing the right constraint IS the insight.
- **Slugs:** `oliverwyman-poseidon-water-park`, `bain-coffee-shop-co` (Q1), `wharton-casebook-2017-unicloth`.

### 2.8 Unconventional / public-sector / ESG
- **Sequence:** structure (often a MECE driver tree for a non-profit objective) -> interpret survey/impact exhibit -> a large cost or cost-benefit calculation -> a creative-alternatives brainstorm (budget rarely covers the obvious plan) -> recommendation balancing mission and money.
- **Quant shapes:** cost-benefit aggregation: `diconsa`: families x monthly cost x 12 x reduction % = 450M pesos/yr saved. Big bottom-up cost builds: `coral-reefs`: boats needed = area / coverage-per-boat; fuel = liters/hr x hours x price x boats; total vs a stated budget. Threshold: `national-education`: how many schools close if avg size matches a benchmark neighbor.
- **Exhibits:** survey-results-by-region chart, trend-over-time table (`coral-reefs`: reef quality 15% -> 10% -> 6.3%), budget line.
- **Planted insight:** the default intervention exceeds the budget, forcing a reframe toward the root cause. `coral-reefs`: boat surveillance costs $125M vs $75M budget, but a fisherman sustainability bonus ($37.5M) addresses the actual cause within budget. `diconsa`: the network already exists, so the win is leverage, not new build.
- **Slugs:** `mckinsey-diconsa`, `web-preplounge-coral-reefs`, `mckinsey-national-education`, `mckinsey-conservation-forever`, `mckinsey-shops-corporation`, `web-preplounge-eon-heating-systems`.

---

## 3. How to invent a new case from scratch

The generator recipe. Follow in order. The cardinal rule: **choose the answer first, then build the numbers backward so everything foots.**

### 3.1 Pick an industry (vary it, stay fresh)
Select randomly but avoid repeating recent picks. The corpus already spans: beverages/CPG, cosmetics, pharma, fashion/apparel retail, footwear, grocery/drug, coffee, food service/QSR, automotive (trucks, luxury), fintech/banking, insurance, energy/utilities, renewables, chemicals, textiles, commodities/mining, logistics/shipping, aviation/airlines, telecom, robotics, water parks/leisure, ski resorts, sports/entertainment, media/streaming, education, healthcare/diagnostics, museums/arts, conservation/environment, public benefits distribution.

Underused, good for freshness: agriculture/vertical farming, waste/recycling, pet care, funeral services, self-storage, vending/micro-markets, ports, water utilities, dental/optical chains, home services (HVAC, pest control), maritime freight, satellite/space, gaming/esports, secondhand/resale marketplaces, carbon credits, EV charging networks, senior living, laundromats, parking, ticketing, live events, craft beverage, specialty coffee roasting, medical devices, generic drug manufacturing, B2B SaaS, agtech, aquaculture, textiles recycling.

### 3.2 Pick case type and style
- Default to **classic consulting style** (a real client with a real decision), not gimmicky framing.
- Choose a type from section 2. Match difficulty to type comfort: profitability and market entry make the cleanest easy/medium cases; M&A, valuation, and multi-layer ops make the best hard cases.
- Choose style: interviewer-led (you drive beats, best for a structured practice session) or interviewee-led (candidate drives, best for testing self-direction). When in doubt, interviewer-led with a clear beat arc.

### 3.3 Invent a fictional client
Naming conventions the corpus actually uses:
- **Portmanteau / descriptive:** `SuperSoda`, `Electro-Light`, `GlobaPharm`, `BioFuture`, `TexGroup` (+ `TexCasual`/`TexPremium` sub-brands), `AlpenGlide`, `GlobalAccess Health`, `Salty Sole`, `Sosland Sports`, `NordWerk`.
- **Founder + category:** "Ralph Kline" (fashion), "Felicity Sosland" (CEO name adds texture).
- **Real-brand-adjacent for public-sector:** real institution (Gates Foundation, Indonesian government, Diconsa) with a fictional engagement.
- Keep it pronounceable and category-signaling. One client name; name sub-segments if the case splits by segment.

### 3.4 Construct economics that FOOT (work backward)
1. **Decide the verdict first.** E.g. "break-even at 12% share, incumbents hold 40/35, so 12% from a standing start is a stretch -> enter only with a differentiated hook" or "payback is 1.25 years -> clearly invest."
2. **Pick round, mentally-computable numbers.** Contributions that divide cleanly ($2.00 - $1.90 = $0.10), markets in round gallons/units, growth rates of 10%/20%/25%, multiples like 6.5x. A candidate should be able to do every step without a calculator.
3. **Build the chain backward from the verdict.** If you want a 12.5% break-even share: choose market size (400M gallons), choose fixed cost ($40M), choose unit contribution ($0.10) and unit size (1/8 gal) so that `40M/0.10 = 400M units = 50M gallons = 12.5%`. Adjust one input if the answer is ugly.
4. **Make every number in every exhibit consistent with every other.** If the income statement says EBITDA $19.65M and the multiple is 6.5x, the sale price cell must read $127.7M. If segment volumes are 60/30/10 of 2M visits, the sub-totals must sum to the stated total. Recompute the whole sheet after any change.
5. **Pick units deliberately** and keep conversions clean (16 oz = 1/8 gallon; 60 kWh pack = 9.1 kg lithium). Awkward conversions are where invented cases break.

### 3.5 Plant exactly one non-obvious insight
Embed ONE thing a strong candidate discovers that a weak one misses. It should be derivable from the data, not stated. Patterns that work (from 2): the obvious driver is a decoy and the real lever is elsewhere; two options tie on the headline but differ on a second axis; the binding constraint is not the obvious one; the budget cannot cover the default plan so a reframe is needed; a small share of volume drives most of the value. Do not plant two competing insights in an easy or medium case; it muddies the signal.

### 3.6 Design 2-4 exhibits
Describe each as a concrete data object the interviewer reveals at one beat:
- **Data table:** multi-year P&L, cost-driver stack, capacity inputs (rows = metrics, columns = years or segments).
- **Chart-as-table:** a bar or line chart rendered as a table (stacked share bars like `Salty Sole` Exhibit B; a trend like `coral-reefs` reef quality by year). Give exact values.
- **Segment split:** channel/segment mix with volume and per-unit economics (`globalaccess-health`).
Rules: every exhibit must be referenced by exactly one beat; every exhibit must carry data that advances the planted insight or a calculation; no exhibit is decorative. Easy = 0-1 exhibit, medium = 1-2, hard = 2-4 (with at least one distractor column in hard).

### 3.7 Write benchmark answers for every beat
- **Qual beats:** 3-5 buckets with 2-4 sub-points each (mirror the "Guideline answer" style in `mckinsey-*`). Add a tiered "Good answer" vs "Outstanding answer" split for at least the structure and recommendation beats (casebook convention).
- **Quant beats:** show the worked solution with the formula in words first, then the plugged-in arithmetic, then the interpreted so-what. Include a sense-check line ("12.5% would make it the #2 player, a stretch").
- **Recommendation:** write the model top-down close verbatim: decision in sentence one, then 2-3 numbered reasons citing the surfaced numbers, then risks and next steps.

### 3.8 Completeness checklist (the generator MUST pass all)
- [ ] Objective stated once, concrete, with a target number where natural.
- [ ] Every number in every exhibit recomputed and consistent with every other number (foot the whole thing).
- [ ] Every quant beat solvable mentally; answer lands on a clean figure.
- [ ] Exactly one planted insight; it is derivable from data, not stated outright.
- [ ] Every exhibit referenced by exactly one beat; no orphan or decorative exhibits.
- [ ] Beat arc present: structure -> quant/exhibit -> brainstorm -> (optional second quant) -> synthesis.
- [ ] Clarifying-facts bank has 3-6 items, with the load-bearing ones (scope, cost classification) flagged as reveal-only-if-asked.
- [ ] Benchmark answer written for every beat, quant math verified by independent recomputation.
- [ ] Recommendation written top-down (answer first) and grounded in the case's own numbers.
- [ ] Difficulty matches the dial in 3.9.

### 3.9 Difficulty dial
- **Easy:** one clean quant beat, single-driver diagnosis, generous data given without asking, 0-1 exhibit, obvious-but-flag-the-caveats answer. Models: `mckinsey-beautify`, `bain-coffee-shop-co`, `globalaccess-health`.
- **Medium:** two quant beats OR one quant plus a meaty exhibit read, one twist (a segment split, a benchmark comparison), 1-2 exhibits, an answer that needs the insight to land. Models: `mckinsey-electro-light`, `mckinsey-talbot-trucks`, `alpenglide`.
- **Hard:** multi-layer math (probability chains, cash-flow payback, TCO), an ambiguous objective the candidate must clarify, at least one distractor data column, and a counterintuitive answer (the default plan fails, or the tie breaks on a second axis). Models: `mckinsey-globapharm`, `web-preplounge-coral-reefs`, `web-preplounge-stern-stewart-texgroup`, `kellogg-casebook-2020-salty-sole-shoe`.

### 3.10 Worked generator example (medium, interviewer-led, market entry)

A full pass through the recipe so the pattern is concrete. Industry picked fresh from the underused list: **self-storage**.

**Step 1, decide the verdict first.** "One 500-unit facility exactly absorbs the town's unmet demand and pays back in 5 years, so ENTER now as first mover; a delayed or second entrant would oversupply and crush occupancy." This fixes both the recommendation AND the planted insight (the demand gap is exactly one facility).

**Step 2-4, build the footing numbers backward.**
- Facility: 500 units, rent $100/unit/month.
- Revenue at full occupancy: 500 x $100 x 12 = $600,000/yr.
- Stabilized occupancy 90%: 0.90 x $600,000 = $540,000/yr.
- Operating cost (fixed): $240,000/yr. Annual profit = $540,000 - $240,000 = $300,000/yr.
- Build cost (fixed investment): $1,500,000. Payback = $1,500,000 / $300,000 = **5 years**. Clean.
- Break-even occupancy (covers opex): $240,000 / ($1,200/unit-yr) = 200 units = **40% occupancy**. Below that the facility loses money, which is the oversupply risk.

**Market-sizing exhibit that foots the "exactly one facility" gap.**
- Town households: 40,000. Self-storage penetration: 10% -> 4,000 renting households (assume 1 unit each) -> 4,000 units of demand.
- Existing supply: 3,500 units across 8 competitors. Unmet demand: 4,000 - 3,500 = **500 units** = exactly one new facility.

**Client:** "BoxYard Storage" (portmanteau, category-signaling), evaluating a first facility in the town of Fairhaven.

**Beat arc and benchmark answers:**
1. *Structure.* "What would you consider before BoxYard enters?" Guideline buckets: market demand vs existing supply; facility unit economics and payback; competitive response; site/regulatory. Outstanding answer states a hypothesis ("enter only if unmet demand covers a full facility at a viable payback").
2. *Market sizing (Exhibit 1).* Candidate should compute the 500-unit gap. Planted so-what: the gap equals exactly one facility, so first-mover timing is decisive.
3. *Economics quant (Exhibit 2, cost + rent table).* Compute stabilized profit ($300k) and payback (5 years). Sense-check: "40% occupancy just breaks even on opex, so the 90% assumption has real cushion."
4. *Judgment twist.* "A competitor is rumored to be scouting the same town. Does that change your answer?" Strong candidate: two facilities split 500 units of gap plus cannibalize existing renters, occupancy falls toward the 40% break-even line, payback balloons. So enter FAST or not at all.
5. *Recommendation (top-down).* "Yes, enter now with one 500-unit facility. One, unmet demand is exactly 500 units, so a single facility fills the market. Two, it pays back in 5 years at a conservative 90% occupancy with a 40% break-even floor. Three, the window is first-mover only: a second entrant oversupplies and pushes both toward the break-even line. Risk: a competitor moving first, and demand penetration softening below 10%."

Checklist pass: numbers foot (600k -> 540k -> 300k -> 5yr; 4,000 - 3,500 = 500), one planted insight (gap = one facility -> timing), both exhibits referenced by a beat, all math mentally computable, recommendation top-down.

---

## 4. Realism rules for delivery

Brief operating rules for running a case (invented or existing) against a live candidate.

- **Hold back clarifying facts until asked.** State only the prompt and objective up front. Reveal each fact in the clarifying bank only when the candidate asks a question that touches it. Do not volunteer scope limits, cost classifications, or segment splits.
- **Reveal exhibits only at their beat.** Push an exhibit when the candidate reaches the beat it belongs to (interviewer-led) or asks for exactly that data (interviewee-led). Never hand over all exhibits at once.
- **Quant tolerance: accept answers within +/-5%.** Reward a worded formula and a clean process over decimal precision. A caught-and-corrected slip scores higher than mechanical perfection (see grading-rubric.md D2).
- **Drive beat transitions in interviewer-led; wait in interviewee-led.** In interviewer-led, announce the next question when the current beat resolves. In interviewee-led, let the candidate choose the next step and only supply data on request.
- **Pushback templates** (use to test conviction, one at a time): "What's driving that?" / "So what does that mean for the client?" / "Our client already tried that and volume dropped, what else?" / "Are you sure, is that annual or weekly?" (the `Sosland` sense-check move) / "You're the market leader already, so where does the growth come from?"
- **Hints only on explicit request, and count them.** Give a hint only when the candidate asks for one or is clearly stuck and asks how to proceed. Note every hint and what the candidate did with it (grading-rubric.md gate check 4). Do not pre-empt struggle with unsolicited nudges.
- **Track the objective.** If the candidate drifts to a different question than the stated objective and does not catch it, let it run briefly, then note it for the debrief (wrong-problem gate). Do not rescue silently.
- **Close on synthesis.** End every case by asking for a recommendation and scoring it top-down: did the decision come first, were the reasons grounded in the surfaced numbers, were risks named.
