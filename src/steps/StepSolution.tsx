import type { Forecast, Station, Summary, Validation } from '../data'
import { int, pct, usd } from '../data'
import { Step } from '../Step'

const BUCKETS = ['1 route', '2–3', '4–6', '7+']

export function StepSolution({ f, v, st, s }: { f: Forecast; v: Validation; st: Station; s: Summary }) {
  const folds = f.levels.wave_h1.folds
  const k = folds[folds.length - 1].calibration_k_by_wave_size
  const rate = v.week1_ranking.find(r => r.param === 'rate_h')
  const row = s.stations.find(x => x.station === st.station)
  const lad = st.sizing.ladder
  const short = st.business.one_cell_short
  const flip = st.sensitivity.tornado.find(t => t.param === 'rate_h')
  const be = st.business.cases.find(c => c.manual_rate_h === 275 && c.ops_per_cell === 1)
  return (
    <Step n={8} id="solution" title="The solution"
      lede={<>A five-step sizing recipe you can run on any station’s route plan.</>}>
      <ol className="recipe">
        <li><span className="recipe-n" aria-hidden="true">1</span><p><b>Check the data first.</b> If volume tracks routes, size on routes × parcels per route.</p></li>
        <li>
          <span className="recipe-n" aria-hidden="true">2</span>
          <div>
            <p><b>Forecast each wave’s P90 with a margin by wave size.</b> Refit on your own history.</p>
            <div className="board recipe-board" role="table" aria-label="P90 margin by wave size">
              {BUCKETS.map((b, i) => (
                <div key={b} className="board-cell" role="row">
                  <span className="board-k" role="rowheader">{b}</span>
                  <span className="board-v" role="cell">{`×${(k[String(i)] ?? 1).toFixed(2)}`.split('').map((c, j) => <span key={j} className="flap">{c}</span>)}</span>
                </div>
              ))}
            </div>
          </div>
        </li>
        <li><span className="recipe-n" aria-hidden="true">3</span><p><b>Size against the waves, not the day:</b> floor, then earliest cutoff first, then first come first served, then 90% of peak days.</p></li>
        <li><span className="recipe-n" aria-hidden="true">4</span><p><b>Measure first on site:</b> sustained cell rate (the count rises about {rate ? pct(rate.median_rel_margin, 0) : '11%'} below nameplate), then peak uplift, then the inbound curve.</p></li>
        <li><span className="recipe-n" aria-hidden="true">5</span><p><b>Price it backwards:</b> the most a cell can cost to pay back in 18, 24 or 36 months.</p></li>
      </ol>

      <div className="term">
        <p className="term-cap"><code>size-site routes.csv</code> → cell count, risk of one short, what to measure first, break-even price per cell. On {st.station}:</p>
        <div className="dboard term-board">
          <div className="term-row term-cmd"><span>$</span><code>size-site --station {st.station}</code></div>
          <div className="term-row"><span>Cells</span><span>{lad.edf} earliest cutoff first · {lad.fifo} first come · {row?.cells_90pct_confidence ?? st.sizing.bootstrap_days.cells_90pct_confidence} on 90% of peak days</span></div>
          {short && <div className="term-row"><span>One short</span><span className="term-late">{pct(short.late_share)} of parcels late · {pct(short.routes_late_share, 0)} of routes</span></div>}
          {flip && flip.flip_up_at !== null && <div className="term-row"><span>Measure first</span><span>Cell rate: count rises below {int(flip.flip_up_at)}/h</span></div>}
          {be && <div className="term-row"><span>Break-even</span><span>{be.breakeven_capex_per_cell_usd['24'] > 0 ? `${usd(be.breakeven_capex_per_cell_usd['24'])} per cell, 24-month payback, 1 operator per cell` : 'labour alone never pays back at 1 operator per cell'}</span></div>}
        </div>
      </div>
      <p className="recipe-foot">Built on public delivery-station data. On a real site, week 1 is one station’s route history run through this recipe.</p>
    </Step>
  )
}
