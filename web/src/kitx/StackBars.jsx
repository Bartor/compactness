import { inkOn } from '@bartor-net/ui-kit'

/**
 * One 100 % stacked bar per row, for comparing how several things split into the same parts: the kit's ShareBars,
 * except that a row's label can be a button (to open that thing). Uses the kit's styles for the bars. Kit-like: no
 * app imports.
 *
 * Props
 *   rows    [{key, label: string, onPick?, parts: [{key, label, color, share}]}]; share is 0..1
 *   pick    {active: Set of part keys lit now, on(key) -> handlers}: what usePick() returns (or a bridge to one)
 *   label   accessible name of the whole
 * With parts lit, each row shows their sum at its end; a part that fills at least `MIN_LABEL` of the bar shows its
 * percentage, thinner ones have it in the tooltip.
 */
const MIN_LABEL = 0.09
const none = { active: new Set(), on: () => ({}) }

export default function StackBars({ rows, pick = none, label }) {
  const dim = (key) => pick.active.size > 0 && !pick.active.has(key)
  return (
    <div className="kit-sharebars kitx-stack" role="table" aria-label={label}>
      {rows.map((r) => {
        const sum = r.parts.filter((p) => pick.active.has(p.key)).reduce((a, p) => a + p.share, 0)
        return (
          <div key={r.key} className="kit-sharebar" role="row">
            <span role="rowheader">
              {r.onPick
                ? <button type="button" className="kitx-stack-pick" onClick={r.onPick}>{r.label}</button>
                : r.label}
            </span>
            <div className="bar">
              {r.parts.filter((p) => p.share > 0).map((p) => (
                <i
                  key={p.key} role="cell" {...pick.on(p.key)} className={dim(p.key) ? 'dim' : undefined}
                  style={{ flexGrow: p.share, background: p.color, color: inkOn(p.color) }}
                  title={`${p.label}: ${Math.round(p.share * 100)} % (${r.label})`}
                >
                  {p.share >= MIN_LABEL ? `${Math.round(p.share * 100)} %` : ''}
                </i>
              ))}
            </div>
            <b>{pick.active.size > 0 ? `${Math.round(sum * 100)} %` : ''}</b>
          </div>
        )
      })}
    </div>
  )
}
