import { useId, useRef, useState } from 'react'
import { FOLDED_PX, dockHeight, snapDock, stepDock } from './dock'

/**
 * The map above and a dock below it, on the stage the sidebar leaves. The dock has three states (kitx/dock.js):
 * folded (a thin bar with its title and buttons), half (about 46 % of the stage) and full (it takes the whole stage
 * and the map shrinks to a small live inset in the corner, still pannable, with a button back to half). The dock's
 * top edge is a handle: drag it, or press the arrow keys on it, to change the state. The map element is the same
 * in every state (only its box changes), so it is never rebuilt. Kit-like: no app imports; the styles are in kitx.css.
 *
 * Props
 *   map          the map, a block that fills its parent (the kit's .kit-map-wrap)
 *   state        'folded' | 'half' | 'full'; onState(state)
 *   label        accessible name of the dock (a landmark)
 *   title        the title bar's left side (a heading, a back button...)
 *   actions      more buttons at the right of the title bar, before the size buttons
 *   children     the dock's content (not rendered while folded); it should fill the height it is given
 *   insetLabel   accessible name of the button that returns from full to half
 *   strings      {fold, unfold, half, full, handle, back}: the button texts, in the page's language
 * The CSS custom property --kitx-dock-h on the stage tells the content how tall the dock is (a length), so that a
 * table inside can bound its own height.
 */
const TEXT = {
  fold: 'Zwiń', unfold: 'Rozwiń', half: 'Połowa', full: 'Cały ekran', handle: 'Wysokość panelu: przeciągnij albo użyj strzałek',
  back: 'Pokaż większą mapę', group: 'Rozmiar panelu',
}

export default function DockStage({ map, state, onState, label, title, actions, children, strings = {} }) {
  const t = { ...TEXT, ...strings }
  const stage = useRef(null)
  const bodyId = useId()
  const [dragH, setDragH] = useState(null)   // px while the handle is being dragged

  const stageH = () => stage.current?.getBoundingClientRect().height || window.innerHeight
  const onDown = (e) => {
    e.currentTarget.setPointerCapture?.(e.pointerId)
    setDragH(dockHeight(state, stageH()))
  }
  const onMove = (e) => {
    if (dragH == null) return
    const r = stage.current.getBoundingClientRect()
    setDragH(Math.min(r.height, Math.max(FOLDED_PX, r.bottom - e.clientY)))
  }
  const onUp = () => {
    if (dragH == null) return
    onState(snapDock(dragH, stageH()))
    setDragH(null)
  }
  const onKey = (e) => {
    if (e.key === 'ArrowUp') { e.preventDefault(); onState(stepDock(state, +1)) }
    if (e.key === 'ArrowDown') { e.preventDefault(); onState(stepDock(state, -1)) }
  }

  const shown = dragH != null ? 'drag' : state
  const sizeVar = dragH != null ? `${dragH}px` : state === 'full' ? '100dvh' : '46dvh'
  return (
    <div ref={stage} className={`kitx-stage ${shown}${dragH != null ? ' dragging' : ''}`} style={{ '--kitx-dock-h': sizeVar }}>
      <div className="kitx-stage-map">{map}</div>
      {state === 'full' && (
        <button type="button" className="kitx-inset-back" aria-label={t.back} title={t.back} onClick={() => onState('half')}>
          <span aria-hidden="true">⤡</span>
        </button>
      )}
      <section className="kitx-dock" aria-label={label} style={dragH != null ? { height: dragH, flex: 'none' } : undefined}>
        <div
          className="kitx-dock-grip" role="separator" aria-orientation="horizontal" aria-label={t.handle} tabIndex={0}
          aria-valuenow={['folded', 'half', 'full'].indexOf(state)} aria-valuemin={0} aria-valuemax={2}
          onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onKeyDown={onKey}
        ><span /></div>
        <header className="kitx-dock-head">
          <div className="kitx-dock-title">{title}</div>
          <div className="kitx-dock-actions">
            {actions}
            <div className="kitx-dock-sizes" role="group" aria-label={t.group}>
              <button
                type="button" aria-expanded={state !== 'folded'} aria-controls={bodyId}
                onClick={() => onState(state === 'folded' ? 'half' : 'folded')}
              >{state === 'folded' ? t.unfold : t.fold}</button>
              <button type="button" aria-pressed={state === 'half'} onClick={() => onState('half')}>{t.half}</button>
              <button type="button" aria-pressed={state === 'full'} onClick={() => onState('full')}>{t.full}</button>
            </div>
          </div>
        </header>
        {state !== 'folded' && <div id={bodyId} className="kitx-dock-body">{children}</div>}
      </section>
    </div>
  )
}
