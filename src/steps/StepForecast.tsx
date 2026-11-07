import { useState } from 'react'
import type { Forecast, MethodCell, MethodKey } from '../data'
import { METHODS, fix, pct } from '../data'
import { useWidth } from '../hooks'
import { barPath } from '../viz'
import { Step } from '../Step'

const ci = (a: number[]) => `${pct(a[0])} to ${pct(a[1])}`

function DayBoard({ f, station, method }: { f: Forecast; station: string; method: MethodKey }) {
  const rows = f.sizing.h1.rows.filter(r => r.station === station)
  const maxCells = Math.max(...rows.map(r => Math.max(r.cells_needed_actual, (r[method] as MethodCell).cells)))
  return (
    <div className="dboard" role="table" aria-label={`Held-out days at ${station}: cells needed and cells bought by ${METHODS.find(m => m.key === method)!.label}`}>
      <div className="dboard-row dboard-head" role="row">
        <span role="columnheader">Date</span><span role="columnheader" className="hide-sm">Routes</span><span role="columnheader">Need</span><span role="columnheader">Cells bought</span><span role="columnheader">Late</span>
      </div>
      {rows.map(r => {
        const m = r[method] as MethodCell
        const need = r.cells_needed_actual
        const slots = Array.from({ length: maxCells }, (_, i) => {
          if (i < Math.min(need, m.cells)) return 'ok'
          if (i < m.cells) return 'over'
          if (i < need) return 'short'
          return 'none'
        })
        const lateBad = m.late_share >= 0.01
        return (
          <div className="dboard-row" role="row" key={r.date}>
            <span role="cell" className="dboard-date">{r.date.slice(5).replace('-', '/')}</span>
            <span role="cell" className="hide-sm">{r.routes}</span>
            <span role="cell">{need}</span>
            <span role="cell" className="slots" aria-label={`${m.cells} bought for ${need} needed`}>
              {slots.map((k, i) => <i key={i} className={`slot slot-${k}`} />)}
              <em>{m.cells}</em>
            </span>
            <span role="cell" className={lateBad ? 'late-bad' : m.late_share > 0 ? 'late-some' : 'late-none'}>{m.late_share === 0 ? '0' : pct(m.late_share, m.late_share < 0.01 ? 1 : 0)}</span>
          </div>
        )
      })}
    </div>
  )
}

