# Cell-Sizing Recipe

**Question.** How many robotic sort cells does a delivery station need to make every departure on a busy day, and how big a safety margin should the volume forecast carry?

**Answer, measured on 899,387 real parcels from six delivery stations.** Sizing on average throughput (peak-day volume divided by the sort window) came up one cell short at 3 of 6 stations in simulation. One cell short left 5.5–34% of parcels late, with 64–100% of routes holding a late parcel. A P90 margin that shrinks with wave size fixes it: replayed on 122 held-out station-days, it bought 403 cell-days against 379 needed (24 surplus), where one flat margin bought 422 (43 surplus). No day reached 1% late. A trained quantile model bought 400, within noise of the rule, so the rule fits in a spreadsheet.

Caveats that stay attached: inbound timing is a stated assumption (each route's parcels arrive 3 h to 1 h before its real departure); volumes are the public route sample, not total station throughput; the wave-size buckets were chosen after the per-size breakdown had been seen on the test folds, which can only favour the rule (disclosed in `pipeline/sizer/forecast.py`).

## The playbook (one page, five steps)

1. **Check the data before sizing.** If daily volume tracks the number of routes (here correlation 0.986–0.997), size on routes × parcels per route, not on daily totals. Look for missing days.
2. **Forecast each departure wave's P90 with a margin that shrinks with wave size.** A wave is the routes leaving in one local hour.

   | Wave size | P90 margin on routes × trailing parcels per route |
   |---|---|
   | 1 route | ×1.15 |
   | 2–3 routes | ×1.10 |
   | 4–6 routes | ×1.09 |
   | 7+ routes | ×1.05 |

   Fitted on public data (last 1-day-ahead fold; 7-day-ahead: ×1.15 / 1.09 / 1.07 / 1.03). Refit on the site's own history when it has 14 or more days.
3. **Size against the departure waves, not the day.** Read the ladder in order: scheduling floor (fewest cells any policy could use), earliest-cutoff-first induction, first-come-first-served, then the count that clears 90% of bootstrap peak days. Check destinations per cell: it can bind before throughput does.
4. **Measure these first on the site visit, in this order:** sustained cell rate (the count flips about 11% below nameplate, median over six stations), peak uplift (about 13%), then the inbound arrival curve (about 18%). Pick-time variability never flips it (CV 0.1 to 1.0).
5. **Price the case backwards.** Report the break-even capex per cell for an 18, 24 and 36-month payback at 0.5, 1 and 2 operators per cell, labour only, with no vendor price assumed.

## Decision rules (thresholds from the measured results)

| If | Then | Evidence |
|---|---|---|
| Daily volume vs route count correlation ≥ 0.9 | Build the design day from routes × parcels per route, with day-block bootstrap intervals | 0.986–0.997 at all six stations |
| The proposal sized cells on average throughput | Run the wave ladder before signing: that rule was one cell short of FIFO at 3 of 6 stations | `summary.json` cells_hand_p90 vs cells_fifo20 |
| Earliest-cutoff-first is available in the controls | Size on EDF: it hit the scheduling floor at 6 of 6 stations and saved a cell at 4 of 6 (24 vs 28 cells) | `summary.json` cells_bound_1pct / cells_edf20 / cells_fifo20 |
| Routes ÷ destinations per cell > EDF count | Destinations bind; at 8 per cell the EDF saving held at 3 of 6 | DLA7: 51 routes need 7 cells at 8 per cell |
| Naive forecast (trailing mean × 1.3, same weekday last week) | Do not use: 15% and 44% of days over 1% late | `forecast.json` sizing.h1 |
| Sustained cell rate measured within ~11% of nameplate | The count holds; below that, re-run | `validation.json` week1_ranking |
| Break-even capex at 2 operators per cell is negative | Labour alone never pays back at that staffing; plan for ≤ 1 per cell | DLA7: about $35k at 1 per cell, $59k at 0.5 (24 months) |

## The tool: `size-site`

A thin wrapper over the existing pipeline. The sizing itself is `pipeline/sizer/site.py::size_station()`, the same function `scripts/analyse.py` calls to produce the shipped results.

```bash
cd pipeline
# from the pipeline's cached table of the public data (fast, about 10 s)
OMP_NUM_THREADS=3 .venv/bin/python -I scripts/size_site.py --station DLA7
# from the raw public files, optionally a date range
.venv/bin/python -I scripts/size_site.py --routes route_data.json --packages package_data.json --station DLA7 --from 2018-07-19 --to 2018-08-26
# from a customer export
.venv/bin/python -I scripts/size_site.py --csv site_routes.csv --station SITE
```

CSV columns: `route_id, date, departure_local, packages[, L, W, H]` (cm). Rows with the same route and date are summed, so a per-route or a per-parcel export both work. Without dimensions every parcel is treated as fitting the pick envelope.

Flags (defaults from `sizer/config.py`): `--cell-rate 500 --uplift 0.10 --open 3 --close 1 --cutoff 0.5 --gaylords 8 --ops 0.5,1,2 --wage 18.10`.

Output: `out/size-site-<station>.json` and a one-page `out/size-site-<station>.md` with

- the data check (volume vs routes, parcels per route, envelope fit);
- design-day P90 by wave with the size-aware margin (refit when 14+ days of history, otherwise the shipped multipliers);
- the cell ladder: average-throughput rule, P90 hand rule, floor, EDF, FIFO, 90% of bootstrap peak days, destinations;
- the risk of one cell short (% parcels late, % routes late);
- the measure-first list, ranked by how far each input can move before the count rises;
- break-even capex per cell.

Run on DLA7 it reproduces `public/data/summary.json`: floor 6, EDF 6, FIFO 7, 8 on 90% of peak days; one short leaves 6.7% of parcels late; $34,907 / $59,342 per cell at 24 months (1 and 0.5 operators per cell). `pipeline/tests/test_size_site.py` checks this, and that a CSV export of the real DLA7 routes maps back to the same daily volumes. Everything runs offline, with no API keys.

## Week 1 on one customer site

- **Day 1.** With the sales lead, pick one live or recent deal. Get the site's route plan (departure times, routes per wave, parcels per route), a parcel-dimension sample if available, and the sizing spreadsheet the proposal used.
- **Day 2.** Run the data check: does volume track route count, are there missing days? Map the export to the `size-site` CSV; set the cell rate to the product's rated sorts per hour and the site's destinations per cell.
- **Day 3.** Refit the wave-size margins on the site's own history and run the ladder (floor / earliest-cutoff-first / FIFO / 90% of peak days), including the risk of one cell short at the customer's expected peak uplift.
- **Day 4.** Compare against the cell count in the proposal and explain any gap. Turn the flip points into the site-visit checklist (sustained cell rate first). Check sustained rates against data from installed sites.
- **Day 5.** Hand over the one-page recipe filled in for that site, the run, and a template the team can reuse on the next proposal, with the break-even price per cell for the business case.

---
Built on public delivery-station data (Amazon Last Mile Routing Research Challenge 2021, CC BY-NC 4.0). See [METHOD.md](METHOD.md) for equations, assumptions and validation. More work at [ibiraheel.com](https://ibiraheel.com).
