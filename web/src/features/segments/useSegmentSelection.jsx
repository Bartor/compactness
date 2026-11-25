import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { idsFilter } from '../speed/lineLayers'
import SegmentPanel from './SegmentPanel'
import { loadDetail, loadFeatures, useLoaded } from './segData'
import { CITY_CODES, aggOfSel, boundsOf, featureBounds, parseSel, selText, toggleId } from './segModel'

/**
 * The selection of speed features (README.md): state, data, map filters and the panel, for the page to wire.
 *
 * Arguments: {layers} the map's catalog layers (with `band`); active Set of layer ids on; selectedId the city; band;
 * onBand(key); initial the address text ("tram:id,id") or null; resolve(url) -> absolute url; cityName(agg).
 * Returns {sel, text (for the address), lineSel ({layerId: filter}), onLinePick, panel (element or null), bounds, n}.
 */
export function useSegmentSelection({ layers, active, selectedId, band, onBand, initial, resolve, cityName }) {
  const [sel, setSel] = useState(() => parseSel(initial))
  const [lastId, setLastId] = useState(null)
  const layerOf = useCallback((mode) => layers.find((l) => l.kind === 'lines' && l.mode_group === mode) || null, [layers])
  const agg = aggOfSel(sel, CITY_CODES)
  const layer = sel ? layerOf(sel.mode) : null

  // the data: the tram detail of the city, or the features of the bus / rail file
  const tramUrl = sel?.mode === 'tram' && agg && layer?.detail_url_template ? resolve(layer.detail_url_template.replace('{agg}', agg)) : null
  const featUrl = sel && sel.mode !== 'tram' && layer
    ? resolve(layer.url_template ? (agg ? layer.url_template.replace('{agg}', agg) : null) : layer.url)
    : null
  const tram = useLoaded(tramUrl, loadDetail)
  const feats = useLoaded(featUrl, loadFeatures)

  const onLinePick = useCallback(({ layer: l, id, properties }) => {
    const mode = l.mode_group || 'tram'
    const pickAgg = properties?.agg || null
    setLastId(id)
    setSel((cur) => {
      if (!cur || cur.mode !== mode || (pickAgg && aggOfSel(cur, CITY_CODES) !== pickAgg)) return { mode, ids: [id] }
      const ids = toggleId(cur.ids, id)
      return ids.length ? { mode, ids } : null
    })
  }, [])
  const onIds = useCallback((ids) => setSel((cur) => (cur && ids.length ? { ...cur, ids } : null)), [])
  const clear = useCallback(() => { setSel(null); setLastId(null) }, [])

  // the layer of the selection switched off: the selection goes with it
  useEffect(() => {
    if (sel && (!layer || !active.has(layer.id))) clear()
  }, [active, layer, sel, clear])
  // another city picked: a selection elsewhere is dropped
  const prevCity = useRef(selectedId)
  useEffect(() => {
    const was = prevCity.current
    prevCity.current = selectedId
    if (was !== selectedId && selectedId && agg && agg !== selectedId) clear()
  }, [selectedId, agg, clear])
  // Escape clears the selection (a popup or a dialog takes it first)
  useEffect(() => {
    if (!sel) return undefined
    const onKey = (e) => {
      if (e.key !== 'Escape' || e.defaultPrevented) return
      if (document.querySelector('dialog[open]')) return
      clear()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [sel, clear])

  const key = sel ? `${sel.mode}:${sel.ids.join(',')}` : ''
  const lineSel = useMemo(() => (sel && layer ? { [layer.id]: idsFilter(sel.ids) } : null), [key, layer])   // eslint-disable-line react-hooks/exhaustive-deps
  const bounds = useMemo(() => {
    if (!sel) return null
    if (sel.mode === 'tram') return tram.status === 'ready' ? boundsOf(sel.ids.map((id) => tram.data.byId.get(id)).filter(Boolean)) : null
    return feats.status === 'ready' ? featureBounds(sel.ids.map((id) => feats.data.byId.get(id)).filter(Boolean)) : null
  }, [key, tram, feats])   // eslint-disable-line react-hooks/exhaustive-deps
  // a new key each time the selection (or its data) changes: the map keeps it in view
  const n = useRef(0)
  const seen = useRef('')
  const bkey = `${key}|${bounds ? bounds.join(',') : ''}`
  if (bkey !== seen.current) { seen.current = bkey; n.current += 1 }

  const panel = sel
    ? (
      <SegmentPanel
        sel={sel} band={band} tram={tram} feats={feats} lastId={lastId} cityName={agg ? cityName?.(agg) : null}
        dates={layer?.timetable_dates || null} onIds={onIds} onClear={clear} onBand={onBand}
      />
    )
    : null
  return { sel, text: selText(sel), lineSel, onLinePick, panel, bounds, n: n.current, clear }
}
