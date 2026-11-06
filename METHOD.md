# Method

This tool answers one pre-sales question for a robotic parcel sort cell: **how many cells does a delivery station need to clear its dispatch waves on a busy day, and what share of its parcels can a robot handle?** Every number below comes from `pipeline/` run on public data. Reproduce it with `pipeline/run_all.sh`.

## 1. Data

| | |
|---|---|
| Dataset | Amazon Last Mile Routing Research Challenge 2021, training split (`model_build_inputs/route_data.json`, `package_data.json`) |
| Source | https://registry.opendata.aws/amazon-last-mile-challenges/ |
| Licence | CC BY-NC 4.0. Credit: Amazon.com, Inc. and the MIT Center for Transportation & Logistics. Non-commercial use. |
| Size | 6,112 routes, 1,457,175 packages, 17 delivery stations, 5 US metros, 2018-07-19 to 2018-08-26 (39 dates) |
| Fields used | station code, route date, route departure time (UTC), stop zone_id, package depth/width/height (cm) |

**Ingest** (`sizer/ingest.py`). `package_data.json` (375 MB) is streamed with ijson and never loaded whole. The file contains bare `NaN` tokens, which are invalid JSON, so the byte stream goes through a filter that rewrites `NaN` to `null` and holds back a trailing `N`/`Na` so a token split across reads is still caught (unit test checks every split point). The filter would also alter the substring `NaN` inside a string value; IDs in this file are lowercase hex and station codes, so none exist, and the reconciliation below confirms nothing was lost.

**Reconciliation.** Packages parsed = 1,457,175. An independent byte count of the `"PackageID_` key in the raw file = 1,457,175. They match exactly.

**Stations analysed.** The six stations with at least 28 observed days and the most packages: DLA7, DLA9, DBO3, DSE5, DLA8, DSE4. Together they hold 899,387 of the 1,457,175 packages; all sizing results use these six, and only the overall envelope share uses the full set.

**Important scope note.** The public sample contains a subset of each station's routes. "Daily volume" here means packages on the routes in the sample, not the station's total throughput. The method is unchanged at full volume; the absolute cell counts scale with it.

## 2. Volume profile: what the sample can and cannot say

**Coverage diagnostic (finding).** The public sample holds a different number of each station's routes on each day, and daily package totals mostly track that number. Per station (`coverage` in `validation.json`):

| Station | corr(daily packages, routes) | Packages/route CV | Routes/day (min to max) | P90 ÷ mean, all days | P90 ÷ mean, days with ≥ ½ max routes | P90 ÷ mean of packages/route |
|---|---|---|---|---|---|---|
| DLA7 | 0.986 | 4.7% | 8 to 56 | 1.30 | 1.21 | 1.07 |
| DLA9 | 0.996 | 4.3% | 2 to 39 | 1.71 | 1.25 | 1.05 |
| DBO3 | 0.993 | 7.3% | 5 to 36 | 1.47 | 1.23 | 1.08 |
| DSE5 | 0.993 | 7.3% | 2 to 24 | 1.64 | 1.28 | 1.08 |
| DLA8 | 0.993 | 3.8% | 8 to 27 | 1.43 | 1.23 | 1.04 |
| DSE4 | 0.997 | 4.1% | 1 to 21 | 1.46 | 1.25 | 1.06 |

So "the P90 day is 1.3–1.7× the mean day" is mainly a property of how the sample was drawn, not of demand. An earlier version of this tool led with that ratio; it is withdrawn. What is stable is packages per route (CV 4–7%), and every station knows its route count and departure schedule.

