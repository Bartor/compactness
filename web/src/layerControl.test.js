import { describe, expect, it } from 'vitest'
import {
  activeIds, chipLabel, chooseOverlay, initialState, overlayGroups, revealLayer, setOverlayOn, setValue, setVariant,
  stateFromIds, valueLayers, variantOf, variantsToWrite,
} from './layerControl'
import { hashOf, hashOfView, readHash, resolveHash } from './urlState'

const L = (id, kind, extra = {}) => ({ id, kind, status: 'ready', title: id, ...extra })
const layers = [
  L('fua', 'boundary'), L('a', 'choropleth'), L('b', 'choropleth'), L('m', 'mask'),
  L('p', 'points', { title: 'Przesiadki: dojście' }), L('q', 'points', { title: 'Przesiadki: czekanie' }),
  L('plan', 'choropleth', { status: 'planned' }), L('x', 'surprise'),
]
const ids = (s) => [...s].sort()

describe('layer control state', () => {
  it('starts with outlines only', () => {
    expect(ids(activeIds(initialState(layers), layers))).toEqual(['fua'])
    expect(initialState(layers).value).toBeNull()
  })
  it('groups overlays by catalog kind, skipping value layers, planned layers and kinds it does not know', () => {
    expect(overlayGroups(layers).map((g) => [g.kind, g.layers.map((l) => l.id)])).toEqual([
      ['boundary', ['fua']], ['points', ['p', 'q']],   // the mask (hatch) is not a switch any more: the layers draw their own hatch
    ])
    expect(valueLayers(layers).map((l) => l.id)).toEqual(['a', 'b'])
  })
  it('one value layer at a time; overlays combine with any of them', () => {
    let s = setValue(initialState(layers), 'a', layers)
    s = setOverlayOn(s, 'points', true)
    expect(ids(activeIds(s, layers))).toEqual(['a', 'fua', 'p'])
    s = setValue(s, 'b', layers)
    expect(ids(activeIds(s, layers))).toEqual(['b', 'fua', 'p'])
    s = setValue(s, null, layers)
    expect(ids(activeIds(s, layers))).toEqual(['fua', 'p'])
  })
  it('a group draws one of its layers: choosing another replaces it', () => {
    let s = setOverlayOn(initialState(layers), 'points', true)
    s = chooseOverlay(s, 'points', 'q', layers)
    expect(ids(activeIds(s, layers))).toEqual(['fua', 'q'])
    expect(ids(activeIds(setOverlayOn(s, 'points', false), layers))).toEqual(['fua'])
    // the choice survives switching the group off and on
    expect(ids(activeIds(setOverlayOn(setOverlayOn(s, 'points', false), 'points', true), layers))).toEqual(['fua', 'q'])
  })
  it('ignores ids that are not there and returns the same state when nothing changes', () => {
    const s = initialState(layers)
    expect(setValue(s, 'zzz', layers)).toBe(s)
    expect(setValue(s, 'plan', layers)).toBe(s)
    expect(setValue(s, null, layers)).toBe(s)
    expect(chooseOverlay(s, 'points', 'a', layers)).toBe(s)
    expect(setOverlayOn(s, 'nope', true)).toBe(s)
    expect(revealLayer(s, layers, 'x')).toBe(s)
  })
  it('"na mapie" reveals a value layer or switches an overlay on', () => {
    let s = revealLayer(initialState(layers), layers, 'a')
    expect(s.value).toBe('a')
    s = revealLayer(s, layers, 'q')
    expect(ids(activeIds(s, layers))).toEqual(['a', 'fua', 'q'])
    expect(revealLayer(s, layers, 'plan')).toBe(s)
  })
  it('a catalog without some kinds still works', () => {
    const only = [L('a', 'choropleth')]
    expect(overlayGroups(only)).toEqual([])
    expect(ids(activeIds(initialState(only), only))).toEqual([])
    expect(initialState([]).overlays).toEqual({})
  })
  it('keeps the chosen variant of a layer that has some, and drops one it does not offer', () => {
    const lines = L('v', 'points', { variants: [{ key: 'am', label: 'rano' }, { key: 'pm', label: 'popołudnie' }] })
    const ls = [L('fua', 'boundary'), lines]
    let s = setOverlayOn(initialState(ls), 'points', true)
    expect(variantOf(s, lines)).toBe('am')
    s = setVariant(s, lines, 'pm')
    expect(variantOf(s, lines)).toBe('pm')
    expect(setVariant(s, lines, 'zzz')).toBe(s)
    expect(variantsToWrite(s, ls, activeIds(s, ls))).toEqual({ v: 'pm' })
    expect(variantsToWrite(initialState(ls), ls, new Set(['v']))).toEqual({})
  })
  it('labels a chooser entry by the part of the title after the colon', () => {
    expect(chipLabel({ title: 'Przesiadki: dojście' })).toBe('dojście')
    expect(chipLabel({ title: 'Bez dwukropka' })).toBe('Bez dwukropka')
    expect(chipLabel({ title: 'A: b', chip: 'x' })).toBe('x')
  })
})

