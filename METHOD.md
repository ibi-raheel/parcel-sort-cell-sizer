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

## 2. Volume profile

For station *s*, daily volume $V_{s,d} = \sum_{r \in s,d} n_r$. We report mean, P50 and P90 over observed days, and the design volume $V^{*} = 1.10 \times V_{P90\text{-day}}$ (peak season 10% above last year). The design day is the observed day whose volume is closest to the P90, so its real route departure times can be used.

| Station | Days | Mean/day | P90/day | P90 ÷ mean |
|---|---|---|---|---|
| DLA7 | 30 | 8,810 | 11,436 | 1.30 |
| DLA9 | 39 | 4,448 | 7,595 | 1.71 |
| DBO3 | 29 | 4,414 | 6,485 | 1.47 |
| DSE5 | 38 | 3,028 | 4,956 | 1.64 |
| DLA8 | 29 | 3,833 | 5,490 | 1.43 |
| DSE4 | 39 | 2,753 | 4,026 | 1.46 |

## 3. Pick-envelope fit

Each package's dimensions are sorted to $L \ge M \ge S$. A package is robot-sortable if
$$L \le L_{max},\quad M \le M_{max},\quad S \le S_{max},\quad S \ge S_{min}.$$
Default envelope 60 × 45 × 35 cm, $S_{min}=0$. **This is an editable assumption, not any vendor's specification.** No weight limit is applied because the dataset has no weights; we do not invent them.

Measured sortable share: 96.4% (DBO3) to 97.7% (DLA7, DLA9); 97.16% over all 1.46 M packages. Sensitivity: moving $L_{max}$ by 5 cm moves the sortable share by only 0.40 to 0.47 points at the default envelope, because the longest-side distribution is already thin beyond 60 cm (P99 longest side = 66 cm). The exception share $e = 1 - \text{share}$ goes to a manual lane.

## 4. Destinations

One sort destination (gaylord or cart) per outbound route. With 8 destinations per cell (configurator range 6–16+), destination count needs $\lceil R/8 \rceil$ cells, where $R$ is the number of routes on the design day. In the sample this is never the binding constraint (DLA7: 52 routes → 7 cells; throughput also needs 7). Zone-prefix counts are exported for a finer sort plan.

## 5. Sizing

Cell rate $\mu = 500$ sorts/h (published configurator figure). Robot volume $\lambda$-total $= V^{*}(1-e)$.

**Inbound shape (synthetic assumption, labelled).** The dataset has no inbound scan times. We tie inbound to the real departures: route *r*'s parcels arrive uniformly in $[D_r - 3\,\text{h},\ D_r - 1\,\text{h}]$ and must be sorted by the cutoff $D_r - 0.5\,\text{h}$. The sort span is therefore $T = (\max D - \min D) + 2\,\text{h}$. Because departures are clustered, the peak 15-minute inbound rate is 1.45–1.96× the span-average rate.

**(a) Spreadsheet rule (hand calculation).**
$$c_{hand} = \left\lceil \frac{V(1-e)}{T\,\mu} \right\rceil$$
computed both for $V^{*}$ (P90 + 10%) and for $1.10\,\bar V$ (the average-day rule).

**(b) Erlang C (M/M/c).** With offered load $a = \lambda/\mu$ and $\rho = a/c$,
$$C(c,a) = \frac{\frac{a^c}{c!}\frac{1}{1-\rho}}{\sum_{k=0}^{c-1}\frac{a^k}{k!} + \frac{a^c}{c!}\frac{1}{1-\rho}},\qquad P(W_q > t) = C(c,a)\,e^{-(c\mu-\lambda)t}.$$
$c_{erlang}$ = smallest *c* with $P(W_q > 0.5\,\text{h}) < 1\%$ at the span-average $\lambda$. (Computed via the stable Erlang B recursion $B_k = aB_{k-1}/(k + aB_{k-1})$.)

**(c) Discrete-event simulation** (`sizer/sim.py`). A pooled bank of *c* identical cells, FIFO, shared infeed. Each arrival in time order takes the cell that frees first, which is exact for G/G/c FIFO. Service times are gamma with mean 7.2 s and CV 0.25 (deterministic plus noise). Arrivals follow the wave shape above at the design day's real departure times. A parcel is late if it finishes after its route's cutoff. $c_{DES}$ = smallest *c* with mean late share < 1% over 8 replications.

