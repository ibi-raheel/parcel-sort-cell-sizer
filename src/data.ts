// Types for the precomputed pipeline output in public/data. Nothing here computes a result;
// the page only reads, formats and (where noted) sums or averages shipped values.

export type CurvePoint = { cells: number; miss_share: number; miss_ci95: number; routes_late_share: number; p95_wait_min: number }
export type Ladder = {
  bound: number; bound_1pct: number; fifo: number; edf: number; edf_saves_cells: number
  curves: { fifo: CurvePoint[]; edf: CurvePoint[] }; reps: number
}
export type Tornado = { param: string; base: number; sweep: Record<string, number>; flip_up_at: number | null; flip_down_at: number | null; range_searched: number[] }
export type LabourCase = { manual_rate_h: number; ops_per_cell: number; manual_heads: number; robot_side_heads: number; annual_labour_delta_usd: number; breakeven_capex_per_cell_usd: Record<string, number> }
export type Coverage = {
  corr_packages_routes: number; packages_per_route_mean: number; packages_per_route_cv: number
  routes_min: number; routes_max: number; p90_over_mean_packages: number; p90_over_mean_packages_well_covered_days: number
  well_covered_days: number; p90_over_mean_packages_per_route: number
}
export type OneShort = { cells: number; late_parcels: number; late_share: number; routes_late_share: number; overflow_heads_at_least: number }

export type StationSummary = {
  station: string; days: number; packages_total: number
  volume: { mean: number; p50: number; p90: number; max: number; p90_peak: number; p90_over_mean: number }
  sortable_share: number; pts_per_5cm: number; peak_rate_over_mean_rate: number
  cells_hand_mean: number; cells_hand_p90: number; cells_erlang: number; cells_des: number; cells_for_destinations: number
  cells_bound_1pct: number; cells_edf20: number; cells_fifo20: number; cells_90pct_confidence: number
  p_ok: Record<string, number>; one_cell_short: OneShort; labour_cases: LabourCase[]
  design_routes: number; coverage: Coverage
  design_basis: { packages_per_route: number; packages_per_route_ci90: number[]; design_routes: number; design_routes_ci90: number[]; n_boot: number }
}

export type Summary = {
  stations: StationSummary[]
  assumptions: { CELL_RATE_H: number; CUTOFF_H: number; ENVELOPE: { max_l: number; max_m: number; max_s: number }; GAYLORDS_PER_CELL: number; INBOUND_OPEN_H: number; INBOUND_CLOSE_H: number; MANUAL_RATE_H: number; MISS_TARGET: number; PEAK_UPLIFT: number; SERVICE_CV: number; WAGE_H: number; DAYS_PER_YEAR: number }
  dataset: { name: string; url: string; licence: string; routes: number; packages: number; stations: number; dates: string[]; reconciliation: { parsed: number; raw_key_count: number }; all_sortable_share: number }
}

export type Station = {
  station: string; days: number
  daily: { date: string; packages: number }[]
  daily_routes: number[]
  coverage: Coverage
  design_basis: StationSummary['design_basis']
  volume: StationSummary['volume']
  envelope: { default: { max_l: number; max_m: number; max_s: number }; sortable_share: number; sweep_longest: { l_cm: number[]; share: number[] }; pts_per_5cm_at_default: number; sample_cm: [number, number, number][]; sample_share: number }
  design_day: { date: string; observed_packages: number; design_packages: number; robot_packages: number; routes: number; departure_spread_h: number; sort_span_h: number; lambda_per_h: number; wave_profile_15min: number[]; peak_15min_rate_per_h: number }
  sizing: { cells_hand_p90: number; cells_hand_mean: number; cells_erlang: number; cells_des: number; cells_for_destinations: number; des_curve: CurvePoint[]; ladder: Ladder; bootstrap_days: { n_days: number; cells_needed_hist: Record<string, number>; p_ok: Record<string, number>; cells_90pct_confidence: number } }
  sensitivity: { cells_base: number; reps: number; tornado: Tornado[] }
  business: { paid_hours_per_day: number; cases: LabourCase[]; one_cell_short: OneShort; cells: number; manual: Record<string, { manual_heads_all: number; manual_heads_exceptions: number }> }
}

