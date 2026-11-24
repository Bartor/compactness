// React state of the "skąd dojadę" mode: the file of the selected city, the picked origin and the scenario shown on
// the map. The map component calls pick([lon, lat]) on a click; it gets back `layers` for syncIsochrones().
import { useEffect, useMemo, useState } from 'react'
import { loadIsochrones } from './isoData'
import { isoGeoJSON, nearestOrigin, originGeoJSON } from './isoModel'

/**
 * @param {string|null} agg   selected agglomeration id (the mode works inside one city)
 * @param {boolean} on        the mode is switched on
 * @returns {{file, status, origin, distanceM, clicked, scenario, setScenario, pick, clear, layers}}
 *   status: 'off' | 'loading' | 'ready' | 'missing'; layers: {bands, walk, origin} or null
 */
export default function useIsochroneMode(agg, on, { load = loadIsochrones } = {}) {
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('off')
  const [picked, setPicked] = useState(null)        // {origin, distanceM, clicked}
  const [scenario, setScenario] = useState('am')

  useEffect(() => {
    setPicked(null)
    if (!on || !agg) {
      setFile(null)
      setStatus('off')
      return undefined
    }
    let live = true
    setStatus('loading')
    load(agg).then((f) => {
      if (!live) return
      setFile(f)
      setStatus(f ? 'ready' : 'missing')
    })
    return () => { live = false }
  }, [agg, on, load])

  const pick = (lngLat) => {
    if (!file) return null
    const hit = nearestOrigin(file.origins, lngLat)
    setPicked(hit ? { ...hit, clicked: lngLat } : null)
    return hit
  }
  const pickById = (id) => {
    const o = file?.origins.find((x) => x.id === id)
    setPicked(o ? { origin: o, distanceM: 0, clicked: [o.lon, o.lat] } : null)
  }

  const layers = useMemo(() => {
    if (!file || !picked) return null
    const id = picked.origin.id
    return { bands: isoGeoJSON(file, id, scenario), walk: isoGeoJSON(file, id, 'walk'), origin: originGeoJSON(picked.origin) }
  }, [file, picked, scenario])

  return {
    file, status, scenario, setScenario, pick, pickById, clear: () => setPicked(null), layers,
    origin: picked?.origin ?? null, distanceM: picked?.distanceM ?? null, clicked: picked?.clicked ?? null,
  }
}
