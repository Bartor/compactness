// Loading what a selection needs: the tram detail document of a city (catalog `detail_url_template`), or the
// features of a bus / rail file (their map properties are all the panel has). One fetch per url, kept.
import { useEffect, useState } from 'react'
import { parseDetail } from './segModel'

const cache = new Map()

function load(url, parse, fetchImpl) {
  if (!cache.has(url)) {
    const p = Promise.resolve(fetchImpl(url))
      .then((r) => {
        if (!r.ok) throw new Error(`Nie udało się wczytać danych odcinków (${r.status}).`)
        return r.json()
      })
      .then(parse)
      .catch((e) => { cache.delete(url); throw e })
    cache.set(url, p)
  }
  return cache.get(url)
}

/** Tram detail of a city: parseDetail(document). */
export const loadDetail = (url, fetchImpl = (u) => fetch(u)) => load(url, parseDetail, fetchImpl)

/** Features of a GeoJSON file indexed by their `id`: {byId: Map(id -> feature)}. */
export const loadFeatures = (url, fetchImpl = (u) => fetch(u)) => load(url, (fc) => ({
  byId: new Map((fc.features || []).map((f) => [f.properties?.id, f])),
}), fetchImpl)

export const clearSegCache = () => cache.clear()

/**
 * {status: 'idle' | 'loading' | 'ready' | 'error', data, url} for a url and a loader; idle without a url.
 */
export function useLoaded(url, loader) {
  const [st, setSt] = useState({ status: url ? 'loading' : 'idle', data: null, url })
  useEffect(() => {
    if (!url) { setSt({ status: 'idle', data: null, url }); return undefined }
    let live = true
    setSt((s) => (s.url === url && s.status === 'ready' ? s : { status: 'loading', data: null, url }))
    loader(url).then((d) => { if (live) setSt({ status: 'ready', data: d, url }) }, () => { if (live) setSt({ status: 'error', data: null, url }) })
    return () => { live = false }
  }, [url, loader])
  return st
}
