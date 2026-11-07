import type { ReactNode } from 'react'

/** Clean axis ticks: 0 plus round steps up to a max that covers the data. */
export function niceTicks(max: number, count = 4) {
  const raw = max / count
  const mag = Math.pow(10, Math.floor(Math.log10(raw)))
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) ?? 10 * mag
  const top = Math.ceil(max / step) * step
  const ticks: number[] = []
  for (let v = 0; v <= top + 1e-9; v += step) ticks.push(Math.round(v * 1000) / 1000)
  return { top, ticks }
}

/** Column with a rounded data end and a square baseline. */
export function colPath(x: number, y: number, w: number, h: number, r = 4) {
  if (h <= 0) return ''
  const rr = Math.min(r, w / 2, h)
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`
}

/** Horizontal bar, rounded at the right end. */
export function barPath(x: number, y: number, w: number, h: number, r = 4) {
  if (w <= 0) return ''
  const rr = Math.min(r, h / 2, w)
  return `M${x},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h - rr}Q${x + w},${y + h} ${x + w - rr},${y + h}H${x}Z`
}

export const tickLabel = (v: number) => (v >= 10000 ? `${v / 1000}K` : v.toLocaleString('en-US'))

export function Tip({ x, y, w, children }: { x: number; y: number; w: number; children: ReactNode }) {
  const left = Math.min(Math.max(8, x - 90), w - 188)
  return <div className="tip" style={{ transform: `translate(${left}px, ${y}px)` }} role="status">{children}</div>
}

// ---- icons (one stroke family, 1.75px) ----------------------------------------
type IconProps = { size?: number; className?: string }
const Svg = ({ size = 16, className, children }: IconProps & { children: ReactNode }) => (
  <svg className={className} width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
)
export const IconCheck = (p: IconProps) => <Svg {...p}><path d="M3 8.5l3.2 3L13 4.5" /></Svg>
export const IconAlert = (p: IconProps) => <Svg {...p}><path d="M8 2.2l6.2 11H1.8z" /><path d="M8 6.6v3" /><path d="M8 11.7v.1" /></Svg>
export const IconChevron = (p: IconProps) => <Svg {...p}><path d="M6 3.5l4.5 4.5L6 12.5" /></Svg>
export const IconReset = (p: IconProps) => <Svg {...p}><path d="M3 3.5v3.2h3.2" /><path d="M3.4 6.6A5 5 0 1 1 3.6 10" /></Svg>
export const IconArrow = (p: IconProps) => <Svg {...p}><path d="M3 8h10" /><path d="M9 4l4 4-4 4" /></Svg>
