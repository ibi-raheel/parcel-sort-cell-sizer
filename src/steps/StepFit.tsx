import { useMemo, useRef, useState } from 'react'
import type { PointerEvent as RPointerEvent } from 'react'
import type { Station, Summary } from '../data'
import { int, pct } from '../data'
import { useWidth } from '../hooks'
import { IconReset } from '../viz'
import { Step } from '../Step'

const LX = 110 // cm shown on the longest-side axis
const MY = 75  // cm shown on the middle-side axis
const clamp = (v: number, a: number, b: number) => Math.min(b, Math.max(a, v))

type Env = { l: number; m: number; s: number }

function Envelope({ st, def }: { st: Station; def: Env }) {
  const [ref, w] = useWidth<HTMLDivElement>()
  const [env, setEnv] = useState<Env>(def)
  const svgRef = useRef<SVGSVGElement>(null)
  const dragging = useRef(false)
  const ml = 40, mr = 14, mt = 12, mb = 34
  const pw = w - ml - mr
  const ph = Math.round(Math.min(380, Math.max(220, pw * 0.58)))
  const H = ph + mt + mb
  const x = (l: number) => ml + (Math.min(l, LX) / LX) * pw
  const y = (m: number) => mt + ph - (Math.min(m, MY) / MY) * ph
  const sample = st.envelope.sample_cm
  const dot = w < 520 ? 1.7 : 2

  const { inPath, outPath, nIn } = useMemo(() => {
    let a = '', b = '', k = 0
    for (const [L, M, S] of sample) {
      const seg = `M${x(L).toFixed(1)} ${y(M).toFixed(1)}h${dot}v${dot}h-${dot}z`
      if (L <= env.l && M <= env.m && S <= env.s) { a += seg; k++ } else b += seg
    }
    return { inPath: a, outPath: b, nIn: k }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sample, env, w])

  const share = nIn / sample.length
  const isDefault = env.l === def.l && env.m === def.m && env.s === def.s

  const toCm = (e: RPointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect()
    const l = Math.round(((e.clientX - r.left - ml) / pw) * LX)
    const m = Math.round(((mt + ph - (e.clientY - r.top)) / ph) * MY)
    return { l: clamp(l, 30, 100), m: clamp(m, 20, 70) }
  }
  const onDown = (e: RPointerEvent<SVGElement>) => { dragging.current = true; (e.target as Element).setPointerCapture(e.pointerId); setEnv(v => ({ ...v, ...toCm(e) })) }
  const onMove = (e: RPointerEvent<SVGElement>) => { if (dragging.current) setEnv(v => ({ ...v, ...toCm(e) })) }
  const onUp = () => { dragging.current = false }

  const ticksL = [0, 20, 40, 60, 80, 100]
  const ticksM = [0, 25, 50, 75]

  return (
    <div ref={ref} className="chart">
      <div className="readout">
        <div className="readout-main"><span className="readout-num">{pct(share)}</span><span className="readout-cap">of {int(sample.length)} sampled {st.station} parcels fit {env.l} × {env.m} × {env.s} cm{isDefault ? ` (every parcel: ${pct(st.envelope.sortable_share)})` : ''}</span></div>
        <button type="button" className="btn-quiet" onClick={() => setEnv(def)} disabled={isDefault}><IconReset /> Reset to 60 × 45 × 35</button>
      </div>
      <svg ref={svgRef} width={w} height={H} className="env-svg" role="img" aria-label={`Parcels by longest and middle side, with the pick envelope at ${env.l} by ${env.m} cm`}>
        {ticksL.map(t => <g key={t}><line className="grid" x1={x(t)} x2={x(t)} y1={mt} y2={mt + ph} /><text className="tick" x={x(t)} y={mt + ph + 16} textAnchor="middle">{t}</text></g>)}
        {ticksM.map(t => <g key={t}><line className="grid" x1={ml} x2={ml + pw} y1={y(t)} y2={y(t)} /><text className="tick" x={ml - 8} y={y(t) + 4} textAnchor="end">{t}</text></g>)}
        <text className="axis-title" x={ml + pw} y={H - 2} textAnchor="end">Longest side, cm</text>
        <text className="axis-title" x={ml + 6} y={mt + 14}>Middle side, cm</text>
        <line className="diag" x1={x(0)} y1={y(0)} x2={x(MY)} y2={y(MY)} />
        <rect className="env-zone" x={x(0)} y={y(env.m)} width={x(env.l) - x(0)} height={y(0) - y(env.m)} />
        <rect className="env-hit" x={ml} y={mt} width={pw} height={ph} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} />
        <path className="pts-in" d={inPath} />
        <path className="pts-out" d={outPath} />
        <rect className="env-edge" x={x(0)} y={y(env.m)} width={x(env.l) - x(0)} height={y(0) - y(env.m)} />
        <g className="env-handle" transform={`translate(${x(env.l)} ${y(env.m)})`} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp}>
          <circle r={22} className="env-handle-hit" />
          <rect x={-8} y={-8} width={16} height={16} />
        </g>
      </svg>
      <p className="legend"><span className="lg"><i className="sw sw-in" />fits the envelope</span><span className="lg"><i className="sw sw-out" />goes to the manual lane (too long, wide or tall)</span><span className="legend-hint">Drag the corner or click the plot.</span></p>
      <div className="sliders">
        <label><span>Longest side ≤ <b>{env.l} cm</b></span><input type="range" min={30} max={100} value={env.l} onChange={e => setEnv({ ...env, l: +e.target.value })} /></label>
        <label><span>Middle side ≤ <b>{env.m} cm</b></span><input type="range" min={20} max={70} value={env.m} onChange={e => setEnv({ ...env, m: +e.target.value })} /></label>
        <label><span>Shortest side ≤ <b>{env.s} cm</b></span><input type="range" min={5} max={45} value={env.s} onChange={e => setEnv({ ...env, s: +e.target.value })} /></label>
      </div>
    </div>
  )
}