### Results (design day, +10% peak, <1% late)

| Station | Mean rule | P90 rule | Erlang C | Wave simulation |
|---|---|---|---|---|
| DLA7 | 5 | 6 | 6 | **7** |
| DLA9 | 3 | 4 | 4 | **5** |
| DBO3 | 3 | 5 | 5 | **5** |
| DSE5 | 2 | 3 | 3 | **4** |
| DLA8 | 2 | 3 | 3 | **4** |
| DSE4 | 3 | 3 | 3 | **3** |

- Sizing on the average day under-builds at 5 of 6 stations, by 1–2 cells (18 cells in total across the six, against 28 from the simulation).
- Even P90-based steady-state sizing (hand rule or Erlang C, which agree everywhere) is one cell short at 4 of 6 stations, because the departure waves concentrate inbound.
- DLA7 detail: with 6 cells, 3.6% of parcels are late and 58% of routes have at least one late parcel; with 7 cells, none are late and the P95 queue wait is 20 min.

## 6. Validation

1. **Hand calculation (DLA7 design day).** $V^{*}$ = 12,542, $e$ = 0.0234, $T$ = 4.589 h. $12{,}542 \times 0.9766 = 12{,}249$; $4.589 \times 500 = 2{,}294$; $12{,}249 / 2{,}294 = 5.34 \Rightarrow 6$ cells. Tool: 6. Match.
2. **DES vs Erlang C theory** (Poisson arrivals, exponential service, 200k parcels, 10% warm-up dropped):

   | λ/h | c | P(wait) theory | P(wait) sim | Wq theory (s) | Wq sim (s) |
   |---|---|---|---|---|---|
   | 1,400 | 4 | 0.429 | 0.425 | 2.57 | 2.48 |
   | 1,800 | 4 | 0.788 | 0.785 | 14.18 | 14.06 |
   | 4,000 | 9 | 0.653 | 0.646 | 4.70 | 4.66 |

3. **Little's law** $L_q = \lambda W_q$, with $L_q$ measured independently by sampling the queue length at 50,000 random instants: 0.974 vs 0.965; 7.10 vs 7.04; 5.24 vs 5.19 (all within 1%).
4. **Time holdout baseline.** Size from days before 2018-08-15, test on the 45 later station-days. The mean rule is exceeded on 37/45 (82%) of later days; the P90 rule on 15/45 (33%). Volume trends up through August in the sample, so P90 alone is not enough: the 10% peak uplift and a trend term matter. This is reported, not hidden.
5. **Reconciliation.** Parsed package count equals the raw key count (1,457,175).

Tests: `pipeline/tests/` (14 pytest tests): Erlang C textbook value (A=2, c=3 → 4/9), M/M/1 reduction, instability flag, hand-calc rounding, DES vs Erlang C, Little's law, a deterministic single-server trace worked by hand, gamma mean/CV, wave-window bounds, monotonicity in *c*, NaN-filter split points, ingest on a fixture, envelope box rule.

## 7. Limitations

- Volumes are the public route sample, not full station throughput (see §1).
- Inbound timing is synthetic (uniform 3 h → 1 h before departure). Real trailer schedules would sharpen the wave and could raise the cell count.
- Only 29–39 days per station, one summer. The P90 is an empirical quantile with wide uncertainty; no ML forecast is used because 30 points per station do not support one honestly.
- Pooled FIFO across cells ignores destination-to-cell assignment and recirculation; both would add load.
- The envelope is a parametric box with no weight or material (polybag, irregular) rules.
- Cell rate and manual rate are published figures, not measured here.

## Business-case inputs (exported for the UI)
Manual sorter rate 275–300 parcels/h (midpoint 287.5, published industry figure); wage $18.10/h (BLS OEWS May 2023 national median, SOC 53-7062, public domain). Capex per cell is a user input with no default claim. Payback months $= 12 \cdot \text{capex} / (\text{annual manual labour} - \text{annual robot labour} - \text{opex})$.
