import { describe, expect, it } from 'vitest'
import { anchorRects, placePopup } from './nodePopup'

const area = { left: 12, top: 12, right: 1012, bottom: 400 }
const size = { w: 330, h: 300 }
const within = (r) => r.left >= area.left && r.right <= area.right && r.top >= area.top && r.bottom <= area.bottom

describe('placePopup', () => {
  it('opens below the point when there is room', () => {
    const p = placePopup({ point: { x: 500, y: 50 }, size, area })
    expect(p.anchor).toBe('top')
    expect(p.pan).toEqual([0, 0])
  })
  it('opens above when the room below is short', () => {
    const p = placePopup({ point: { x: 500, y: 380 }, size, area })
    expect(p.anchor).toBe('bottom')
    expect(within(p.rect)).toBe(true)
  })
  it('uses a corner anchor near the left and right edges', () => {
    expect(placePopup({ point: { x: 20, y: 50 }, size, area }).anchor).toBe('top-left')
    expect(placePopup({ point: { x: 1000, y: 50 }, size, area }).anchor).toBe('top-right')
    expect(placePopup({ point: { x: 20, y: 390 }, size, area }).anchor).toBe('bottom-left')
    expect(placePopup({ point: { x: 1000, y: 390 }, size, area }).anchor).toBe('bottom-right')
  })
  it('keeps clear of the legend when another anchor fits, and uses it when none does', () => {
    const legend = { left: 12, top: 250, right: 200, bottom: 388 }
    const a = placePopup({ point: { x: 100, y: 300 }, size: { w: 330, h: 200 }, area, avoid: [legend] })
    expect(a.anchor).not.toBe('top')   // below would lie on the legend
    expect(within(a.rect)).toBe(true)
    const wide = { left: 12, top: 12, right: 1012, bottom: 400 }
    const b = placePopup({ point: { x: 500, y: 200 }, size, area, avoid: [wide] })
    expect(within(b.rect)).toBe(true)   // nothing clear: the legend is ignored rather than the edge
  })
  it('pans by the smallest shift when no anchor fits', () => {
    const small = { left: 12, top: 12, right: 1012, bottom: 300 }
    const tall = { w: 330, h: 280 }
    const p = placePopup({ point: { x: 500, y: 60 }, size: tall, area: small })
    expect(p.pan[0]).toBe(0)
    expect(p.pan[1]).toBe(46)   // a corner anchor, 66..346 against 300
    const r = anchorRects({ x: 500, y: 60 }, tall)[p.anchor]
    expect(r.bottom - p.pan[1]).toBeLessThanOrEqual(small.bottom)
  })
  it('aligns a popup larger than the area to its top left corner', () => {
    const p = placePopup({ point: { x: 500, y: 200 }, size: { w: 330, h: 600 }, area })
    const r = anchorRects({ x: 500, y: 200 }, { w: 330, h: 600 })[p.anchor]
    expect(r.top - p.pan[1]).toBe(area.top)
  })
})
