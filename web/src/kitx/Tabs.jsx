import { useId } from 'react'

/**
 * Real tabs: an underlined row on a header line, visibly not a set of filter chips. role="tablist" with arrow keys, Home
 * and End; the selected tab is the one tab stop. The panel they switch has role="tabpanel" and `aria-labelledby` the
 * tab (`tabId(prefix, key)` and `panelId(prefix)` give the ids). Kit-like: no app imports; styles in kitx.css.
 *
 * Props
 *   tabs      [{key, label}]
 *   value     the key of the selected tab; onChange(key)
 *   label     accessible name of the tab list
 *   prefix    unique text for the ids (default: generated)
 */
export const tabId = (prefix, key) => `${prefix}-tab-${key}`
export const panelId = (prefix) => `${prefix}-panel`

export default function Tabs({ tabs, value, onChange, label, prefix }) {
  const own = useId()
  const p = prefix || own
  const move = (i) => {
    const t = tabs[(i + tabs.length) % tabs.length]
    onChange(t.key)
    document.getElementById(tabId(p, t.key))?.focus()
  }
  const onKey = (e, i) => {
    if (e.key === 'ArrowRight') { e.preventDefault(); move(i + 1) }
    else if (e.key === 'ArrowLeft') { e.preventDefault(); move(i - 1) }
    else if (e.key === 'Home') { e.preventDefault(); move(0) }
    else if (e.key === 'End') { e.preventDefault(); move(tabs.length - 1) }
  }
  return (
    <div className="kitx-tabs" role="tablist" aria-label={label}>
      {tabs.map((t, i) => (
        <button
          key={t.key} id={tabId(p, t.key)} type="button" role="tab" aria-selected={t.key === value}
          aria-controls={panelId(p)} tabIndex={t.key === value ? 0 : -1}
          className={t.key === value ? 'kitx-tab on' : 'kitx-tab'} onClick={() => onChange(t.key)} onKeyDown={(e) => onKey(e, i)}
        >{t.label}</button>
      ))}
    </div>
  )
}
