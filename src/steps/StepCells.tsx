import { useState } from 'react'
import type { Station, Summary } from '../data'
import { int, pct, fix } from '../data'
import { useWidth } from '../hooks'
import { IconAlert, IconCheck } from '../viz'
import { Step } from '../Step'

function CellFloor({ cells, late, gaylords }: { cells: number; late: number; gaylords: number }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const cw = w < 520 ? 58 : 76
  const gap = w < 520 ? 14 : 22
  const laneW = w < 520 ? 92 : 132
  const avail = w - laneW - 24
  const cols = Math.max(1, Math.floor((avail + gap) / (cw + gap)))
  const rows = Math.ceil(cells / cols)
  const g = Math.round(cw * 0.24) // gaylord size
  const rowH = cw + g + 30
  const beltY = 8
  const top = beltY + 34
  const boxes = Math.round(late * 100)
  const bs = w < 520 ? 7 : 9
  const perRow = Math.floor((laneW - 16) / (bs + 2))
  const H = Math.max(top + rows * rowH, beltY + 48 + Math.ceil(boxes / perRow) * (bs + 2))
  const laneX = w - laneW

  return (
    <div ref={ref} className="chart">
      <svg width={w} height={H} role="img" aria-label={`${cells} sort cells; each orange box in the overflow lane is about 1% of the day's parcels late`}>
        <rect className="plan-belt" x={0} y={beltY} width={laneX - 12} height={22} rx={2} />
        {Array.from({ length: Math.floor((laneX - 12) / 12) }, (_, i) => <line key={i} className="roller" x1={i * 12 + 6} x2={i * 12 + 6} y1={beltY + 3} y2={beltY + 19} />)}
        {Array.from({ length: cells }, (_, i) => {
          const c = i % cols, r = Math.floor(i / cols)
          const x0 = c * (cw + gap) + 4
          const y0 = top + r * rowH
          const per = Math.min(gaylords, 8)
          return (
            <g key={i} className="cell-unit" style={{ transitionDelay: `${Math.min(i, 6) * 18}ms` }}>
              <rect className="plan-induct" x={x0 + cw * 0.3} y={y0 - 10} width={cw * 0.4} height={8} />
              <rect className="plan-cell" x={x0} y={y0} width={cw} height={cw} />
              <circle className="plan-robot" cx={x0 + cw / 2} cy={y0 + cw / 2} r={cw * 0.2} />
              <path className="plan-arm" d={`M${x0 + cw / 2} ${y0 + cw / 2}l${cw * 0.26} ${cw * 0.18}`} />
              {Array.from({ length: per / 2 }, (_, k) => <rect key={k} className="plan-gaylord" x={x0 + k * (cw / (per / 2)) + 1} y={y0 + cw + 4} width={cw / (per / 2) - 3} height={g} />)}
              {Array.from({ length: per / 2 }, (_, k) => <rect key={`b${k}`} className="plan-gaylord" x={x0 + k * (cw / (per / 2)) + 1} y={y0 + cw + g + 7} width={cw / (per / 2) - 3} height={g * 0.6} />)}
              <text className="cell-no" x={x0 + 6} y={y0 + 15}>{i + 1}</text>
            </g>
          )
        })}
        <rect className="plan-overflow" x={laneX} y={beltY} width={laneW} height={H - beltY - 2} />
        <text className="lane-label" x={laneX + 8} y={beltY + 18}>Late</text>
        {Array.from({ length: boxes }, (_, i) => (
          <rect key={i} className="late-box" x={laneX + 8 + (i % perRow) * (bs + 2)} y={beltY + 28 + Math.floor(i / perRow) * (bs + 2)} width={bs} height={bs} rx={1} />
        ))}
        {boxes === 0 && <text className="lane-empty" x={laneX + 8} y={beltY + 40}>{late > 0 ? 'under 1%' : 'none'}</text>}
      </svg>
    </div>
  )
}

