import type { ReactNode } from 'react'
import { useSeen } from './hooks'
import { IconChevron } from './viz'

export function Step({ n, id, title, lede, children, details }: { n: number; id: string; title: string; lede: ReactNode; children: ReactNode; details?: ReactNode }) {
  const [ref, seen] = useSeen<HTMLDivElement>()
  return (
    <section id={id} className="step" aria-labelledby={`${id}-h`}>
      <div className="step-head">
        <span className="stencil" aria-hidden="true">{n}</span>
        <h2 id={`${id}-h`}>{title}</h2>
      </div>
      <p className="lede">{lede}</p>
      <div ref={ref} className="fig" data-seen={seen || undefined}>{children}</div>
      {details && (
        <details className="more">
          <summary><IconChevron className="more-chev" /> Show details</summary>
          <div className="more-body">{details}</div>
        </details>
      )}
    </section>
  )
}
