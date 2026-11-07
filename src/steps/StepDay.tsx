import { useState } from 'react'
import type { Station, Validation } from '../data'
import { int, fix, pct } from '../data'
import { useWidth } from '../hooks'
import { colPath, niceTicks, tickLabel, Tip } from '../viz'
import { Step } from '../Step'

const shortDate = (d: string) => new Date(`${d}T12:00:00Z`).toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' })

function DayChart({ st }: { st: Station }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const ml = 46, mr = 14, mt = 18
  const hTop = w < 520 ? 150 : 190
  const gap = 34
  const hBot = w < 520 ? 60 : 72
  const pw = w - ml - mr
  const n = st.daily.length
  const band = pw / n
  const bw = Math.min(18, band * 0.68)
  const vT = niceTicks(Math.max(...st.daily.map(d => d.packages)) * 1.04, 3)
  const rT = niceTicks(Math.max(...st.daily_routes) * 1.04, 2)
  const yTop = (v: number) => mt + hTop - (v / vT.top) * hTop
  const y0Bot = mt + hTop + gap + hBot
  const yBot = (v: number) => y0Bot - (v / rT.top) * hBot
  const H = y0Bot + 26
  const isDesign = (i: number) => st.daily[i].date === st.design_day.date
  const x = (i: number) => ml + i * band + (band - bw) / 2
  const vol = st.volume
  const labelLeft = ml + pw - 4

  return (
    <div ref={ref} className="chart" onMouseLeave={() => setHover(null)}>
      <svg width={w} height={H} role="img" aria-label={`Daily parcels and sampled routes at ${st.station} over ${n} days`}>
        {/* grid */}
        {vT.ticks.map(t => <g key={t}><line className="grid" x1={ml} x2={ml + pw} y1={yTop(t)} y2={yTop(t)} /><text className="tick" x={ml - 8} y={yTop(t) + 4} textAnchor="end">{tickLabel(t)}</text></g>)}
        {rT.ticks.map(t => <g key={`r${t}`}><line className="grid" x1={ml} x2={ml + pw} y1={yBot(t)} y2={yBot(t)} /><text className="tick" x={ml - 8} y={yBot(t) + 4} textAnchor="end">{t}</text></g>)}
        <text className="axis-title" x={ml} y={mt - 6}>Parcels per day</text>
        <text className="axis-title" x={ml} y={mt + hTop + gap - 8}>Routes in the sample that day</text>
        {/* bars */}
        {st.daily.map((d, i) => (
          <g key={d.date} className={hover === i ? 'is-hover' : undefined}>
            <path className={isDesign(i) ? 'col col-key' : 'col'} d={colPath(x(i), yTop(d.packages), bw, mt + hTop - yTop(d.packages), 3)} />
            <path className={isDesign(i) ? 'col col-key' : 'col col-soft'} d={colPath(x(i), yBot(st.daily_routes[i]), bw, y0Bot - yBot(st.daily_routes[i]), 3)} />
            <rect className="hit" x={ml + i * band} y={mt} width={band} height={y0Bot - mt} onMouseEnter={() => setHover(i)} onClick={() => setHover(i)} />
          </g>
        ))}
        {/* mean and P90 */}
        <line className="ref-line" x1={ml} x2={ml + pw} y1={yTop(vol.mean)} y2={yTop(vol.mean)} />
        <line className="ref-line ref-strong" x1={ml} x2={ml + pw} y1={yTop(vol.p90)} y2={yTop(vol.p90)} />
        <text className="ref-label" x={labelLeft} y={yTop(vol.p90) - 6} textAnchor="end">P90 {int(vol.p90)}</text>
        <text className="ref-label ref-label-soft" x={labelLeft} y={yTop(vol.mean) + 15} textAnchor="end">mean {int(vol.mean)}</text>
        {/* x labels */}
        <text className="tick" x={ml} y={H - 6}>{shortDate(st.daily[0].date)}</text>
        <text className="tick" x={ml + pw} y={H - 6} textAnchor="end">{shortDate(st.daily[n - 1].date)}</text>
      </svg>
      {hover !== null && (
        <Tip x={x(hover)} y={mt + 4} w={w}>
          <b>{shortDate(st.daily[hover].date)}{isDesign(hover) ? ' · design day' : ''}</b>
          <span>{int(st.daily[hover].packages)} parcels</span>
          <span>{st.daily_routes[hover]} routes</span>
        </Tip>
      )}
      <p className="legend"><span className="lg"><i className="sw sw-key" />Design day, {shortDate(st.design_day.date)}: {st.design_day.routes} routes, {int(st.design_day.observed_packages)} parcels</span></p>
    </div>
  )
}

export function StepDay({ st, v }: { st: Station; v: Validation }) {
  const dd = st.design_day
  return (
    <Step n={1} id="day" title="A station’s day"
      lede={<>At {st.station} the busiest tenth of days carry {int(st.volume.p90)} parcels against a mean of {int(st.volume.mean)}. But volume moves with how many routes the public sample holds (r = {fix(st.coverage.corr_packages_routes, 3)}), so the design day is a real {dd.routes}-route day plus 10% for peak: <b>{int(dd.design_packages)} parcels</b>.</>}
      details={<>
        <p>Daily totals in this sample measure route coverage, not demand. Parcels per route are steady (CV {pct(st.coverage.packages_per_route_cv)} here), so the design day is the P90 route count × parcels per route, using an observed day’s real departure times and per-route counts. 90% intervals come from a 2,000-resample day-block bootstrap.</p>
        <div className="scroll"><table>
          <caption>Coverage check, six sized stations</caption>
          <thead><tr><th>Station</th><th>corr(parcels, routes)</th><th>Parcels/route CV</th><th>Routes/day</th><th>P90 ÷ mean, all days</th><th>P90 ÷ mean, parcels/route</th></tr></thead>
          <tbody>{v.coverage.map(c => (
            <tr key={c.station} className={c.station === st.station ? 'row-on' : undefined}><td>{c.station}</td><td>{fix(c.corr_packages_routes, 3)}</td><td>{pct(c.packages_per_route_cv)}</td><td>{c.routes_min}–{c.routes_max}</td><td>{fix(c.p90_over_mean_packages)}</td><td>{fix(c.p90_over_mean_packages_per_route)}</td></tr>
          ))}</tbody>
        </table></div>
        <p className="note">{st.station}: design routes {fix(st.design_basis.design_routes, 1)} (90% CI {fix(st.design_basis.design_routes_ci90[0], 1)}–{fix(st.design_basis.design_routes_ci90[1], 1)}), parcels per route {fix(st.design_basis.packages_per_route, 1)} ({fix(st.design_basis.packages_per_route_ci90[0], 1)}–{fix(st.design_basis.packages_per_route_ci90[1], 1)}). Volumes are parcels on the routes in the public sample, not total station throughput.</p>
      </>}>
      <DayChart st={st} />
    </Step>
  )
}
