import { STEPS } from './data'

// Overhead plan of a small sort floor. The numbered floor stencils are the story's steps, placed where
// each question lives on the floor, and they jump to that step.
const W = 1200
const H = 440

const cellsX = [300, 480, 660, 840]
const pins: { n: number; x: number; y: number }[] = [
  { n: 1, x: 160, y: 378 },   // inbound docks: the station's day
  { n: 2, x: 210, y: 58 },   // a parcel on the infeed: does it fit
  { n: 3, x: 560, y: 58 },   // the belt filling up: the wave
  { n: 4, x: 570, y: 378 },  // the cell bank
  { n: 5, x: 1086, y: 160 }, // the departure board: forecast
  { n: 6, x: 965, y: 378 },  // overflow lane: late parcels, cells saved
  { n: 7, x: 1130, y: 378 }, // QA desk: how we know
]

export function FloorPlan() {
  const rollers = []
  for (let x = 60; x < 1000; x += 14) rollers.push(<line key={x} x1={x} x2={x} y1={108} y2={136} />)
  const parcels = [0, 1, 2, 3, 4, 5, 6, 7, 8]
  return (
    <svg className="plan" viewBox={`0 0 ${W} ${H}`} role="img" aria-labelledby="plan-t">
      <title id="plan-t">Overhead plan of a parcel sort floor: inbound docks, an infeed conveyor, four robotic sort cells ringed by gaylords, an overflow lane and outbound doors under a departure board. Numbered floor marks link to the seven steps.</title>
      {/* structural bays */}
      <g className="plan-bay">
        {[150, 300, 450, 600, 750, 900, 1050].map(x => <line key={x} x1={x} x2={x} y1={0} y2={H} />)}
        {[150, 300].map(y => <line key={y} x1={0} x2={W} y1={y} y2={y} />)}
        {[150, 300, 450, 600, 750, 900, 1050].flatMap(x => [150, 300].map(y => <rect key={`${x}-${y}`} x={x - 5} y={y - 5} width={10} height={10} className="plan-col" />))}
      </g>
      {/* inbound doors */}
      <g className="plan-door">
        {[70, 150, 230, 310].map(y => <rect key={y} x={0} y={y} width={18} height={56} />)}
      </g>
      <text className="plan-label" x={26} y={384}>Inbound</text>
      {/* walkway tape */}
      <path className="plan-tape" d="M30 336H1180" />
      <path className="plan-tape" d="M30 420H1180" />
      {/* infeed belt */}
      <rect className="plan-belt" x={40} y={104} width={980} height={36} rx={2} />
      <g className="plan-roller">{rollers}</g>
      <g className="plan-parcels">
        {parcels.map(i => <rect key={i} className="plan-parcel" style={{ animationDelay: `${-i * 2.4}s` }} x={40} y={i % 2 ? 112 : 116} width={i % 3 ? 22 : 30} height={i % 2 ? 20 : 14} rx={1.5} />)}
      </g>
      <text className="plan-label" x={60} y={92}>Infeed</text>
      {/* induction + cells + gaylords */}
      {cellsX.map((cx, i) => (
        <g key={cx}>
          <rect className="plan-induct" x={cx - 26} y={142} width={52} height={20} />
          <rect className="plan-cell" x={cx - 48} y={170} width={96} height={96} />
          <circle className="plan-robot" cx={cx} cy={218} r={20} />
          <path className="plan-arm" d={`M${cx} 218L${cx + (i % 2 ? -26 : 26)} ${i % 2 ? 196 : 240}`} />
          {[-36, -12, 12, 36].map(dx => <rect key={dx} className="plan-gaylord" x={cx + dx - 10} y={276} width={20} height={20} />)}
          {[0, 1].map(k => <rect key={k} className="plan-gaylord" x={cx - 74} y={186 + k * 34} width={20} height={20} />)}
          {[0, 1].map(k => <rect key={k} className="plan-gaylord" x={cx + 54} y={186 + k * 34} width={20} height={20} />)}
        </g>
      ))}
      <text className="plan-label" x={252} y={322}>Cells and gaylords</text>
      {/* overflow lane */}
      <rect className="plan-overflow" x={920} y={180} width={90} height={130} />
      <text className="plan-label" x={928} y={172}>Overflow</text>
      {/* outbound doors + board */}
      <g className="plan-door">
        {[180, 250, 320].map(y => <rect key={y} x={W - 18} y={y - 10} width={18} height={50} />)}
      </g>
      <g className="plan-board">
        <rect x={1040} y={34} width={140} height={84} rx={2} />
        {[0, 1, 2].map(r => <g key={r}>{[0, 1, 2, 3, 4, 5, 6].map(c => <rect key={c} className="plan-flap" x={1050 + c * 18} y={46 + r * 22} width={14} height={16} rx={1} />)}</g>)}
      </g>
      <text className="plan-label" x={1040} y={24}>Departures</text>
      {/* step stencils */}
      {pins.map(p => (
        <a key={p.n} href={`#${STEPS[p.n - 1].id}`} className="plan-pin" aria-label={`Step ${p.n}: ${STEPS[p.n - 1].title}`}>
          <rect x={p.x - 24} y={p.y - 24} width={48} height={48} />
          <text x={p.x} y={p.y + 1}>{p.n}</text>
        </a>
      ))}
    </svg>
  )
}
