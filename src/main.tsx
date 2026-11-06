import { StrictMode, useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './styles.css'

type Station = {
  station: string; days: number; packages_total: number
  volume: { mean: number; p90: number; p90_peak: number; p90_over_mean: number }
  sortable_share: number; pts_per_5cm: number; peak_rate_over_mean_rate: number
  cells_hand_mean: number; cells_hand_p90: number; cells_erlang: number; cells_des: number | null; cells_for_destinations: number
}
type Summary = { stations: Station[]; dataset: { name: string; url: string; licence: string; routes: number; packages: number; stations: number; dates: string[] } }

const pct = (x: number) => `${(100 * x).toFixed(1)}%`

function App() {
  const [s, setS] = useState<Summary | null>(null)
  const [err, setErr] = useState<string | null>(null)
  useEffect(() => { fetch('/data/summary.json').then(r => r.json()).then(setS).catch(e => setErr(String(e))) }, [])
  if (err) return <p role="alert">Could not load results: {err}</p>
  if (!s) return <p>Loading precomputed results…</p>
  const d = s.dataset
  return (
    <main>
      <h1>Parcel Sort Cell Sizer</h1>
      <p>How many robotic sort cells a delivery station needs to clear its dispatch waves on a P90 day, from real parcel data.
        Precomputed results; the interactive walkthrough comes in the next pass.</p>
      <div className="scroll"><table>
        <caption>Cells needed per station at +10% peak (500 sorts/h per cell, &lt;1% of parcels late)</caption>
        <thead><tr><th>Station</th><th>Days</th><th>Mean/day</th><th>P90/day</th><th>P90 ÷ mean</th><th>Robot-sortable</th><th>Peak 15-min rate ÷ mean</th><th>Cells: mean rule</th><th>Cells: P90 rule</th><th>Cells: Erlang C</th><th>Cells: wave simulation</th></tr></thead>
        <tbody>{s.stations.map(r => (
          <tr key={r.station}><td>{r.station}</td><td>{r.days}</td><td>{r.volume.mean.toLocaleString()}</td><td>{r.volume.p90.toLocaleString()}</td>
            <td>{r.volume.p90_over_mean.toFixed(2)}</td><td>{pct(r.sortable_share)}</td><td>{r.peak_rate_over_mean_rate.toFixed(2)}</td>
            <td>{r.cells_hand_mean}</td><td>{r.cells_hand_p90}</td><td>{r.cells_erlang}</td><td><strong>{r.cells_des ?? '>max'}</strong></td></tr>))}
        </tbody>
      </table></div>
      <p className="credit">Data: <a href={d.url}>{d.name}</a>, {d.routes.toLocaleString()} routes, {d.packages.toLocaleString()} packages, {d.stations} stations, {d.dates[0]} to {d.dates[1]}. Licence {d.licence}. Volumes are packages on the routes in the public sample, not total station throughput. Inbound timing is a stated assumption (see METHOD.md).</p>
    </main>
  )
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>)