function Tally({ f, method }: { f: Forecast; method: MethodKey }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const sm = f.sizing.h1.summary
  const max = Math.max(...METHODS.map(m => sm[m.key].excess_cells + sm[m.key].under_cells))
  const lw = w < 560 ? 0 : 150
  const bw = Math.max(80, w < 560 ? w - 8 : (w - lw) * 0.42)
  const sc = (v: number) => (v / max) * bw
  return (
    <div ref={ref} className="tally">
      <p className="tally-cap">All six stations, {f.sizing.h1.station_days} held-out station-days, one day ahead. Cells needed: {sm.model.cell_days_needed} cell-days.</p>
      <ul>
        {METHODS.map(m => {
          const r = sm[m.key]
          return (
            <li key={m.key} className={m.key === method ? 'on' : undefined}>
              <span className="tally-name">{m.short}</span>
              <svg width={bw + 4} height={14} aria-hidden="true">
                <path className="bar-over" d={barPath(0, 1, sc(r.excess_cells), 12, r.under_cells ? 0 : 3)} />
                {r.under_cells > 0 && <path className="bar-short" d={barPath(sc(r.excess_cells) + 2, 1, sc(r.under_cells) - 2, 12, 3)} />}
              </svg>
              <span className="tally-val">{r.excess_cells} over{r.under_cells ? `, ${r.under_cells} short` : ''} · {pct(r.exact_days_share, 0)} exact · {pct(r.under_days_share, 0)} of days ≥1% late</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function StepForecast({ f, station }: { f: Forecast; station: string }) {
  const [method, setMethod] = useState<MethodKey>('model')
  const sm = f.sizing.h1.summary
  const w1 = f.levels.wave_h1, w7 = f.levels.wave_h7, d1 = f.levels.day_h1
  const vsOne = w1.model_vs.routes_x_ppr_calibrated
  const vsSize1 = w1.model_vs.routes_x_ppr_calibrated_by_wave_size
  const vsSize7 = w7.model_vs.routes_x_ppr_calibrated_by_wave_size
  const vsDay = d1.model_vs.routes_x_ppr_calibrated
  const buckets = ['1 route', '2–3 routes', '4–6 routes', '7+ routes']
  const kMean = (lv: typeof w1, b: string) => lv.folds.reduce((a, fo) => a + fo.calibration_k_by_wave_size[b], 0) / lv.folds.length
  const cur = METHODS.find(m => m.key === method)!
  return (
    <Step n={5} id="forecast" title="AI forecast against the rule"
      lede={<>A gradient-boosted quantile model forecasts each departure wave’s P90 a day ahead. Replayed on the real parcels of {f.sizing.h1.station_days} held-out days, it bought <b>{sm.model.excess_cells} surplus cell-days</b> against {sm.routes_x_ppr_calibrated.excess_cells} for the one-margin rule, with no day reaching 1% late.</>}
      details={<>
        <div className="scroll"><table>
          <caption>Wave-level P90 forecast, 17 stations, {w1.units} held-out waves: pinball loss in parcels (lower is better), coverage in brackets (target 0.90)</caption>
          <thead><tr><th>Method</th><th>1 day ahead</th><th>7 days ahead</th></tr></thead>
          <tbody>
            {[...METHODS, { key: 'same_weekday_last_week', label: 'Same weekday last week' }].map(m => (
              <tr key={m.key} className={m.key === 'model' ? 'row-on' : undefined}><td>{m.label}</td><td>{fix(w1.scores[m.key].pinball, 1)} ({fix(w1.scores[m.key].coverage)})</td><td>{fix(w7.scores[m.key].pinball, 1)} ({fix(w7.scores[m.key].coverage)})</td></tr>
            ))}
          </tbody>
        </table></div>
        <ul className="facts">
          <li>Model vs one-margin rule, wave loss: {pct(vsOne.rel_improvement)} lower (90% CI {ci(vsOne.rel_improvement_ci90)}).</li>
          <li>Model vs size-aware rule: {pct(vsSize1.rel_improvement)} lower at 1 day (CI {ci(vsSize1.rel_improvement_ci90)}); {pct(vsSize7.rel_improvement)} at 7 days (CI {ci(vsSize7.rel_improvement_ci90)}, not significant). Cell-days bought: {sm.model.cell_days} vs {sm.routes_x_ppr_calibrated_by_wave_size.cell_days}.</li>
          <li>Daily totals: the model does not beat the one-margin rule ({pct(vsDay.rel_improvement)}, CI {ci(vsDay.rel_improvement_ci90)}).</li>
          <li>The model’s wave coverage is {fix(w1.scores.model.coverage)} against a 0.90 target; its worst replayed day was {pct(sm.model.max_late_share)} late, against {pct(sm.routes_x_ppr_calibrated.max_late_share)} for the one-margin rule.</li>
        </ul>
        <div className="scroll"><table>
          <caption>Size-aware rule: P90 margin per wave-size bucket, mean over the 5 training folds (1 day ahead)</caption>
          <thead><tr>{buckets.map(b => <th key={b}>{b}</th>)}</tr></thead>
          <tbody><tr>{['0', '1', '2', '3'].map(b => <td key={b}>× {fix(kMean(w1, b), 3)}</td>)}</tr></tbody>
        </table></div>
        <p className="note">Model: {f.model}, pooled over {f.stations_in_training.length} stations, {f.features.length} features known at the forecast origin (planned routes, departure hour, vehicle mix, station history). Validation: rolling origin on whole dates, training only on dates before the test block; paired 2,000-resample date-block bootstrap. “Exact” means the bank bought equals the bank the real parcels needed.</p>
      </>}>
      <div className="seg" role="radiogroup" aria-label="Forecast method">
        {METHODS.map(m => (
          <button key={m.key} type="button" role="radio" aria-checked={method === m.key} className={method === m.key ? 'on' : undefined} onClick={() => setMethod(m.key)}>{m.label}</button>
        ))}
      </div>
      <p className="seg-note">{cur.note}.</p>
      <DayBoard f={f} station={station} method={method} />
      <p className="legend"><span className="lg"><i className="sw sw-slot" />needed and bought</span><span className="lg"><i className="sw sw-surplus" />surplus cell</span><span className="lg"><i className="sw sw-short" />cell short</span></p>
      <Tally f={f} method={method} />
      <p className="verdict-text"><b>The honest result:</b> a simple rule with one margin per wave size buys {sm.routes_x_ppr_calibrated_by_wave_size.excess_cells} surplus cell-days, close to the model’s {sm.model.excess_cells}. Most of the gain is that a P90 margin must shrink as waves grow; the model learns that, and a hand rule can be told it.</p>
    </Step>
  )
}
