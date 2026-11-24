import { useId, useRef, useState } from 'react'
import { FOLDED_PX, dockHeight, stepDock } from './dock'

/**
 * The map above and a dock below it, on the stage the sidebar leaves. The dock has three states (kitx/dock.js):
 * folded (a thin bar), half and full (it takes the whole stage; the map then moves out of the way: the app places it, e.g.
 * as a small live map at the bottom of the sidebar, with the button this component draws). The divider is the dock's top
 * edge: a handle in the middle to drag (a drag sets a custom height and changes no mode) and, beside it, one pair of
 * buttons that make the dock smaller or larger by a step. Kit-like: no app imports; the styles are in kitx.css.
 *
 * Props
 *   map          the map, a block that fills its parent (the kit's .kit-map-wrap)
 *   state        'folded' | 'half' | 'full'; onState(state); onSettle() after a drag ended (the map box changed)
 *   label        accessible name of the dock (a landmark)
 *   title        the header line's left side (a heading, a back button...)
 *   tabs         the header line's middle: a Tabs control (kitx/Tabs.jsx)
 *   actions      more buttons at the right of the header line
 *   children     the dock's content (not rendered while folded); it should fill the height it is given
 *   strings      {larger, smaller, handle, back}: the button texts, in the page's language
 * The CSS custom property --kitx-dock-h on the stage tells the content how tall the dock is (a length).
 */
const TEXT = {
  larger: 'Powiększ panel', smaller: 'Zmniejsz panel', handle: 'Wysokość panelu: przeciągnij albo użyj strzałek góra i dół',
  back: 'Wróć do dużej mapy',
}
const FULL_AT = 0.93   // a drag that ends above this share of the stage makes the dock full

export default function DockStage({ map, state, onState, onSettle, label, title, tabs, actions, children, strings = {} }) {
  const t = { ...TEXT, ...strings }
  const stage = useRef(null)
  const bodyId = useId()
  const [dragH, setDragH] = useState(null)       // px while the handle is being dragged
  const [customH, setCustomH] = useState(null)   // px after a drag that ended between the states

  const stageH = () => stage.current?.getBoundingClientRect().height || window.innerHeight
  const onDown = (e) => {
    if (e.target.closest('button')) return
    e.currentTarget.setPointerCapture?.(e.pointerId)
    setDragH(customH ?? dockHeight(state, stageH()))
  }
  const onMove = (e) => {
    if (dragH == null) return
    const r = stage.current.getBoundingClientRect()
    setDragH(Math.min(r.height, Math.max(FOLDED_PX, r.bottom - e.clientY)))
  }
  const onUp = () => {
    if (dragH == null) return
    const h = stageH()
    const end = dragH
    setDragH(null)
    if (end <= FOLDED_PX + 24) { setCustomH(null); onState('folded') } else if (end >= h * FULL_AT) { setCustomH(null); onState('full') } else {
      setCustomH(Math.round(end))
      if (state === 'full' || state === 'folded') onState('half')   // a custom height is a half-like state
    }
    onSettle?.()
  }
  const step = (dir) => {
    setCustomH(null)
    onState(stepDock(customH != null ? 'half' : state, dir))
    onSettle?.()
  }
  const onKey = (e) => {
    if (e.key === 'ArrowUp') { e.preventDefault(); step(+1) }
    if (e.key === 'ArrowDown') { e.preventDefault(); step(-1) }
  }

  const live = dragH ?? (state === 'half' ? customH : null)
  const shown = dragH != null ? 'drag' : state
  const sizeVar = live != null ? `${live}px` : state === 'full' ? '100dvh' : '46dvh'
  return (
    <div ref={stage} className={`kitx-stage ${shown}${dragH != null ? ' dragging' : ''}`} style={{ '--kitx-dock-h': sizeVar }}>
      <div className="kitx-stage-map">{map}</div>
      {state === 'full' && (
        <button type="button" className="kitx-inset-back" aria-label={t.back} title={t.back} onClick={() => { setCustomH(null); onState('half') }}>
          <span aria-hidden="true">⤡</span> Duża mapa
        </button>
      )}
      <section className="kitx-dock" aria-label={label} style={live != null ? { height: live, flex: 'none' } : undefined}>
        <div
          className="kitx-dock-grip" role="separator" aria-orientation="horizontal" aria-label={t.handle} tabIndex={0}
          aria-valuenow={['folded', 'half', 'full'].indexOf(state)} aria-valuemin={0} aria-valuemax={2}
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onKeyDown={onKey}
        >
          <button type="button" className="kitx-dock-step" aria-label={t.smaller} title={t.smaller} disabled={state === 'folded'} aria-controls={bodyId} onClick={() => step(-1)}>▾</button>
          <span className="kitx-dock-pill" />
          <button type="button" className="kitx-dock-step" aria-label={t.larger} title={t.larger} disabled={state === 'full'} aria-expanded={state !== 'folded'} aria-controls={bodyId} onClick={() => step(+1)}>▴</button>
        </div>
        <header className="kitx-dock-head">
          <div className="kitx-dock-title">{title}</div>
          {tabs && <div className="kitx-dock-tabs">{tabs}</div>}
          {actions && <div className="kitx-dock-actions">{actions}</div>}
        </header>
        {state !== 'folded' && <div id={bodyId} className="kitx-dock-body">{children}</div>}
      </section>
    </div>
  )
}