describe('address <-> layer state', () => {
  const catalog = { agglomerations: [{ id: 'lodz' }], layers }
  const round = (state, agg = null) => {
    const h = hashOfView(agg, state, layers)
    const r = resolveHash(readHash(h), catalog)
    return { h, r }
  }
  it('writes nothing for the default view', () => {
    expect(hashOfView(null, initialState(layers), layers)).toBe('')
  })
  it('round-trips value layer, overlays, chosen points layer and city', () => {
    let s = setValue(initialState(layers), 'b', layers)
    s = chooseOverlay(setOverlayOn(s, 'points', true), 'points', 'q', layers)
    s = setOverlayOn(s, 'mask', true)   // no such group: nothing happens
    const { h, r } = round(s, 'lodz')
    expect(h).toBe('#a=lodz&l=b,fua,q')
    expect(r.agg).toBe('lodz')
    expect(ids(activeIds(r.state, layers))).toEqual(['b', 'fua', 'q'])
    expect(r.state.value).toBe('b')
    expect(r.state.overlays.points).toMatchObject({ on: true, layer: 'q' })
  })
  it('round-trips outlines off and no layers at all', () => {
    const off = setOverlayOn(initialState(layers), 'boundary', false)
    expect(round(off).h).toBe('#l=')
    expect(ids(activeIds(round(off).r.state, layers))).toEqual([])
  })
  it('round-trips a variant', () => {
    const lines = L('v', 'points', { variants: [{ key: 'am' }, { key: 'pm' }] })
    const ls = [L('fua', 'boundary'), lines]
    const s = setVariant(setOverlayOn(initialState(ls), 'points', true), lines, 'pm')
    const h = hashOfView(null, s, ls)
    expect(h).toBe('#l=fua,v&v=v:pm')
    const back = resolveHash(readHash(h), { agglomerations: [], layers: ls })
    expect(variantOf(back.state, lines)).toBe('pm')
    expect(hashOf({ agg: null, layers: ['fua'] }, { layers: ['fua'] })).toBe('')
  })
  it('old addresses with several value layers or several points layers keep the first of each', () => {
    const s = stateFromIds(['b', 'fua', 'a', 'q', 'p', 'm'], layers)   // an old address naming the mask layer: ignored
    expect(ids(activeIds(s, layers))).toEqual(['b', 'fua', 'q'])
    expect(resolveHash({ layers: ['p', 'q', 'a', 'b'] }, catalog).state.value).toBe('a')
  })
  it('unknown, planned and unlisted-kind ids are dropped; no l= means the default', () => {
    expect(ids(activeIds(stateFromIds(['plan', 'x', 'nope', 'a'], layers), layers))).toEqual(['a'])
    expect(ids(activeIds(resolveHash({}, catalog).state, layers))).toEqual(['fua'])
  })
})