**Design day = routes × packages per route.** Design routes $R^{*}$ = P90 of sampled routes per day (a sample-coverage bound, not the station's true route count). Packages per route $\bar n = \sum_d V_d / \sum_d R_d$. A day-block bootstrap (2,000 resamples of whole days) gives 90% intervals:

| Station | $R^{*}$ (90% CI) | $\bar n$ (90% CI) | Design day used |
|---|---|---|---|
| DLA7 | 51.1 (47.0–55.1) | 233.3 (230.0–236.6) | 2018-08-15, 51 routes |
| DLA9 | 30.4 (23.6–35.0) | 247.5 (244.6–250.3) | 2018-07-24, 30 routes |
| DBO3 | 32.0 (27.2–35.2) | 223.4 (218.9–228.3) | 2018-08-16, 32 routes |
| DSE5 | 23.0 (19.3–23.0) | 226.5 (223.2–230.1) | 2018-08-23, 23 routes |
| DLA8 | 22.0 (18.6–23.0) | 248.1 (245.2–250.9) | 2018-07-25, 22 routes |
| DSE4 | 17.0 (15.0–18.6) | 240.8 (238.5–243.0) | 2018-08-21, 17 routes |

The design day is the observed day whose route count is closest to $R^{*}$ (ties broken by packages closest to $R^{*}\bar n$), so its **real departure times and real per-route counts** are used, scaled by 1.10 for peak season.

**Bootstrap design days.** To put an interval on the cell count itself, 200 bootstrap design days are built: resample the days, take that resample's P90 route count $R_b$, use the real departure set of an observed day with $R_b$ routes, and draw $R_b$ real per-route counts from the routes on the resampled days. Each goes through the wave simulation (§5c) and we record the smallest $c$ with < 1% late. $P(c \text{ is enough})$ is the share of the 200 days that $c$ clears.

## 3. Pick-envelope fit

Each package's dimensions are sorted to $L \ge M \ge S$. A package is robot-sortable if
$$L \le L_{max},\quad M \le M_{max},\quad S \le S_{max},\quad S \ge S_{min}.$$
Default envelope 60 × 45 × 35 cm, $S_{min}=0$. **This is an editable assumption, not any vendor's specification.** No weight limit is applied because the dataset has no weights; we do not invent them.

Measured sortable share: 96.4% (DBO3) to 97.7% (DLA7, DLA9); 97.16% over all 1.46 M packages. Sensitivity: moving $L_{max}$ by 5 cm moves the sortable share by only 0.40 to 0.47 points at the default envelope, because the longest-side distribution is already thin beyond 60 cm (P99 longest side = 66 cm). The exception share $e = 1 - \text{share}$ goes to a manual lane.

## 4. Destinations

One sort destination (gaylord or cart) per outbound route. With 8 destinations per cell (configurator range 6–16+), destination count needs $\lceil R/8 \rceil$ cells, where $R$ is the number of routes on the design day. At DLA7 (51 routes → 7 cells) destinations bind at the same count as FIFO throughput, and above the EDF count (6). Elsewhere destinations need no more cells than EDF. Zone-prefix counts are exported for a finer sort plan (DLA7 would need 12 cells to sort to zone prefix).

## 5. Sizing

Cell rate $\mu = 500$ sorts/h (published configurator figure). Robot volume per route $= 1.10\,n_r(1-e)$.

**Inbound shape (synthetic assumption, labelled).** The dataset has no inbound scan times. We tie inbound to the real departures: route *r*'s parcels arrive uniformly in $[D_r - 3\,\text{h},\ D_r - 1\,\text{h}]$ and must be sorted by the cutoff $D_r - 0.5\,\text{h}$. The sort span is $T = (\max D - \min D) + 2\,\text{h}$. **Headline finding:** because real departures cluster, the peak 15-minute inbound rate is **1.45–1.96× the span-average rate** (DLA7 1.82, DLA9 1.81, DBO3 1.65, DSE5 1.80, DLA8 1.96, DSE4 1.45). This rests on the real departure times; only the shape of each route's inbound window is assumed, and §5f measures how much that matters.

**(a) Spreadsheet rule.** $c_{hand} = \lceil V(1-e)/(T\mu) \rceil$, for the design day and (for reference only) the average sampled day.

**(b) Erlang C, kept only as a stability check.** $P(W_q > t) = C(c,a)\,e^{-(c\mu-\lambda)t}$ with $a=\lambda/\mu$. With $\mu = 500$/h and $t = 0.5$ h, the exponent is $250(c-a)$, so $P(W_q > t) < 1\%$ as soon as $c - a > \ln(100)/(\mu t) = 0.018$. Erlang C at this threshold therefore collapses to $c = \lceil a \rceil$, which *is* the hand rule. The earlier claim that "Erlang C agrees with the hand rule" was one method counted twice; it is now reported only as a stability check.

**(c) Wave simulation, FIFO** (`sizer/sim.py:run`). A pooled bank of *c* identical cells, FIFO, shared infeed; each arrival in time order takes the cell that frees first (exact for G/G/c FIFO). Service is gamma, mean 7.2 s, CV 0.25. A parcel is late if it finishes after its route's cutoff. $c_{FIFO}$ = smallest *c* with mean late share < 1% (20 replications, 95% CI on the late share reported per *c*).

**(d) Deadline floor (processor-demand criterion)** (`sizer/deadline.py`). Parcels that arrive at or after $t_1$ and are due by $t_2$ must be processed inside $[t_1,t_2]$, so for any policy
$$c \;\ge\; \max_{t_1<t_2} \left\lceil \frac{N(t_1,t_2) - L}{\mu\,(t_2-t_1)} \right\rceil,\qquad N(t_1,t_2) = \sum_{r:\,K_r\le t_2} n_r \cdot \mathrm{clip}\!\left(\frac{B_r-\max(t_1,A_r)}{B_r-A_r},0,1\right)$$
with $[A_r,B_r]$ route *r*'s inbound window and $K_r$ its cutoff. $t_2$ runs over every cutoff (demand only steps there), $t_1$ over a 5-minute grid plus every $A_r$, $B_r$. $L = 0$ gives the zero-late floor; $L = 0.01\sum n_r$ gives the floor for the same < 1%-late target the simulation uses. $N$ is the fluid expectation under the inbound assumption.

**(e) Earliest-deadline-first induction** (`sizer/sim.py:run_priority`). Same bank, but a freed cell takes the waiting parcel with the earliest cutoff (heap keyed by cutoff). With the key set to arrival order it reproduces FIFO exactly (tested). This asks whether deadline-aware sequencing in the cell-control software can meet the same cutoff with fewer cells.

### Results (design day, +10% peak, < 1% late)

| Station | Avg-day rule* | Design-day rule (= Erlang C) | **Floor, 1% late** | **EDF** | **FIFO** | FIFO, 90% of bootstrap days | Destinations ⌈R/8⌉ |
|---|---|---|---|---|---|---|---|
| DLA7 | 5 | 6 | 6 | **6** | **7** | 8 (P(7) = 0.85) | 7 |
| DLA9 | 3 | 4 | 4 | **4** | **5** | 5 (P(4) = 0.39) | 4 |
| DBO3 | 3 | 5 | 5 | **5** | **5** | 6 (P(5) = 0.53) | 4 |
| DSE5 | 2 | 4 | 3 | **3** | **4** | 4 (P(3) = 0.29) | 3 |
| DLA8 | 2 | 3 | 3 | **3** | **4** | 4 (P(3) = 0.18) | 3 |
| DSE4 | 3 | 3 | 3 | **3** | **3** | 4 (P(3) = 0.62) | 3 |

\*The average-day rule is shown for reference only: its gap to the design day comes from sample coverage (§2).

- **The ladder checks the simulation's extra cell.** The 1%-late floor is a lower bound for any policy on the expected (fluid) inbound under the §5 inbound assumption; a single random day can fall slightly below it. EDF reaches it at all six stations. FIFO sits one cell above it at 4 of 6 (DLA7, DLA9, DSE5, DLA8). So the extra FIFO cell is not a simulation bug: within this model it is the cost of serving parcels in arrival order when departures are clustered. Whether it appears on a real floor depends on the real inbound curve (§5f).
- **Deadline-aware induction saves one cell on throughput at 4 of 6 stations** (24 cells against 28 in total), under the stated inbound assumption. At DLA7 the 51 route destinations still need 7 cells at 8 gaylords each, so the saving is realised there only with 9 or more destinations per cell; at DLA9, DSE5 and DLA8 it holds with 8. Where EDF saves nothing (DBO3, DSE4), FIFO is already at the floor and there is no slack.
- **One cell short (FIFO, design day):** DLA7 6 cells → 6.7% of parcels (823) late, 73% of routes with a late parcel; DLA9 6.5%, 67%; DBO3 18.6%, 100%; DSE5 10.4%, 93%; DLA8 5.5%, 64%; DSE4 34%, 100%.
- **Uncertainty from the sample.** Across 200 bootstrap design days, the FIFO count that clears 90% of them is one higher than the point estimate at DLA7, DBO3 and DSE4.
- DLA7 FIFO detail (20 reps): 6 cells → 6.86% late (95% CI ± 0.20 pt); 7 cells → 0.0%. EDF: 6 cells → 0.0%.

### 5f. Sensitivity of the cell count to each assumption

One assumption at a time on each design day (common random numbers, 4 replications per point). The flip point is found by bisection (8 steps) on the continuous parameter: the value at which the FIFO count rises (↑) or falls (↓) from its base value. "–" = no flip in the searched range.

| Station (base FIFO cells) | Sustained cell rate (500/h) ↑ / ↓ | Peak uplift (10%) ↑ / ↓ | Inbound opens before departure (3 h) ↑ / ↓ | Inbound closes before departure (1 h) ↑ / ↓ | Cutoff buffer (30 min) ↑ / ↓ | Service CV (0.25) |
|---|---|---|---|---|---|---|
| DLA7 (7) | 462 / 541 | 19% / 1.6% | 2.44 h / 3.53 h | 0.78 h / 1.36 h | 40 min / 17 min | – |
| DLA9 (5) | 429 / 538 | 29% / 2.5% | 2.50 h / 3.29 h | – / 1.52 h | 50 min / 19 min | – |
| DBO3 (5) | 474 / 593 | 16% / −7.2% | 2.82 h / 3.60 h | 0.67 h / – | 37 min / 3 min | – |
| DSE5 (4) | 416 / 560 | 32% / −1.2% | 2.11 h / 3.59 h | – / 1.60 h | 47 min / 16 min | – |
| DLA8 (4) | 399 / 534 | 37% / 2.3% | 1.96 h / 3.38 h | – / 1.25 h | – / 20 min | – |
| DSE4 (3) | 491 / 738 | 13% / −27% | 2.94 h / – | 0.92 h / – | 32 min / – | – |

Service-time variability (CV 0.1 to 1.0) never changes the count: at 7.2 s per pick, the wave, not pick jitter, sets the size.

### 5g. Business case in dollars (no vendor price assumed)

Manual sorters are simulated as servers under the **same wave and the same < 1%-late rule** ($\mu$ = 275 and 300/h), giving peak manual heads for all parcels, and separately for the exception share alone. Robot side = operators per cell × $c_{FIFO}$ + manual exception heads. Operators per cell is an explicit input, shown at 0.5 (one person tending two cells), 1 and 2.
$$\Delta_{yr} = (h_{manual} - h_{robot}) \times \$18.10 \times H \times 300,\qquad \text{break-even capex per cell}(N\text{ months}) = \frac{\Delta_{yr} \cdot N/12}{c}$$
$H$ = paid hours per sort day = sort span rounded up to 0.5 h (DLA7: 4.5 h); 300 sort days/yr; wage unburdened (conservative). Both sides are staffed for the design day.

| Station | Manual heads (275/h) | FIFO cells | Δ/yr at 0.5 op/cell | Δ/yr at 1 op/cell | Break-even capex per cell, 24-month payback (0.5 / 1 op) | at 2 ops/cell |
|---|---|---|---|---|---|---|
| DLA7 | 13 | 7 | $207,700 | $122,200 | $59,300 / $34,900 | negative |
| DLA9 | 8 | 5 | $122,200 | $54,300 | $48,900 / $21,700 | negative |
| DBO3 | 9 | 5 | $104,500 | $57,000 | $41,800 / $22,800 | negative |
| DSE5 | 7 | 4 | $86,900 | $43,400 | $43,400 / $21,700 | negative |
| DLA8 | 7 | 4 | $119,500 | $59,700 | $59,700 / $29,900 | negative |
| DSE4 | 6 | 3 | $57,000 | $32,600 | $38,000 / $21,700 | negative |

**Reading.** These are labour savings only. Break-even capex excludes cell maintenance, software, power and other running costs, so the true break-even is lower; volumes are the public sample's (§1). At 500/h a cell replaces about 1.8 manual sorters at 275/h. The labour case therefore turns on the operator ratio, not the cell count: at one operator per cell, a DLA7 cell pays back in 24 months if it costs under about $35k; with one operator tending two cells, under about $59k; at two operators per cell, labour alone never pays it back. At 300/h manual, DLA7's break-even falls to $27.9k (1 op) and $52.4k (0.5 op). Cost of one cell short: see §5 (e.g. DLA7 loses 823 parcels per peak day, needing at least 1 extra manual head across the span to recover them; this is a lower bound because the late parcels cluster in the peak).

### 5h. Week-1 site measurements

Ranked by how little each input has to move (median across stations, relative to its base) before the cell count rises:

1. **Sustained cell rate including rejects and recirculation**: the count rises if it falls about 11% (median); DLA7 flips at 462/h, DSE4 at 491/h. Measure it on the customer's own parcel mix, not the nameplate.
2. **Peak-season volume uplift**: flips at about +13% relative volume (DLA7 at 19% uplift, DSE4 at 13%). Get the customer's last peak, by route.
3. **Inbound trailer arrival curve**: if inbound starts about 18% later (DLA7 2.44 h instead of 3 h before departure), the count rises. This is the synthetic assumption; replace it with the trailer schedule and scan timestamps.

Items 1 and 2 are nearly the same lever (a cell-rate drop of 11% equals about 12% more volume per cell), so in practice they are one measurement of load against capacity. The cutoff buffer (median 34% margin) and the inbound close time (flip at only 3 of 6 stations) matter less. Flip points use 4 replications per point, so a flip within a few percent of the base (DSE4 cell rate, 491/h) is within simulation noise.

### 5i. P90 volume forecast: a trained quantile model against simple rules

Sizing turns on one number per departure wave: how many parcels the 90th-percentile day puts on the routes leaving in that hour. §2 builds the design day from history by hand. This section trains a model to forecast that P90 ahead of time and checks it the way a sizing decision would: by the cells it buys and the parcels it leaves late. Code: `sizer/forecast.py`, `scripts/forecast.py`; results: `public/data/forecast.json`.

**Task.** Forecast the P90 of parcel volume for date $D$ at origin $O = D - h$, for $h$ = 1 day and $h$ = 7 days, at three grains: station-day, **wave** (station × date × local departure hour) and single route. Known at the origin: the planned route count and departure hours for $D$ (stations plan routes with their delivery partners ahead of the day; in this sample the "planned" count is the sampled count, see §7), the vehicle mix (share of the larger van class), weekday, and the station's history up to and including $O$. Nothing dated after $O$ enters a feature (unit test perturbs every later day and checks the features do not move).

**Model.** Gradient-boosted trees with quantile (pinball) loss, $q = 0.9$ (scikit-learn `HistGradientBoostingRegressor`, 300 trees, 15 leaves, learning rate 0.04, min 20 per leaf). It forecasts packages per route and multiplies by the planned route count. Because the route count is known, $q_{0.9}(y) = R \cdot q_{0.9}(y/R)$ exactly, and training with weight $R$ makes the training loss the pinball loss on $y$. Features: station (categorical), weekday, departure hour, routes in the unit, mean vehicle capacity, large-van share, routes today ÷ station's mean routes, station packages per route (last 7 days, all history, last day, same weekday last observed, and its day-to-day s.d.), station packages per route for that hour, and the all-station weekday effect. Pooled over all 17 stations.

**Baselines** (all forecast $y$ for the same unit):
1. **Trailing mean × 1.3**: mean of the unit's volume over observed days in $(O-7, O]$, times 1.3.
2. **Same weekday last week**: the unit's volume on $D-7$ (else $D-14$) if it is on or before the origin; otherwise the unscaled trailing mean.
3. **Routes × packages per route, calibrated** (the honest simple rule, and what §2 does by hand): $R \cdot \bar n_{7}\cdot k$, with $\bar n_7$ the station's trailing 7-day packages per route and $k$ the 90th percentile of $y / (R\bar n_7)$ on the training fold only.
4. **Same, per departure hour**: as 3 but with the station's packages per route for that hour.

**Validation.** Rolling origin with whole dates as blocks: five test blocks of five consecutive dates (2018-08-02 to 2018-08-26); each fold trains only on units dated on or before (first test date − $h$). A test unit needs at least 3 observed history days. Score = mean pinball loss at $q = 0.9$ (lower is better), plus coverage (share of actuals at or below the forecast; target 0.90). Uncertainty: paired bootstrap over test dates (2,000 resamples of whole dates) on the loss difference.

**Forecast accuracy (all 17 stations; pinball loss in parcels, coverage in brackets):**

| Grain, horizon | Units | Model | Trailing mean × 1.3 | Same weekday last week | Routes × ppr, calibrated | Routes × hour ppr | Model vs routes × ppr: loss reduction (90% CI) |
|---|---|---|---|---|---|---|---|
| Day, 1 d | 299 | 25.2 (0.85) | 278.0 (0.71) | 640.4 (0.44) | 26.2 (0.91) | – | 3.8% (−6.0% to 12.6%) **not significant** |
| Day, 7 d | 221 | 31.5 (0.83) | 406.0 (0.58) | 665.5 (0.44) | 32.4 (0.91) | – | 2.8% (−7.8% to 12.4%) **not significant** |
| **Wave, 1 d** | 835 | **11.5** (0.87) | 181.3 (0.56) | 334.6 (0.39) | 14.6 (0.90) | 15.7 (0.94) | **21.1% (15.9% to 26.1%)** |
| **Wave, 7 d** | 835 | **13.3** (0.87) | 228.1 (0.53) | 334.8 (0.39) | 16.7 (0.92) | 18.8 (0.96) | **20.5% (15.9% to 25.2%)** |
| Route, 1 d | 3,861 | 4.6 (0.89) | 7.4 (1.00) | 10.3 (0.55) | 4.9 (0.90) | 5.1 (0.94) | 5.7% (4.6% to 6.8%) |
| Route, 7 d | 3,861 | 4.8 (0.90) | 7.9 (1.00) | 10.3 (0.55) | 5.0 (0.90) | 5.1 (0.94) | 5.8% (4.5% to 7.2%) |

On the six sized stations alone the wave-level reduction is 26.7% (19.1% to 33.5%) at 1 day and 24.2% (18.3% to 29.9%) at 7 days.

**Reading.**
- **The two naive rules are not usable here**, and the reason is §2's coverage finding: they ignore how many routes leave that day, which explains 99% of daily volume. "Same weekday last week" covers the actual only 39–44% of the time. Beating them is easy and is not the claim.
- **At the day grain the model does not beat the honest rule.** The 90% interval on the difference spans zero at both horizons, and the model's coverage (0.83–0.85) is below target. For a daily total, routes × packages per route × one calibrated multiplier is as good as the model.
- **At the wave grain, which is what sizes a cell bank, the model wins by about a fifth**, at both horizons, with the whole interval above zero. Why: one multiplier $k$ cannot fit waves of different sizes. A wave of one route is relatively noisier than a wave of ten. Split by routes in the wave (1-day horizon): for single-route waves the simple rule covers only 0.78 of actuals; for waves of 7 or more routes it covers 0.99 at 12.5% above actual. The model's margin over actual shrinks from 12.9% to 6.1% as waves grow, with coverage 0.86 and 0.91. That is exactly where cells are decided, because the big waves set the peak.
- At the route grain the gain is small but significant (about 6%).
- The model's coverage is slightly below nominal at the wave grain (0.87 vs 0.90). It trades a few more small misses for much less over-forecast on big waves. The next table shows that this does not turn into late parcels.

**Cell-count consequence.** For each of the 122 test station-days at the six sized stations: build a forecast day from the real departure times with each route's count set to its wave forecast ÷ routes in the wave (robot share only), find the smallest FIFO bank with < 1% late (§5c, 2 replications), then run the same simulation on the day's **real** per-route counts with that bank (4 replications) and record the late share. "Needed" is the same search run on the real counts. No peak uplift here: these are observed days.

| 1-day horizon, 122 station-days | Cell-days bought (needed: 379) | Days ≥ 1% late | Mean / worst late share | Cells over need | Cells under need | Days sized exactly |
|---|---|---|---|---|---|---|
| **Quantile model** | **400** | **0%** | 0.01% / 0.7% | **21** | 0 | **83%** |
| Routes × ppr, calibrated | 422 | 0% | 0.00% / 0.0% | 43 | 0 | 65% |
| Routes × hour ppr | 428 | 0% | 0.00% / 0.0% | 49 | 0 | 60% |
| Trailing mean × 1.3 | 437 | 15% | 2.2% / 36.9% | 76 | 18 | 41% |
| Same weekday last week | 352 | 44% | 9.7% / 63.4% | 37 | 64 | 33% |

At a 7-day horizon: model 410 cell-days (31 over, 0 under, 75% exact); routes × ppr 431 (52 over, 0 under, 58% exact); trailing mean × 1.3 413 cell-days but 25% of days ≥ 1% late (worst 57%).

- **Against the honest rule**, the model buys half the surplus cells (21 against 43 cell-days over need) with no extra late days. Absolute cell error per station-day falls by 0.18 cells (90% CI 0.13 to 0.23; 0.17, CI 0.11 to 0.24, at 7 days), bootstrap over test dates. Per station (1-day): DLA7 90 vs 96 cell-days over 16 days (need 84), DBO3 65 vs 68 (60), DLA9 73 vs 79 (72), DLA8 33 vs 36 (33), DSE4 70 vs 73 (70), DSE5 69 vs 70 (60).
- **The naive rules fail in both directions at once**: trailing mean × 1.3 buys more cells than the model and still leaves 15% of days with over 1% of parcels late, because it over-sizes small-coverage days and under-sizes big ones.
- What this means for a proposal: on a day-ahead or week-ahead basis, a wave-level quantile forecast sizes the bank right on about four days in five, against two in three for the hand rule, without adding late parcels. For the one-off design-day number in §5 the hand-built design day stays, because a single P90 day does not need a forecast.

## 6. Validation

All figures are from `public/data/validation.json`, written by `pipeline/scripts/validate.py`.

1. **Hand calculation (DLA7 design day).** $V^{*}$ = 12,537, $e$ = 0.0234, $T$ = 4.392 h. $12{,}537 \times 0.9766 / (4.392 \times 500) = 5.58 \Rightarrow 6$ cells. Tool: 6. Match.
2. **Deadline floor by hand** (unit test). One route, 1,000 parcels arriving uniformly over $[D-3\,\text{h}, D-1\,\text{h}]$, due $D-0.5$ h, $\mu$ = 500/h: the worst window is the full 2.5 h, $1000/(500 \times 2.5) = 0.8 \Rightarrow 1$ cell. Two such routes of 1,500: 2.4 ⇒ 3. Allowing 600 late: 1.92 ⇒ 2.
3. **EDF vs FIFO trace by hand** (unit test). Two servers, unit service; four parcels at $t=0$ due at 10, one at $t=0.5$ due at 2. FIFO finishes the last parcel at 3 (late); EDF serves it at $t=1$ and meets every deadline. Priority dispatch keyed on arrival order reproduces the FIFO simulator exactly.
4. **Ladder on the real stations.** 1%-late floor ≤ EDF ≤ FIFO at all six (asserted in a test on the exported results).
5. **DES vs Erlang C theory** (Poisson arrivals, exponential service, 200k parcels, 10% warm-up dropped):

   | λ/h | c | P(wait) theory | P(wait) sim | Wq theory (s) | Wq sim (s) |
   |---|---|---|---|---|---|
   | 1,400 | 4 | 0.429 | 0.425 | 2.57 | 2.48 |
   | 1,800 | 4 | 0.788 | 0.785 | 14.18 | 14.06 |
   | 4,000 | 9 | 0.653 | 0.646 | 4.70 | 4.66 |

6. **Little's law** $L_q = \lambda W_q$, with $L_q$ sampled at 50,000 random instants: 0.974 vs 0.965; 7.10 vs 7.04; 5.24 vs 5.19 (all within 1%).
7. **Factor-split time holdout.** Train on days before 2018-08-15, test on the later days (3 test days at DLA7, DBO3 and DLA8; 12 at the others). Mean sampled routes per day rose 30–81% at 5 of 6 stations (DLA8 fell 10%), while packages per route changed by −1% to −11%. The apparent volume trend therefore comes from sample coverage, not demand. With 3 test days at half the stations, this is a consistency check, not a forecast test.
8. **Forecast validation** (§5i): rolling-origin folds of whole dates, training strictly before (first test date − horizon); a test perturbs every day after the origin and checks the features do not change; pinball loss and the naive baselines are checked by hand in unit tests; bootstrap over whole test dates.
9. **Reconciliation.** Parsed package count equals the raw key count (1,457,175).

Tests: `pipeline/tests/` (33 pytest tests): Erlang C textbook value (A=2, c=3 → 4/9), M/M/1 reduction, instability flag, hand-calc rounding, Erlang monotonicity, DES vs Erlang C, Little's law, a single-server trace worked by hand, gamma mean/CV, wave-window bounds, monotonicity in *c*, NaN-filter split points, ingest on a fixture, envelope box rule, deadline floor by hand, floor ≥ hand rule and zero-late impossible below the floor, EDF vs FIFO hand trace, arrival-keyed priority = FIFO, EDF never worse than FIFO on a wave, coverage diagnostic, bootstrap interval coverage, bootstrap days use real departure sets, ladder order on the exported results, labour case by hand; forecast: pinball loss by hand (y = 10, 20; f = 12, 15; q = 0.9 → 0.2 and 4.5, mean 2.35), trailing-mean and last-week baselines by hand, features by hand, no feature reads past the origin (h = 1 and 7), consecutive folds, block bootstrap by hand, the model learns an hour effect a flat rule misses (synthetic fixture, test only), exported forecast consistency.

## 7. Limitations

- Volumes are the public route sample, not full station throughput (§1). The design route count is a sample-coverage bound with a bootstrap interval, not the station's true route count.
- Inbound timing is synthetic (uniform 3 h → 1 h before each real departure). The wave ratio, the floor and the EDF saving all rest on it; §5f gives the flip points, and the inbound curve is the third item on the week-1 list.
- Only 29–39 days per station, one summer. A per-station daily forecast is not supported by ~30 points; the forecast in §5i is pooled over 17 stations and scored at the wave and route grain, where there are 835 and 3,861 test units. At the day grain it does not beat the simple rule.
- The forecast treats the day's route count and departure hours as known in advance. In this sample that count is the number of sampled routes, so the forecast's skill at following coverage swings would, at a real station, be skill at following its planned route count. Test period: 25 dates in one August.
- The simulation pools cells behind one queue. Destination-to-cell assignment and recirculation are not simulated and can only raise the count; at DLA7 destinations already bind at 7 cells with 8 per cell, which cancels the EDF saving there.
- The bootstrap design days use FIFO only with 2 replications each; the EDF ladder runs on the point design day only. Sensitivity flip points use 4 replications per point.
- The break-even capex is labour-only; it ignores cell maintenance, software and other running costs. Cost of one cell short gives overflow heads only as a lower bound.
- The envelope is a parametric box with no weight or material (polybag, irregular) rules; the dataset has no weights.
- Cell rate, manual rate and wage are published figures, not measured here.

## Business-case inputs (exported for the UI)
Manual sorter rate 275–300 parcels/h (midpoint 287.5, published industry figure); wage $18.10/h (BLS OEWS May 2023 national median, SOC 53-7062, public domain). Capex per cell is never assumed; §5g reports the break-even capex per cell instead. Payback months $= 12 \cdot \text{capex} / (\text{annual manual labour} - \text{annual robot labour} - \text{opex})$.
