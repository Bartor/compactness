import { describe, expect, it } from 'vitest'
import {
  EMPTY_FOCUS, EMPTY_FOCUSES, clearPinned, emphasised, focusOf, hoverClass, hoverOnMap, hovered, leaveMap,
  pruneFocuses, togglePinned, updateFocus,
} from './classFocus'
import { legendRows } from './layerInfo'
import { KIND_ORDER } from './mapLayers'
import { oneOfEachGroup, toggleLayer } from './layerState'
import { resolveHash } from './urlState'

describe('focus of several layers at once', () => {
  it('keeps one focus per layer, so a value layer and a points layer can both be pinned', () => {
    let all = updateFocus(EMPTY_FOCUSES, 'grid', (f) => togglePinned(f, 'grid', 2))
    all = updateFocus(all, 'pts', (f) => togglePinned(f, 'pts', 0))
    expect(Object.keys(all).sort()).toEqual(['grid', 'pts'])
    expect([...emphasised(focusOf(all, 'grid'), 'grid')]).toEqual([2])
    expect([...emphasised(focusOf(all, 'pts'), 'pts')]).toEqual([0])
    // hovering the points legend does not disturb the grid pin
    all = updateFocus(all, 'pts', (f) => hoverClass(f, 'pts', 3))
    expect([...emphasised(focusOf(all, 'pts'), 'pts')].sort()).toEqual([0, 3])
    expect(focusOf(all, 'grid').pinned).toEqual([2])
  })
  it('an unpinned and unhovered layer leaves the map; nothing changing returns the same object', () => {
    let all = updateFocus(EMPTY_FOCUSES, 'a', (f) => togglePinned(f, 'a', 1))
    expect(updateFocus(all, 'a', (f) => hoverClass(f, 'a', null))).toBe(all)
    all = updateFocus(all, 'a', (f) => togglePinned(f, 'a', 1))
    expect(all).toEqual({})
    expect(updateFocus(all, 'a', (f) => clearPinned(f, 'a'))).toBe(all)
    expect(focusOf(all, 'a')).toBe(EMPTY_FOCUS)
  })
  it('the pointer on the map marks a row in each layer under it, without fading, and clears the rest', () => {
    let all = hoverOnMap(EMPTY_FOCUSES, ['grid', 'pts'], { grid: 1, pts: 4 })
    expect(hovered(focusOf(all, 'grid'), 'grid')).toBe(1)
    expect(hovered(focusOf(all, 'pts'), 'pts')).toBe(4)
    expect(emphasised(focusOf(all, 'pts'), 'pts').size).toBe(0)
    all = hoverOnMap(all, ['grid', 'pts'], { grid: 1 })
    expect(focusOf(all, 'pts')).toBe(EMPTY_FOCUS)
    expect(hoverOnMap(all, ['grid', 'pts'], { grid: 1 })).toBe(all)
    expect(leaveMap(all)).toEqual({})
  })
  it('leaving the map keeps pins', () => {
    let all = updateFocus(EMPTY_FOCUSES, 'pts', (f) => togglePinned(f, 'pts', 2))
    all = hoverOnMap(all, ['pts'], { pts: 0 })
    all = leaveMap(all)
    expect(all.pts).toEqual({ layerId: 'pts', hover: null, from: null, pinned: [2] })
  })
  it('a hidden layer loses its focus, a visible one keeps it', () => {
    let all = updateFocus(EMPTY_FOCUSES, 'a', (f) => togglePinned(f, 'a', 1))
    all = updateFocus(all, 'b', (f) => togglePinned(f, 'b', 0))
    const kept = pruneFocuses(all, new Set(['a', 'x']))
    expect(Object.keys(kept)).toEqual(['a'])
    expect(pruneFocuses(kept, new Set(['a']))).toBe(kept)
  })
})

describe('layer switches with point layers', () => {
  const layers = [
    { id: 'fua', kind: 'boundary' }, { id: 'a', kind: 'choropleth' }, { id: 'b', kind: 'choropleth' },
    { id: 'p', kind: 'points' }, { id: 'q', kind: 'points' }, { id: 'm', kind: 'mask' },
  ]
  it('turning a points layer on turns the other points layer off, not the value layer', () => {
    const on = toggleLayer(new Set(['fua', 'a', 'p']), 'q', true, layers)
    expect([...on].sort()).toEqual(['a', 'fua', 'q'])
  })
  it('turning a value layer on leaves the points layer alone, and the other way round', () => {
    expect([...toggleLayer(new Set(['a', 'p']), 'b', true, layers)].sort()).toEqual(['b', 'p'])
    expect([...toggleLayer(new Set(['a']), 'p', true, layers)].sort()).toEqual(['a', 'p'])
    expect([...toggleLayer(new Set(['a', 'p']), 'p', false, layers)]).toEqual(['a'])
  })
  it('an address keeps the first of each group', () => {
    expect(oneOfEachGroup(['q', 'a', 'p', 'b', 'fua'], layers)).toEqual(['q', 'a', 'fua'])
    const catalog = { agglomerations: [], layers: layers.map((l) => ({ ...l, status: 'ready' })) }
    expect(resolveHash({ layers: ['p', 'q', 'a', 'b'] }, catalog, []).layers).toEqual(['p', 'a'])
  })
  it('legend rows of a points layer carry the no-value label', () => {
    const l = { kind: 'points', ramp: { stops: [1], colors: ['#0', '#1'] }, has_nodata: true, nodata_label: 'x', novalue_label: 'y' }
    expect(legendRows(l)).toMatchObject({ noData: 'x', noValue: 'y' })
    expect(legendRows({ ...l, novalue_label: undefined }).noValue).toBeNull()
  })
  it('a points layer is drawn between the grid layers and the outlines', () => {
    expect(KIND_ORDER.choropleth).toBeLessThan(KIND_ORDER.mask)
    expect(KIND_ORDER.mask).toBeLessThan(KIND_ORDER.points)
    expect(KIND_ORDER.points).toBeLessThan(KIND_ORDER.boundary)
  })
})
