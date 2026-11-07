import { useEffect, useState } from 'react'
import type { Forecast, Station, Summary, Validation } from './data'
import { getJSON, int, STEPS } from './data'
import { useActiveStep } from './hooks'
import { FloorPlan } from './FloorPlan'
import { IconArrow } from './viz'
import { StepDay } from './steps/StepDay'
import { StepFit } from './steps/StepFit'
import { StepWave } from './steps/StepWave'
import { StepCells } from './steps/StepCells'
import { StepForecast } from './steps/StepForecast'
import { StepSaved } from './steps/StepSaved'
import { StepKnow } from './steps/StepKnow'
import { StepSolution } from './steps/StepSolution'

const IDS = STEPS.map(s => s.id)

function StationPicker({ list, value, onChange, compact }: { list: string[]; value: string; onChange: (s: string) => void; compact?: boolean }) {
  return (
    <div className={compact ? 'picker picker-compact' : 'picker'} role="radiogroup" aria-label="Delivery station">
      {list.map(s => (
        <button key={s} type="button" role="radio" aria-checked={s === value} className={s === value ? 'on' : undefined} onClick={() => onChange(s)}>{s}</button>
      ))}
    </div>
  )
}

export function App() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [forecast, setForecast] = useState<Forecast | null>(null)
  const [validation, setValidation] = useState<Validation | null>(null)
  const [stations, setStations] = useState<Record<string, Station>>({})
  const [station, setStation] = useState('DLA7')
  const [err, setErr] = useState<string | null>(null)
  const { active, progress } = useActiveStep(IDS)

  useEffect(() => {
    Promise.all([getJSON<Summary>('summary.json'), getJSON<Forecast>('forecast.json'), getJSON<Validation>('validation.json')])
      .then(([s, f, v]) => { setSummary(s); setForecast(f); setValidation(v) })
      .catch(e => setErr(String(e)))
  }, [])

  useEffect(() => {
    if (stations[station]) return
    getJSON<Station>(`station-${station}.json`).then(d => setStations(m => ({ ...m, [station]: d }))).catch(e => setErr(String(e)))
  }, [station, stations])

  const st = stations[station]
  const list = summary?.stations.map(s => s.station) ?? []
  const ready = summary && forecast && validation && st

  return (
    <div className="shell">
      <aside className="rail" aria-label="Steps">
        <a className="rail-title" href="#top">Parcel Sort<br />Cell Sizer</a>
        {list.length > 0 && <><p className="rail-k">Station</p><StationPicker list={list} value={station} onChange={setStation} compact /></>}
        <nav>
          <ol className="rail-steps">
            {STEPS.map((s, i) => (
              <li key={s.id} className={i === active ? 'on' : i < active ? 'done' : undefined}>
                <a href={`#${s.id}`} aria-current={i === active ? 'step' : undefined}><span className="rail-n">{i + 1}</span>{s.title}</a>
              </li>
            ))}
          </ol>
        </nav>
      </aside>

      <div className="mbar" aria-hidden={false}>
        <div className="mbar-row">
          <span className="mbar-step">{active >= 0 ? <><b>{active + 1}/{STEPS.length}</b> {STEPS[active].title}</> : 'Parcel Sort Cell Sizer'}</span>
          {list.length > 0 && (
            <label className="mbar-sel"><span className="sr">Station</span>
              <select value={station} onChange={e => setStation(e.target.value)}>{list.map(s => <option key={s}>{s}</option>)}</select>
            </label>
          )}
        </div>
        <div className="mbar-prog"><i style={{ transform: `scaleX(${progress})` }} /></div>
      </div>

      <main id="top">
        <header className="intro">
          <p className="intro-k">Parcel Sort Cell Sizer</p>
          <h1 className="intro-q">How many sort cells does a delivery station need to make every departure on a busy day?</h1>
          <p className="intro-lede"><b>More than the average says.</b> On {summary ? int(summary.stations.reduce((a, x) => a + x.packages_total, 0)) : '899,387'} real parcels, dividing a busy day by the sort window came up a cell short at {summary ? summary.stations.filter(x => x.cells_hand_p90 < x.cells_fifo20).length : 3} of {summary ? summary.stations.length : 6} stations. <b>The fix:</b> size against each departure wave, with a P90 margin that shrinks as waves grow. Replayed on {forecast ? forecast.sizing.h1.station_days : 122} held-out station-days, no day left 1% of parcels late, on {forecast ? forecast.sizing.h1.summary.routes_x_ppr_calibrated_by_wave_size.excess_cells : 24} surplus cell-days against {forecast ? forecast.sizing.h1.summary.routes_x_ppr_calibrated.excess_cells : 43} for a flat margin.</p>
          <a className="cta" href="#solution">Here’s the playbook <IconArrow /></a>
          <FloorPlan />
          {list.length > 0 && (
            <div className="intro-pick">
              <p>Pick a station. Every step follows it.</p>
              <StationPicker list={list} value={station} onChange={setStation} />
            </div>
          )}
        </header>

        {err && <p className="error" role="alert">Could not load the precomputed results ({err}). Reload the page to try again.</p>}
        {!ready && !err && <p className="loading">Loading precomputed results…</p>}
        {ready && (
          <>
            <StepDay st={st} v={validation} />
            <StepFit st={st} s={summary} />
            <StepWave st={st} s={summary} />
            <StepCells key={station} st={st} s={summary} />
            <StepForecast f={forecast} station={station} />
            <StepSaved s={summary} st={st} onPick={setStation} />
            <StepKnow v={validation} st={st} s={summary} />
            <StepSolution f={forecast} v={validation} st={st} s={summary} />
          </>
        )}

        <footer className="foot">
          {summary && (
            <p>Data: <a href={summary.dataset.url}>{summary.dataset.name}</a>, {int(summary.dataset.routes)} routes, {int(summary.dataset.packages)} parcels, {summary.dataset.stations} stations, {summary.dataset.dates[0]} to {summary.dataset.dates[1]}. Licence {summary.dataset.licence}, Amazon.com, Inc. and MIT Center for Transportation &amp; Logistics; used non-commercially. Volumes are parcels on the routes in the public sample, not total station throughput. Inbound arrival timing is a stated assumption tied to real departure times. Wages: BLS OEWS (public domain). Cell and manual sort rates are published industry figures. All results are precomputed by the pipeline in this repository; see METHOD.md.</p>
          )}
          <p className="foot-more">More work at <a href="https://ibiraheel.com">ibiraheel.com</a></p>
        </footer>
      </main>
    </div>
  )
}
