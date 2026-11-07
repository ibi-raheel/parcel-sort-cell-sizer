import { useState } from 'react'
import type { Station, Summary } from '../data'
import { int, fix } from '../data'
import { useWidth } from '../hooks'
import { colPath, niceTicks, tickLabel, Tip } from '../viz'
import { Step } from '../Step'

export function Board({ items, label }: { items: { k: string; v: string }[]; label: string }) {
  return (
    <div className="board" role="group" aria-label={label}>
      {items.map(it => (
        <div key={it.k} className="board-cell">
          <span className="board-k">{it.k}</span>
          <span className="board-v">{it.v.split('').map((c, i) => <span key={i} className={c === ' ' ? 'flap flap-gap' : 'flap'}>{c}</span>)}</span>
        </div>
      ))}
    </div>
  )
}

function WaveChart({ st }: { st: Station }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const dd = st.design_day
  // 15-minute bins of parcels; shown as an hourly rate (×4) so they read against the board
  const rates = dd.wave_profile_15min.map(v => v * 4)
  const avg = dd.lambda_per_h
  const ml = 46, mr = 14, mt = 22, mb = 28
  const ph = w < 520 ? 190 : 240
  const pw = w - ml - mr
  const n = rates.length
  const band = pw / n
  const bw = Math.min(22, band * 0.72)
  const T = niceTicks(Math.max(...rates) * 1.08, 4)
  const y = (v: number) => mt + ph - (v / T.top) * ph
  const x = (i: number) => ml + i * band + (band - bw) / 2
  const peakI = rates.indexOf(Math.max(...rates))
  const H = mt + ph + mb
  const hours = Math.floor((n * 15) / 60)

  return (
    <div ref={ref} className="chart" onMouseLeave={() => setHover(null)}>
      <svg width={w} height={H} role="img" aria-label={`Modelled inbound rate in 15-minute bins on the ${st.station} design day, peak ${fix(st.design_day.peak_15min_rate_per_h / avg)} times the average`}>
        {T.ticks.map(t => <g key={t}><line className="grid" x1={ml} x2={ml + pw} y1={y(t)} y2={y(t)} /><text className="tick" x={ml - 8} y={y(t) + 4} textAnchor="end">{tickLabel(t)}</text></g>)}
        <text className="axis-title" x={ml} y={mt - 8}>Inbound parcels per hour, 15-minute bins</text>
        {rates.map((r, i) => {
          const base = Math.min(r, avg)
          const yb = y(base)
          const over = r > avg
          return (
            <g key={i}>
              <path className="col" d={colPath(x(i), yb, bw, y(0) - yb, over ? 0 : 3)} />
              {over && <path className="col col-over" d={colPath(x(i), y(r), bw, yb - y(r) - 2, 3)} />}
              <rect className="hit" x={ml + i * band} y={mt} width={band} height={ph} onMouseEnter={() => setHover(i)} onClick={() => setHover(i)} />
            </g>
          )
        })}
        <line className="ref-line ref-strong" x1={ml} x2={ml + pw} y1={y(avg)} y2={y(avg)} />
        <text className="ref-label" x={ml + pw - 4} y={y(avg) - 6} textAnchor="end">shift average {int(avg)}/h</text>
        <text className="ref-label" x={x(peakI) + bw / 2} y={y(rates[peakI]) - 8} textAnchor={peakI > n * 0.6 ? 'end' : 'middle'}>peak {fix(st.design_day.peak_15min_rate_per_h / avg)}×</text>
        {Array.from({ length: hours + 1 }, (_, h) => (
          <text key={h} className="tick" x={ml + h * 4 * band} y={H - 8} textAnchor={h === 0 ? 'start' : 'middle'}>{h} h</text>
        ))}
      </svg>
      {hover !== null && (
        <Tip x={x(hover)} y={mt + 4} w={w}>
          <b>{Math.floor(hover / 4)} h {String((hover % 4) * 15).padStart(2, '0')} min</b>
          <span>{int(rates[hover])} parcels/h</span>
          <span>{fix(rates[hover] / avg)}× the average</span>
        </Tip>
      )}
      <p className="legend"><span className="lg"><i className="sw sw-col" />up to the shift average</span><span className="lg"><i className="sw sw-over" />above it: the part that queues</span></p>
    </div>
  )
}

export function StepWave({ st, s }: { st: Station; s: Summary }) {
  const dd = st.design_day
  const ratio = s.stations.find(x => x.station === st.station)!.peak_rate_over_mean_rate
  const ratios = s.stations.map(x => x.peak_rate_over_mean_rate)
  const date = dd.date.slice(5).replace('-', '/')
  return (
    <Step n={3} id="wave" title="Waves pile up"
      lede={<>Routes leave in clusters, so parcels arrive in a wave. On {st.station}’s design day the busiest 15 minutes run at <b>{fix(ratio)}× the shift average</b>; across the six stations, {fix(Math.min(...ratios))}–{fix(Math.max(...ratios))}×.</>}
      details={<>
        <p>The dataset has real route departure times but no inbound scan times. Each route’s parcels are modelled as arriving evenly from {s.assumptions.INBOUND_OPEN_H} h to {s.assumptions.INBOUND_CLOSE_H} h before its real departure, and they must be sorted {s.assumptions.CUTOFF_H * 60} minutes before it. The clustering is real; the shape of each route’s window is assumed, and step 7 shows how far it can move before the cell count changes.</p>
        <div className="scroll"><table>
          <caption>Peak 15-minute inbound ÷ shift average, design day</caption>
          <thead><tr>{s.stations.map(x => <th key={x.station}>{x.station}</th>)}</tr></thead>
          <tbody><tr>{s.stations.map(x => <td key={x.station} className={x.station === st.station ? 'cell-on' : undefined}>{fix(x.peak_rate_over_mean_rate)}</td>)}</tr></tbody>
        </table></div>
        <p className="note">Sort span = departure spread ({fix(dd.departure_spread_h)} h) + 2 h = {fix(dd.sort_span_h)} h. Design parcels {int(dd.design_packages)} = observed {int(dd.observed_packages)} × 1.10 peak uplift; {int(dd.robot_packages)} of them fit the robot.</p>
      </>}>
      <Board label={`Design day at ${st.station}`} items={[
        { k: 'Design day', v: date },
        { k: 'Routes', v: String(dd.routes) },
        { k: 'Sort span', v: `${fix(dd.sort_span_h, 1)} h` },
        { k: 'Avg / h', v: int(dd.lambda_per_h) },
        { k: 'Peak / h', v: int(dd.peak_15min_rate_per_h) },
      ]} />
      <WaveChart st={st} />
    </Step>
  )
}
