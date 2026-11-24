// Bridge between the class focus of the page (classFocus.js, kept by useFocuses: hover and pin per layer, shared by
// the legend and the map) and the kit's "pick" of a chart (usePick: {active, pinned, toggle, on}). The kit's Donut,
// SplitTable and ShareBars take this object as their `pick`, so pointing at a slice or a row does what pointing at
// a legend row does, and the map follows. Keys are class indices as text ("0", "1", ...); other keys (a no-data
// slice, say) are lit by nothing and pick nothing.
import { emphasised } from './classFocus'

const isClassKey = (key) => /^\d+$/.test(key)

/**
 * `focus` is the focus of one layer (focusOf), `handlers` {onHover(layerId, index|null), onToggle(layerId, index)};
 * `hover` says whether hovering previews (false on touch screens).
 */
export function focusPick(focus, layerId, handlers, hover = true) {
  const active = new Set([...emphasised(focus, layerId)].map(String))
  const pinned = new Set((focus.layerId === layerId ? focus.pinned : []).map(String))
  const toggle = (key) => { if (isClassKey(key)) handlers.onToggle?.(layerId, Number(key)) }
  return {
    active,
    pinned,
    toggle,
    on: (key) => {
      if (!isClassKey(key)) return {}
      return {
        onMouseEnter: hover ? () => handlers.onHover?.(layerId, Number(key)) : undefined,
        onMouseLeave: hover ? () => handlers.onHover?.(layerId, null) : undefined,
        onClick: () => toggle(key),
      }
    },
  }
}

/** The pinned class indices of a layer, sorted. */
export const pinnedOf = (focus, layerId) => (focus.layerId === layerId ? [...focus.pinned] : [])
