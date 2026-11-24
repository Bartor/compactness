import { describe, expect, it } from 'vitest'
import { EMPTY_FOCUS, clearPinned, emphasised, hoverClass, hovered, pruneFocus, togglePinned } from './classFocus'
import { classIndex, focusOpacity } from './ramp'

describe('class focus (hover and pin)', () => {
  it('hover sets and clears the hovered class without touching the pins', () => {
    let f = togglePinned(EMPTY_FOCUS, 'a', 2)
    f = hoverClass(f, 'a', 0)
    expect(f).toEqual({ layerId: 'a', hover: 0, from: 'legend', pinned: [2] })
    expect([...emphasised(f, 'a')].sort()).toEqual([0, 2])
    f = hoverClass(f, 'a', null)
    expect(f).toEqual({ layerId: 'a', hover: null, from: null, pinned: [2] })
  })

  it('pointing at the map marks the legend row but does not fade the map', () => {
    let f = hoverClass(EMPTY_FOCUS, 'a', 1, 'map')
    expect(hovered(f, 'a')).toBe(1)
    expect(emphasised(f, 'a').size).toBe(0)
    f = togglePinned(f, 'a', 3)
    expect([...emphasised(f, 'a')]).toEqual([3])
    expect(hovered(f, 'b')).toBe(null)
    expect([...emphasised(hoverClass(f, 'a', 1, 'legend'), 'a')].sort()).toEqual([1, 3])
  })

  it('returns the same object when nothing changes', () => {
    const f = hoverClass(EMPTY_FOCUS, 'a', 1)
    expect(hoverClass(f, 'a', 1)).toBe(f)
    expect(hoverClass(EMPTY_FOCUS, null, null)).toBe(EMPTY_FOCUS)
    expect(hoverClass(f, 'b', null)).toBe(f)
    expect(clearPinned(f, 'a')).toBe(f)
    expect(pruneFocus(f, new Set(['a']))).toBe(f)
  })

  it('a click pins a class, a second click unpins it, several can be pinned', () => {
    let f = togglePinned(EMPTY_FOCUS, 'a', 3)
    f = togglePinned(f, 'a', 1)
    expect(f.pinned).toEqual([1, 3])
    f = togglePinned(f, 'a', 3)
    expect(f.pinned).toEqual([1])
    expect(clearPinned(f, 'a').pinned).toEqual([])
  })

  it('another layer starts from scratch and a hidden layer loses its focus', () => {
    const f = togglePinned(EMPTY_FOCUS, 'a', 1)
    expect(hoverClass(f, 'b', 0)).toEqual({ layerId: 'b', hover: 0, from: 'legend', pinned: [] })
    expect(togglePinned(f, 'b', 4)).toEqual({ layerId: 'b', hover: null, from: null, pinned: [4] })
    expect(emphasised(f, 'b').size).toBe(0)
    expect(pruneFocus(f, new Set(['b']))).toBe(EMPTY_FOCUS)
  })
})

describe('ramp classes under focus', () => {
  const ramp = { stops: [10, 20], colors: ['#a', '#b', '#c'] }       // one colour more than stops
  const codes = { stops: [1, 2, 3, 4], colors: ['#0', '#1', '#2', '#3', '#4'] }

  it('classIndex follows the ramp bounds', () => {
    expect([5, 10, 19.9, 20, 99].map((v) => classIndex(ramp, v))).toEqual([0, 1, 1, 2, 2])
    expect([0, 1, 2, 3, 4].map((v) => classIndex(codes, v))).toEqual([0, 1, 2, 3, 4])
  })

  it('focusOpacity is plain without emphasis and a step expression with it', () => {
    expect(focusOpacity('v', ramp, new Set(), 0.8)).toBe(0.8)
    expect(focusOpacity('v', ramp, new Set([1]), 0.8, 0.1)).toEqual(['step', ['get', 'v'], 0.1, 10, 0.8, 20, 0.1])
    expect(focusOpacity('v', codes, new Set([0, 4]), 0.9, 0.1))
      .toEqual(['step', ['get', 'v'], 0.9, 1, 0.1, 2, 0.1, 3, 0.1, 4, 0.9])
  })
})
