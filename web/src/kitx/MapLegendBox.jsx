/**
 * The frame of a map legend in a corner of the map, in the style of the kit's MapLegend: a small card that folds into
 * a button. It never grows past about half of the height of the map (it scrolls inside instead). Kit-like: no app
 * imports; the styles are in kitx.css and reuse the kit's .kit-map-legend. Put it inside the map's positioned box.
 *
 * Props
 *   open, onToggle(open)   whether it is unfolded; the caller keeps the state, so it can start open or folded
 *   label                  text of the folded button (default "Legenda") and the card's accessible name
 *   foldLabel              accessible name of the close button
 *   children               the key
 */
export default function MapLegendBox({ open, onToggle, label = 'Legenda', foldLabel = 'Zwiń legendę', children }) {
  if (!open) {
    return (
      <button type="button" className="kit-map-legend closed" aria-expanded="false" onClick={() => onToggle(true)}>
        {label}
      </button>
    )
  }
  return (
    <div className="kit-map-legend kitx-legend" role="group" aria-label={label}>
      <button type="button" className="kit-legend-close" aria-expanded="true" aria-label={foldLabel} onClick={() => onToggle(false)}>×</button>
      <div className="kitx-legend-scroll">{children}</div>
    </div>
  )
}
