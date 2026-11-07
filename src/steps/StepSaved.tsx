import type { Station, Summary } from '../data'
import { int, pct, usd } from '../data'
import { useWidth } from '../hooks'
import { Step } from '../Step'

const SERIES = [
  { key: 'floor', label: 'Scheduling floor (any policy)' },
  { key: 'edf', label: 'Earliest cutoff first' },
  { key: 'fifo', label: 'First come, first served' },
  { key: 'boot', label: 'FIFO, 90% of bootstrap days' },
] as const

function Ladder({ s, station, onPick }: { s: Summary; station: string; onPick: (st: string) => void }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const ml = 58, mr = 18, mt = 26
  const rowH = 46
  const maxC = Math.max(...s.stations.map(x => x.cells_90pct_confidence)) + 1
  const pw = w - ml - mr
  const x = (c: number) => ml + (c / maxC) * pw
  const H = mt + s.stations.length * rowH + 8
  const vals = (st: Summary['stations'][number]) => ({ floor: st.cells_bound_1pct, edf: st.cells_edf20, fifo: st.cells_fifo20, boot: st.cells_90pct_confidence })
  return (
    <div ref={ref} className="chart">
      <svg width={w} height={H} role="img" aria-label="Cells needed per station: scheduling floor, earliest-cutoff-first, first-come-first-served and the 90%-of-bootstrap-days count">
        {Array.from({ length: maxC + 1 }, (_, c) => (
          <g key={c}><line className="grid" x1={x(c)} x2={x(c)} y1={mt - 4} y2={H - 8} /><text className="tick" x={x(c)} y={mt - 10} textAnchor="middle">{c}</text></g>
        ))}
        {s.stations.map((st, i) => {
          const y0 = mt + i * rowH
          const v = vals(st)
          const on = st.station === station
          return (
            <g key={st.station} className={on ? 'lrow on' : 'lrow'} onClick={() => onPick(st.station)}>
              <rect className="lrow-band" x={0} y={y0 + 2} width={w} height={rowH - 4} />
              <text className="lrow-name" x={8} y={y0 + rowH / 2 + 4}>{st.station}</text>
              {SERIES.map((se, k) => {
                const cy = y0 + 9 + k * 9.5
                const cx = x(v[se.key])
                return <g key={se.key}>
                  <line className="lrow-stem" x1={x(0)} x2={cx} y1={cy} y2={cy} />
                  <circle className={`mk mk-${se.key}`} cx={cx} cy={cy} r={4.5} />
                </g>
              })}
            </g>
          )
        })}
      </svg>
      <p className="legend">{SERIES.map(se => <span key={se.key} className="lg"><i className={`mkk mk-${se.key}`} />{se.label}</span>)}</p>
    </div>
  )
}

export function StepSaved({ s, st, onPick }: { s: Summary; st: Station; onPick: (x: string) => void }) {
  const sum = (k: 'cells_bound_1pct' | 'cells_edf20' | 'cells_fifo20' | 'cells_90pct_confidence') => s.stations.reduce((a, x) => a + x[k], 0)
  const saves = s.stations.filter(x => x.cells_fifo20 > x.cells_edf20).length
  const ss = s.stations.find(x => x.station === st.station)!
  const one = ss.one_cell_short
  const cases = st.business.cases.filter(c => c.manual_rate_h === 275)
  const be = (ops: number) => cases.find(c => c.ops_per_cell === ops)!.breakeven_capex_per_cell_usd['24']
  const destBinds = ss.cells_for_destinations > ss.cells_edf20
  const pOk = st.sizing.bootstrap_days.p_ok
  return (
    <Step n={6} id="saved" title="Cells saved, and the risk of one short"
      lede={<>Sequencing induction by earliest cutoff reaches the scheduling floor at all six stations: <b>{sum('cells_edf20')} cells against {sum('cells_fifo20')}</b> first come, first served, one saved at {saves} of 6. One cell short at {st.station} leaves {pct(one.late_share)} of parcels late on the design day.</>}
      details={<>
        <p>The floor is a processor-demand bound: parcels that arrive after t₁ and are due by t₂ must be sorted inside that window, whatever the policy. It is computed on the expected inbound under the same arrival assumption, for the same &lt;1% late target. Earliest-cutoff-first induction means a freed cell takes the waiting parcel whose route leaves soonest.</p>
        <div className="scroll"><table>
          <caption>Labour-only business case at {st.station} (manual sorters at 275/h, $18.10/h, 300 sort days)</caption>
          <thead><tr><th>Operators per cell</th><th>Manual heads</th><th>Robot-side heads</th><th>Labour saved per year</th><th>Break-even capex per cell, 18 / 24 / 36 months</th></tr></thead>
          <tbody>{cases.map(c => (
            <tr key={c.ops_per_cell}><td>{c.ops_per_cell}</td><td>{c.manual_heads}</td><td>{c.robot_side_heads}</td><td>{c.annual_labour_delta_usd < 0 ? '−' : ''}${int(Math.abs(c.annual_labour_delta_usd))}</td><td>{c.annual_labour_delta_usd < 0 ? 'never pays back' : ['18', '24', '36'].map(k => usd(c.breakeven_capex_per_cell_usd[k])).join(' / ')}</td></tr>
          ))}</tbody>
        </table></div>
        <p className="note">Labour savings only: maintenance, software and other running costs would lower these figures. No cell price is assumed. Bootstrap: 200 design days rebuilt from resampled days; P(cells enough) for {st.station}: {Object.entries(pOk).map(([k, v]) => `${k} cells ${pct(v, 0)}`).join(', ')}.</p>
      </>}>
      <Ladder s={s} station={st.station} onPick={onPick} />
      <p className="totals">Six-station totals: floor {sum('cells_bound_1pct')} · earliest cutoff first {sum('cells_edf20')} · first come, first served {sum('cells_fifo20')} · 90% of bootstrap days {sum('cells_90pct_confidence')}. Tap a row to switch station.</p>
      <div className="station-notes">
        <p><b>{st.station}, one cell short.</b> {one.cells} cells instead of {ss.cells_des}: {int(one.late_parcels)} parcels ({pct(one.late_share)}) miss cutoff and {pct(one.routes_late_share, 0)} of routes leave with a late parcel. {ss.cells_des} cells clear {pct(pOk[String(ss.cells_des)] ?? 0, 0)} of 200 bootstrap design days; {ss.cells_90pct_confidence} clear 90%.{destBinds ? ` Here ${st.design_day.routes} route destinations at ${s.assumptions.GAYLORDS_PER_CELL} per cell need ${ss.cells_for_destinations} cells, so the saving needs more destinations per cell.` : ''}</p>
        <p><b>Payback on labour alone.</b> A cell here pays back in 24 months if it costs under {usd(be(1))} at one operator per cell, or {usd(be(0.5))} with one operator tending two. At two operators per cell, labour never pays it back.</p>
      </div>
    </Step>
  )
}
