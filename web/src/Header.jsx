import { useEffect, useRef, useState } from 'react'
import { Select } from '@bartor-net/ui-kit'
import { DOMAIN_INFO } from './metricInfo'
import { AREAS } from './metricTable'

export const APP_NAME = 'Zwartość miast'
export const APP_SUBTITLE = 'Komunikacja zbiorowa i gęstość zaludnienia w polskich aglomeracjach'

/** The one global area switch: which area every number on the page refers to. */
export function AreaSwitch({ area, onArea }) {
  return (
    <div className="area-switch" role="group" aria-label="Obszar, którego dotyczą liczby">
      {AREAS.map((a) => (
        <button
          key={a} type="button" aria-pressed={a === area} title={DOMAIN_INFO[a].read}
          onClick={() => onArea(a)}
        >{DOMAIN_INFO[a].short}</button>
      ))}
    </div>
  )
}

/**
 * The bar across the top, the only home of global state: the name (a button that goes home), the city picker, the area
 * switch and "O danych". On a phone: the name, the picker and a menu button holding the rest.
 */
export default function Header({ catalog, selectedId, onPick, onHome, area, onArea, onAbout, onCompare, phone }) {
  const options = [
    { value: '', label: 'Wszystkie aglomeracje' },
    ...catalog.agglomerations.map((a) => ({ value: a.id, label: a.name })),
  ]
  const [menu, setMenu] = useState(false)
  const box = useRef(null)
  useEffect(() => {
    if (!menu) return undefined
    const away = (e) => { if (box.current && !box.current.contains(e.target)) setMenu(false) }
    const esc = (e) => { if (e.key === 'Escape') setMenu(false) }
    document.addEventListener('pointerdown', away)
    document.addEventListener('keydown', esc)
    return () => { document.removeEventListener('pointerdown', away); document.removeEventListener('keydown', esc) }
  }, [menu])

  return (
    <header className="app-header">
      <button type="button" className="app-name" onClick={onHome} title="Wróć do widoku wszystkich aglomeracji">
        <b>{APP_NAME}</b>
        {!phone && <span>{APP_SUBTITLE}</span>}
      </button>
      <div className="app-picker">
        <Select label="Aglomeracja" value={selectedId || ''} options={options} onChange={(v) => onPick(v || null)} />
      </div>
      {phone
        ? (
          <div className="app-menu" ref={box}>
            <button type="button" className="app-menu-btn" aria-expanded={menu} aria-haspopup="true" onClick={() => setMenu(!menu)}>Menu</button>
            {menu && (
              <div className="app-menu-pop" role="group" aria-label="Menu">
                <button type="button" className="app-about" onClick={() => { setMenu(false); onCompare?.() }}>Porównanie aglomeracji</button>
                <p className="app-menu-label">Obszar, którego dotyczą liczby</p>
                <AreaSwitch area={area} onArea={onArea} />
                <button type="button" className="app-about" onClick={() => { setMenu(false); onAbout() }}>O danych</button>
              </div>
            )}
          </div>
        )
        : (
          <>
            <div className="app-area">
              <span className="app-area-label">Obszar:</span>
              <AreaSwitch area={area} onArea={onArea} />
            </div>
            <button type="button" className="app-about" onClick={onAbout}>O danych</button>
          </>
        )}
    </header>
  )
}
