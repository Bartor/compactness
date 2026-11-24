import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it, vi } from 'vitest'
import {
  CELL_COLORS, aggOfNode, bandText, cellColor, createDetailLoader, decodeNode, dirLabel, matrixModel, minText,
  obstacleRows, pairs, summarySentence, sumParts, topMovementTable,
} from './detailData'
import {
  DETAIL_SOURCE, LAYER_IDS, clearNodeDetail, detailBounds, detailFeatures, detailLayerSpecs, hotFilter, setHotPath,
  showNodeDetail,
} from './detailLayers'
import NodeDetail from './NodeDetail'

const flat = (s) => s.replace(/ | /g, ' ')

// A record in the shape pipeline/transfer_detail.py writes: two lines, tram 4 both ways and bus 190 one way.
const REC = {
  id: 'poznan-T00012', n: 'Rondo Testowe', c: [16.9, 52.4], dep: 45.2, md: 'bus,tram',
  sum: { walk: 1.64, wait: 7.14, conn: 7.0, conn50: 6, conn90: 12.7, gtt: [17.5, 26.2, 31.2], w6: [61, 49], x: 1.1, steps: 0.2, free: 1, f10: 0.17, f15: 0.48 },
  l: [['4', 'tram'], ['190', 'bus']],
  d: [[0, 'Biskupin', 'a', 56], [0, 'Oporów', 'a', 50], [1, 'Pętla', 'd', 20], [0, 'Oporów', 'd', 50]],
  s: [[16.9001, 52.4001, 'Rondo A', [0]], [16.9005, 52.4003, 'Rondo B', [0, 1]]],
  p: [{ a: 0, b: 1, g: [16.9001, 52.4001, 16.9003, 52.4002, 16.9005, 52.4003], m: 60, t: 0.7, x: [[16.9003, 52.4002, 'signal']], st: [[16.9004, 52.40025]] }],
  mv: [
    [0, 2, 0, 0.7, 5.5, 4, 9, 56, 20, 70],
    [1, 2, -1, 0, 5.5, null, null, 50, 20, null],
    [0, 3, 0, 0.7, 3.2, 2.5, 6, 56, 50, 70],
  ],
  top: [2, 0, 1], ar: [0, 1], dp: [2, 3],
}

describe('loader', () => {
  it('reads the agglomeration from a node id', () => {
    expect(aggOfNode('poznan-T00012')).toBe('poznan')
    expect(aggOfNode('gzm-T01000')).toBe('gzm')
    expect(aggOfNode('nonsense')).toBe(null)
  })
  it('fetches each city file once, returns null for a node without detail', async () => {
    const fetchJson = vi.fn(async () => ({ nodes: [REC] }))
    const L = createDetailLoader({ base: 'd/', fetchJson })
    expect(await L.get('poznan-T00012')).toEqual(REC)
    expect(await L.get('poznan-T99999')).toBe(null)
    expect(fetchJson).toHaveBeenCalledTimes(1)
    expect(fetchJson).toHaveBeenCalledWith('d/poznan.json')
    expect(L.cached()).toEqual(['poznan'])
  })
  it('does not keep a failed fetch: the next call tries again', async () => {
    let n = 0
    const fetchJson = vi.fn(async () => { n += 1; if (n === 1) throw new Error('HTTP 404'); return { nodes: [REC] } })
    const L = createDetailLoader({ base: 'd/', fetchJson })
    await expect(L.get('poznan-T00012')).rejects.toThrow('404')
    expect(await L.get('poznan-T00012')).toEqual(REC)
    expect(fetchJson).toHaveBeenCalledTimes(2)
  })
})

describe('decoding and models', () => {
  const node = decodeNode(REC)
  it('decodes lines, directions, stops, paths and movements that refer to each other', () => {
    expect(node.dirs[0].label).toBe('4 → Biskupin')
    expect(dirLabel({ label: 'IC' }, '')).toBe('IC')
    expect(node.paths[0].coords).toEqual([[16.9001, 52.4001], [16.9003, 52.4002], [16.9005, 52.4003]])
    expect(pairs([1, 2, 3])).toEqual([[1, 2]])
    expect(node.moves[0].from.label).toBe('4 → Biskupin')
    expect(node.moves[0].to.label).toBe('190 → Pętla')
    expect(node.moves[2].trips).toBe(56 * 50)
    expect(node.top.map((m) => m.i)).toEqual([2, 0, 1])
    expect(decodeNode(null)).toBe(null)
  })
  it('the sentence adds up the printed parts and says when there is no data', () => {
    expect(flat(summarySentence(node))).toBe('Typowa przesiadka: 1,6 min dojścia + 7,1 min czekania (7–9, średnia ważona liczbą kursów).')
    expect(summarySentence(decodeNode({ ...REC, sum: {} }))).toContain('brak danych')
    expect(sumParts(0.66, 5.54)).toEqual({ walk: 0.7, wait: 5.5, total: 6.2 })
    expect(sumParts(1, null)).toBe(null)
  })
  it('matrix: rows arriving, columns departing; same line and missing movements are marked, not zero', () => {
    const M = matrixModel(node)
    expect(M.rows.map((r) => r.label)).toEqual(['4 → Biskupin', '4 → Oporów'])
    expect(M.cols.map((c) => c.label)).toEqual(['190 → Pętla', '4 → Oporów'])
    expect(M.cells[0][0].kind).toBe('move')
    expect(M.cells[0][0].parts).toEqual({ walk: 0.7, wait: 4, total: 4.7 })
    expect(M.cells[0][0].color).toBe(CELL_COLORS[0])
    expect(M.cells[0][1].kind).toBe('same')
    expect(M.cells[1][0].parts).toBe(null)          // no connection wait: no number at all
    expect(M.cells[1][1].kind).toBe('same')
    expect(cellColor(9)).toBe(CELL_COLORS[2])
    expect(cellColor(null)).toBe(null)
  })
  it('band, obstacles and the table rows', () => {
    expect(flat(bandText(node.sum))).toBe('17,5–31,2 min (wariant środkowy 26,2)')
    expect(bandText({})).toBe(null)
    const o = obstacleRows(node)
    expect(o.counts.signal).toBe(1)
    expect(flat(o.rows[1][1])).toContain('61 % (sygnalizacja jako 70 %), 49 %')
    expect(minText(undefined)).toBe('brak danych')
    const t = topMovementTable(node)
    expect(t.columns.map((c) => c.key)).toEqual(['to', 'walk', 'wait', 'conn', 'conn90', 'trips'])
    expect(t.rows[0].cells[5]).toEqual({ content: '56 × 50', value: 2800 })
    expect(t.rows[2].cells[3]).toBe(null)            // missing is missing, never 0
  })
})