export function StepCells({ st, s }: { st: Station; s: Summary }) {
  const curve = st.sizing.des_curve
  const lo = curve[0].cells
  const hi = Math.min(curve[curve.length - 1].cells, st.sizing.cells_des + 5)
  const [c, setC] = useState(st.sizing.cells_hand_p90)
  const p = curve.find(q => q.cells === c) ?? curve[curve.length - 1]
  const ok = p.miss_share < s.assumptions.MISS_TARGET
  const pos = (v: number) => `${((v - lo) / (hi - lo)) * 100}%`
  const hand = st.sizing.cells_hand_p90
  const sim = st.sizing.cells_des
  return (
    <Step n={4} id="cells" title="How many cells"
      lede={hand === sim
        ? <>The spreadsheet rule divides the day by the sort window and says {hand} cells. Here a simulation of the wave, parcel by parcel at {int(s.assumptions.CELL_RATE_H)} sorts an hour per cell, agrees: <b>{sim} cells</b> keep late parcels under 1%. Slide the bank and watch the overflow lane.</>
        : <>Dividing the day by the sort window gives {hand} cells. Simulating the wave parcel by parcel, at {int(s.assumptions.CELL_RATE_H)} sorts an hour per cell, gives <b>{sim}</b>: the fewest that keep late parcels under 1%. Slide the bank and watch the overflow lane.</>}
      details={<>
        <p>A pooled bank of identical cells serves parcels first come, first served from a shared infeed; service is gamma with a mean of 7.2 s and CV {s.assumptions.SERVICE_CV}. A parcel is late if it finishes after its route’s cutoff. Each count is the mean of 20 replications. Erlang C at a 30-minute threshold reduces to the spreadsheet rule here, so it is kept only as a stability check.</p>
        <div className="scroll"><table>
          <caption>{st.station}, design day: late share by cell count (FIFO simulation)</caption>
          <thead><tr><th>Cells</th><th>Late parcels</th><th>±95% CI</th><th>Routes with a late parcel</th><th>95th-pct wait</th></tr></thead>
          <tbody>{curve.filter(q => q.cells <= hi).map(q => (
            <tr key={q.cells} className={q.cells === c ? 'row-on' : undefined}><td>{q.cells}</td><td>{pct(q.miss_share, 2)}</td><td>{pct(q.miss_ci95, 2)}</td><td>{pct(q.routes_late_share, 0)}</td><td>{fix(q.p95_wait_min, 1)} min</td></tr>
          ))}</tbody>
        </table></div>
      </>}>
      <div className="cells-ctl">
        <label className="range-big">
          <span className="range-label">Cells in the bank: <b>{c}</b></span>
          <input type="range" min={lo} max={hi} step={1} value={c} onChange={e => setC(+e.target.value)} aria-valuetext={`${c} cells, ${pct(p.miss_share)} late`} />
          <span className="range-marks" aria-hidden="true">
            {hand === sim
              ? <span style={{ left: pos(sim) }} className="mark mark-key">rule and simulation {sim}</span>
              : <>
                <span style={{ left: pos(hand) }} className={`mark ${sim - hand === 1 ? 'mark-l' : ''}`}>rule {hand}</span>
                <span style={{ left: pos(sim) }} className={`mark mark-key ${sim - hand === 1 ? 'mark-r' : ''}`}>simulation {sim}</span>
              </>}
          </span>
        </label>
        <dl className="gauges">
          <div><dt>Parcels late</dt><dd>{pct(p.miss_share)}</dd><dd className="sub">about {int(p.miss_share * st.design_day.robot_packages)} parcels</dd></div>
          <div><dt>Routes with a late parcel</dt><dd>{pct(p.routes_late_share, 0)}</dd></div>
          <div><dt>95th-percentile wait</dt><dd>{fix(p.p95_wait_min, 0)} min</dd></div>
          <div className={ok ? 'verdict ok' : 'verdict bad'}>{ok ? <IconCheck size={18} /> : <IconAlert size={18} />}<span>{ok ? 'Meets the <1% late target' : 'Misses the <1% late target'}</span></div>
        </dl>
      </div>
      <CellFloor cells={c} late={p.miss_share} gaylords={s.assumptions.GAYLORDS_PER_CELL} />
      <p className="legend"><span className="lg"><i className="sw sw-cell" />robotic cell with {s.assumptions.GAYLORDS_PER_CELL} gaylords</span><span className="lg"><i className="sw sw-late" />about 1% of the day’s parcels missing cutoff</span></p>
    </Step>
  )
}
