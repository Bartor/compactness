import { useCallback, useEffect, useMemo, useState } from 'react'
import { EMPTY_FOCUSES, clearPinned, hoverClass, pruneFocuses, togglePinned, updateFocus } from './classFocus'

/**
 * The hover and pin state of the colour classes of all layers (classFocus.js), kept by the common parent of
 * the sidebar legend and the map. `setFocuses` takes an updater, as React's; the handlers are those of the
 * legend rows. A layer switched off (not in `active`) loses its focus.
 */
export function useFocuses(active) {
  const [focuses, setFocuses] = useState(EMPTY_FOCUSES)
  useEffect(() => setFocuses((f) => pruneFocuses(f, active)), [active])
  const onHover = useCallback((id, i) => setFocuses((f) => updateFocus(f, id, (x) => hoverClass(x, id, i))), [])
  const onToggle = useCallback((id, i) => setFocuses((f) => updateFocus(f, id, (x) => togglePinned(x, id, i))), [])
  const onClear = useCallback((id) => setFocuses((f) => updateFocus(f, id, (x) => clearPinned(x, id))), [])
  return useMemo(() => ({ focuses, setFocuses, onHover, onToggle, onClear }), [focuses, onHover, onToggle, onClear])
}