describe('map layers', () => {
  const node = decodeNode(REC)
  it('one source, features by kind', () => {
    const fc = detailFeatures(node)
    const kinds = fc.features.map((f) => f.properties.k)
    expect(kinds).toEqual(['path', 'x', 'step', 'stop', 'stop'])
    expect(fc.features[1].properties.cls).toBe('signal')
    expect(detailFeatures(null).features).toEqual([])
  })
  it('layers: paths under the lit path, steps and crossings, stops and labels on top; W6 colours', () => {
    const specs = detailLayerSpecs()
    expect(specs.map((s) => s.id)).toEqual([LAYER_IDS.paths, LAYER_IDS.hot, LAYER_IDS.steps, LAYER_IDS.xings, LAYER_IDS.stops, LAYER_IDS.labels])
    expect(specs.every((s) => s.source === DETAIL_SOURCE)).toBe(true)
    const x = specs.find((s) => s.id === LAYER_IDS.xings)
    expect(x.paint['circle-color'][0]).toBe('match')
    expect(x.paint['circle-color']).toContain('grade')
    expect(hotFilter(3)).toEqual(['all', ['==', ['get', 'k'], 'path'], ['==', ['get', 'i'], 3]])
    expect(hotFilter(null)[2][2]).toBe(-1)
    expect(hotFilter(-1)[2][2]).toBe(-1)
  })
  it('show, light and clear on a map object', () => {
    const layers = new Map()
    const sources = new Map()
    const map = {
      getSource: (id) => sources.get(id), addSource: (id, s) => sources.set(id, { ...s, setData: vi.fn() }),
      removeSource: (id) => sources.delete(id), getLayer: (id) => layers.get(id), addLayer: (s) => layers.set(s.id, s),
      removeLayer: (id) => layers.delete(id), setFilter: vi.fn(),
    }
    showNodeDetail(map, node)
    expect(sources.get(DETAIL_SOURCE).data.features).toHaveLength(5)
    expect(layers.size).toBe(6)
    showNodeDetail(map, node)                 // again: data replaced, no duplicate layers
    expect(sources.get(DETAIL_SOURCE).setData).toHaveBeenCalledTimes(1)
    setHotPath(map, 0)
    expect(map.setFilter).toHaveBeenCalledWith(LAYER_IDS.hot, hotFilter(0))
    clearNodeDetail(map)
    expect(layers.size).toBe(0)
    expect(sources.size).toBe(0)
    expect(detailBounds(node)).toEqual([16.9001, 52.4001, 16.9005, 52.4003])
    expect(detailBounds(null)).toBe(null)
  })
})

describe('the card', () => {
  const node = decodeNode(REC)
  it('renders the sentence, the matrix, the band, obstacles and the table', () => {
    const s = flat(renderToStaticMarkup(h(NodeDetail, { node, status: 'ready', hot: 0, timetableDate: '2026-11-25' })))
    expect(s).toContain('Typowa przesiadka: 1,6 min dojścia + 7,1 min czekania')
    expect(s).toContain('nd-matrix')
    expect(s).toContain('4 → Biskupin')
    expect(s).toContain('17,5–31,2 min')
    expect(s).toContain('Wardman 1998')
    expect(s).toContain('z sygnalizacją (70 lub 50 %): 1')
    expect(s).toContain('class="hot"')
    expect(s).toContain('56 × 50')
  })
  it('loading, no record, error', () => {
    expect(renderToStaticMarkup(h(NodeDetail, { status: 'loading', name: 'X' }))).toContain('Wczytywanie')
    expect(renderToStaticMarkup(h(NodeDetail, { status: 'none', name: 'X' }))).toContain('co najmniej 20 odjazdami')
    expect(renderToStaticMarkup(h(NodeDetail, { status: 'error' }))).toContain('Nie udało się')
  })
})