export function StepFit({ st, s }: { st: Station; s: Summary }) {
  const shares = s.stations.map(x => x.sortable_share)
  const e = s.assumptions.ENVELOPE
  const def = { l: e.max_l, m: e.max_m, s: e.max_s }
  const sw = st.envelope.sweep_longest
  return (
    <Step n={2} id="fit" title="Parcels that fit the robot"
      lede={<>With an assumed 60 × 45 × 35 cm pick envelope, <b>{pct(st.envelope.sortable_share)}</b> of {st.station}’s parcels can go to a cell ({pct(Math.min(...shares))}–{pct(Math.max(...shares))} across the six stations). The rest go to a manual lane. Drag the envelope to see how little the edge matters.</>}
      details={<>
        <p>Each parcel’s dimensions are sorted so that longest ≥ middle ≥ shortest, then tested against the box. The envelope is an editable assumption, not any vendor’s specification, and no weight rule is applied because the dataset has no weights. The live figure above uses a {int(st.envelope.sample_cm.length)}-parcel sample ({pct(st.envelope.sample_share)} at the default); the headline uses every parcel at the station.</p>
        <div className="scroll"><table>
          <caption>{st.station}, all parcels: share that fits as the longest-side limit moves (middle 45, shortest 35 cm)</caption>
          <thead><tr><th>Longest side ≤</th>{sw.l_cm.filter((_, i) => i % 2 === 0).map(l => <th key={l}>{l} cm</th>)}</tr></thead>
          <tbody><tr><td>Fits</td>{sw.share.filter((_, i) => i % 2 === 0).map((v, i) => <td key={i}>{pct(v)}</td>)}</tr></tbody>
        </table></div>
        <p className="note">Moving the longest-side limit by 5 cm around 60 cm changes the share by {st.envelope.pts_per_5cm_at_default.toFixed(2)} percentage points at this station. Over all {int(s.dataset.packages)} parcels in the dataset, {pct(s.dataset.all_sortable_share)} fit.</p>
      </>}>
      <Envelope key={st.station} st={st} def={def} />
    </Step>
  )
}
