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

**Stations analysed.** The six stations with at least 28 observed days and the most packages: DLA7, DLA9, DBO3, DSE5, DLA8, DSE4.

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

- **The ladder validates the simulation's extra cell.** The 1%-late floor is a hard limit for any policy. EDF reaches it at all six stations. FIFO sits one cell above it at 4 of 6 (DLA7, DLA9, DSE5, DLA8). So the extra cell in the FIFO simulation is real and not a modelling artefact: it is the cost of serving parcels in arrival order when departures are clustered.
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

**Reading.** At 500/h a cell replaces about 1.8 manual sorters at 275/h. The labour case therefore turns on the operator ratio, not the cell count: at one operator per cell, a DLA7 cell pays back in 24 months if it costs under about $35k; with one operator tending two cells, under about $59k; at two operators per cell, labour alone never pays it back. At 300/h manual, DLA7's break-even falls to $27.9k (1 op) and $52.4k (0.5 op). Cost of one cell short: see §5 (e.g. DLA7 loses 823 parcels per peak day, needing at least 1 extra manual head across the span to recover them; this is a lower bound because the late parcels cluster in the peak).

### 5h. Week-1 site measurements

Ranked by how little each input has to move (median across stations, relative to its base) before the cell count rises:

1. **Sustained cell rate including rejects and recirculation**: the count rises if it falls about 11% (median); DLA7 flips at 462/h, DSE4 at 491/h. Measure it on the customer's own parcel mix, not the nameplate.
2. **Peak-season volume uplift**: flips at about +13% relative volume (DLA7 at 19% uplift, DSE4 at 13%). Get the customer's last peak, by route.
3. **Inbound trailer arrival curve**: if inbound starts about 18% later (DLA7 2.44 h instead of 3 h before departure), the count rises. This is the synthetic assumption; replace it with the trailer schedule and scan timestamps.

The cutoff buffer (median 34% margin) and the inbound close time (flip at only 3 of 6 stations) matter less.

## Business-case inputs (exported for the UI)
Manual sorter rate 275–300 parcels/h (midpoint 287.5, published industry figure); wage $18.10/h (BLS OEWS May 2023 national median, SOC 53-7062, public domain). Capex per cell is never assumed; §5g reports the break-even capex per cell instead. Payback months $= 12 \cdot \text{capex} / (\text{annual manual labour} - \text{annual robot labour} - \text{opex})$.
