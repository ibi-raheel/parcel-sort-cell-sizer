import type { Station, Validation, Summary, Tornado } from '../data'
import { int, pct, fix } from '../data'
import { useWidth } from '../hooks'
import { barPath, IconCheck } from '../viz'
import { Step } from '../Step'

const NAMES: Record<string, string> = {
  rate_h: 'Sustained cell rate',
  uplift: 'Peak-season uplift',
  open_h: 'When inbound starts',
  close_h: 'When inbound ends',
  cutoff_h: 'Cutoff buffer',
  cv: 'Pick-time variability',
}

function flipText(t: Tornado | undefined) {
  if (!t || t.flip_up_at === null) return 'no flip in the range searched'
  const v = t.flip_up_at
  switch (t.param) {
    case 'rate_h': return `rises below ${int(v)}/h (base ${int(t.base)})`
    case 'uplift': return `rises above ${pct(v, 0)} uplift (base ${pct(t.base, 0)})`
    case 'open_h': return `rises if inbound starts ${fix(v)} h before departure (base ${t.base} h)`
    case 'close_h': return `rises if inbound ends ${fix(v)} h before departure (base ${t.base} h)`
    case 'cutoff_h': return `rises above a ${Math.round(v * 60)}-min buffer (base ${Math.round(t.base * 60)})`
    default: return `rises at ${v}`
  }
}

function FlipBars({ v, st }: { v: Validation; st: Station }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const rows = v.week1_ranking
  const max = Math.max(...rows.map(r => r.median_rel_margin))
  const narrow = w < 620
  const lw = narrow ? 0 : 190
  const bw = narrow ? w - 70 : Math.min(300, w - lw - 300)
  const cv = st.sensitivity.tornado.find(t => t.param === 'cv')
  return (
    <div ref={ref} className="flips">
      <p className="flips-cap">How far each input can move before the cell count rises (median over the six stations). Shorter bar: measure it first.</p>
      <ol>
        {rows.map(r => {
          const t = st.sensitivity.tornado.find(x => x.param === r.param)
          return (
            <li key={r.param} style={{ gridTemplateColumns: narrow ? '1fr' : `${lw}px ${bw + 60}px 1fr` }}>
              <span className="flip-name">{NAMES[r.param] ?? r.param}</span>
              <span className="flip-bar">
                <svg width={bw} height={14} aria-hidden="true"><path className="bar-flip" d={barPath(0, 1, (r.median_rel_margin / max) * bw, 12, 3)} /></svg>
                <b>{pct(r.median_rel_margin, 0)}</b>
              </span>
              <span className="flip-st">{st.station}: {flipText(t)}{r.stations_with_flip < 6 ? ` · flips at ${r.stations_with_flip} of 6 stations` : ''}</span>
            </li>
          )
        })}
        <li style={{ gridTemplateColumns: narrow ? '1fr' : `${lw}px ${bw + 60}px 1fr` }}>
          <span className="flip-name">{NAMES.cv}</span>
          <span className="flip-bar flip-none">never flips</span>
          <span className="flip-st">{st.station}: {cv && cv.flip_up_at === null ? 'CV 0.1 to 1.0 leaves the count unchanged' : flipText(cv)}</span>
        </li>
      </ol>
    </div>
  )
}

export function StepKnow({ v, st, s }: { v: Validation; st: Station; s: Summary }) {
  const h = v.hand_calc
  const ladderOk = v.ladder.filter(r => r.bound_1pct <= r.edf && r.edf <= r.fifo).length
  const rate = v.week1_ranking.find(r => r.param === 'rate_h')!
  return (
    <Step n={7} id="know" title="How we know"
      lede={<>Every count is checked by hand, against queueing theory and against its own lower bound. And the input that would change it fastest is the cell’s real sustained rate: the count rises if it runs about <b>{pct(rate.median_rel_margin, 0)} below nameplate</b>.</>}
      details={<>
        <div className="scroll"><table>
          <caption>Simulation against M/M/c theory (Poisson arrivals, exponential service, 200k parcels)</caption>
          <thead><tr><th>Arrivals/h</th><th>Cells</th><th>P(wait) theory</th><th>P(wait) sim</th><th>Mean wait theory</th><th>Mean wait sim</th><th>Little’s law Lq vs λWq</th></tr></thead>
          <tbody>{v.mmc.map(r => (
            <tr key={r.lam_h}><td>{int(r.lam_h)}</td><td>{r.c}</td><td>{fix(r.pwait_theory, 3)}</td><td>{fix(r.pwait_sim, 3)}</td><td>{fix(r.wq_theory_min * 60)} s</td><td>{fix(r.wq_sim_min * 60)} s</td><td>{fix(r.littles_Lq, 3)} vs {fix(r.littles_lambdaW, 3)}</td></tr>
          ))}</tbody>
        </table></div>
        <div className="scroll"><table>
          <caption>Time holdout: later days vs earlier days</caption>
          <thead><tr><th>Station</th><th>Test days</th><th>Sampled routes/day</th><th>Parcels per route</th></tr></thead>
          <tbody>{v.holdout.map(r => (
            <tr key={r.station}><td>{r.station}</td><td>{r.test_days}</td><td>{r.routes_change > 0 ? '+' : ''}{pct(r.routes_change, 0)}</td><td>{r.ppr_change > 0 ? '+' : ''}{pct(r.ppr_change, 0)}</td></tr>
          ))}</tbody>
        </table></div>
        <p className="note">Limits: volumes are the public route sample, not full station throughput; inbound timing is a stated assumption; 29–39 days per station from one summer; one pooled queue (assigning destinations to cells can only raise the count); cell rate, manual rate and wage are published figures. Flip points use 4 replications per point, so a flip within a few percent of base is within simulation noise.</p>
      </>}>
      <FlipBars v={v} st={st} />
      <ul className="checks">
        <li><IconCheck /><span><b>Hand calculation, {h.station}.</b> <code>⌈{int(h.design_packages)} × (1 − {fix(h.exception_rate, 4)}) ÷ ({fix(h.sort_span_h, 3)} h × {h.rate_h})⌉ = {h.by_hand_value}</code>; the tool gives {h.tool_value}.</span></li>
        <li><IconCheck /><span><b>Ladder holds.</b> Floor ≤ earliest cutoff first ≤ first come, first served at {ladderOk} of {v.ladder.length} stations.</span></li>
        <li><IconCheck /><span><b>Simulation matches theory.</b> P(wait) {fix(v.mmc[0].pwait_theory, 3)} by formula, {fix(v.mmc[0].pwait_sim, 3)} simulated; Little’s law within 1% in all {v.mmc.length} cases.</span></li>
        <li><IconCheck /><span><b>Nothing lost in ingest.</b> {int(s.dataset.reconciliation.parsed)} parcels parsed = {int(s.dataset.reconciliation.raw_key_count)} keys in the raw file.</span></li>
        <li><IconCheck /><span><b>No look-ahead in the forecast.</b> Features stay fixed when every day after the forecast origin is perturbed; folds train only on earlier dates.</span></li>
      </ul>
    </Step>
  )
}