export type Score = { pinball: number; coverage: number; forecast_over_actual: number }
export type Compare = { rel_improvement: number; rel_improvement_ci90: number[]; p_a_better: number; n_units: number }
export type Level = {
  level: string; horizon_days: number; units: number
  folds: { calibration_k: number; calibration_k_by_wave_size: Record<string, number> }[]
  scores: Record<string, Score>
  model_vs: Record<string, Compare>
}
export type SizingSummary = { cell_days: number; cell_days_needed: number; under_days_share: number; under_cells: number; excess_cells: number; exact_days_share: number; mean_late_share: number; max_late_share: number }
export type SizingRow = { station: string; date: string; routes: number; packages: number; cells_needed_actual: number } & Record<string, unknown>
export type Forecast = {
  quantile: number; features: string[]; model: string; validation: string
  levels: Record<string, Level>
  sizing: Record<'h1' | 'h7', { station_days: number; summary: Record<string, SizingSummary>; rows: SizingRow[]; model_vs: Record<string, { abs_cell_error: Compare & { mean_diff: number; mean_diff_ci90: number[] } }> }>
  stations_in_training: string[]; sized_stations: string[]
}

export type Validation = {
  hand_calc: { station: string; design_packages: number; sort_span_h: number; exception_rate: number; rate_h: number; by_hand: string; by_hand_value: number; tool_value: number }
  mmc: { lam_h: number; mu_h: number; c: number; pwait_theory: number; pwait_sim: number; wq_theory_min: number; wq_sim_min: number; littles_Lq: number; littles_lambdaW: number }[]
  ladder: { station: string; bound: number; bound_1pct: number; edf: number; fifo: number; cells_90pct: number }[]
  week1_ranking: { param: string; median_rel_margin: number; stations_with_flip: number }[]
  coverage: (Coverage & { station: string })[]
  holdout: { station: string; routes_change: number; ppr_change: number; test_days: number }[]
  reconciliation: { parsed: number; raw_key_count: number }
}

export type MethodCell = { cells: number; late_share: number; routes_late_share: number }

const base = import.meta.env.BASE_URL
export const getJSON = <T,>(name: string): Promise<T> =>
  fetch(`${base}data/${name}`).then(r => { if (!r.ok) throw new Error(`${name}: HTTP ${r.status}`); return r.json() as Promise<T> })

// ---- formatting -------------------------------------------------------------
export const int = (n: number) => Math.round(n).toLocaleString('en-US')
export const pct = (x: number, d = 1) => `${(100 * x).toFixed(d)}%`
export const fix = (x: number, d = 2) => x.toFixed(d)
export const usd = (n: number) => `$${(Math.round(n / 100) / 10).toFixed(1)}k`

export const METHODS = [
  { key: 'model', label: 'Quantile model', short: 'Model', note: 'Gradient-boosted trees, pinball loss at q = 0.9' },
  { key: 'routes_x_ppr_calibrated_by_wave_size', label: 'Size-aware rule', short: 'Size-aware rule', note: 'Routes × parcels per route × one margin per wave size' },
  { key: 'routes_x_ppr_calibrated', label: 'One-margin rule', short: 'One-margin rule', note: 'Routes × parcels per route × one calibrated margin' },
  { key: 'trailing_mean_x1.3', label: 'Trailing mean × 1.3', short: 'Trailing mean × 1.3', note: 'Last 7 days’ mean volume, plus 30%' },
] as const
export type MethodKey = (typeof METHODS)[number]['key']

export const STEPS = [
  { id: 'day', title: 'A station’s day' },
  { id: 'fit', title: 'Parcels that fit' },
  { id: 'wave', title: 'Waves pile up' },
  { id: 'cells', title: 'How many cells' },
  { id: 'forecast', title: 'Forecast vs rule' },
  { id: 'saved', title: 'Cells saved, risk' },
  { id: 'know', title: 'How we know' },
  { id: 'solution', title: 'The solution' },
] as const
