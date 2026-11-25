// Map helpers of the selection: the hover tooltip's DOM and keeping a selection in view next to the panel.

/** DOM of the tooltip from segText.tipModel (no innerHTML: names come from data). */
export function renderLineTip(model, doc = document) {
  const root = doc.createElement('div')
  const b = doc.createElement('b')
  b.textContent = model.title
  root.appendChild(b)
  for (const t of model.lines) {
    const s = doc.createElement('span')
    s.textContent = t
    root.appendChild(s)
  }
  const em = doc.createElement('em')
  em.textContent = 'kliknij, by zaznaczyć'
  root.appendChild(em)
  return root
}

const M = 16

/**
 * The part of the map box (px, relative to it) not covered by the panel: left of a panel on the right, above a sheet
 * at the bottom; the bottom strip with the attribution is left out. `cont` and `panel` are DOMRects.
 */
export function freeArea(cont, panel, legend = null) {
  const area = { left: M, top: M, right: cont.width - M, bottom: cont.height - M - 24 }
  if (panel && panel.width > 0 && panel.height > 0) {
    const left = panel.left - cont.left
    const top = panel.top - cont.top
    if (left > cont.width * 0.35) area.right = Math.min(area.right, left - M)
    else if (top > cont.height * 0.2) area.bottom = Math.min(area.bottom, top - M)
  }
  if (legend && legend.width > 0) {
    const r = legend.right - cont.left + M
    if (area.right - r >= 220) area.left = Math.max(area.left, r)
  }
  return area
}

/** How far to pan (px) so that box (px) lies in area; null when it is too large to fit at this zoom. */
export function panToShow(box, area) {
  if (box.right - box.left > area.right - area.left || box.bottom - box.top > area.bottom - area.top) return null
  const dx = box.left < area.left ? box.left - area.left : box.right > area.right ? box.right - area.right : 0
  const dy = box.top < area.top ? box.top - area.top : box.bottom > area.bottom ? box.bottom - area.bottom : 0
  return [dx, dy]
}

/** Moves the map as little as needed so that bounds [w, s, e, n] are visible beside the panel element. */
export function ensureVisible(map, bounds, panelEl) {
  const cont = map.getContainer().getBoundingClientRect()
  const legend = map.getContainer().parentElement?.querySelector('.kit-map-legend')?.getBoundingClientRect() || null
  const area = freeArea(cont, panelEl?.getBoundingClientRect() || null, legend)
  const a = map.project([bounds[0], bounds[3]])
  const b = map.project([bounds[2], bounds[1]])
  const box = { left: Math.min(a.x, b.x), right: Math.max(a.x, b.x), top: Math.min(a.y, b.y), bottom: Math.max(a.y, b.y) }
  const d = panToShow(box, area)
  if (d) {
    if (Math.abs(d[0]) >= 1 || Math.abs(d[1]) >= 1) map.panBy([Math.round(d[0]), Math.round(d[1])], { duration: 400 })
    return
  }
  map.fitBounds([[bounds[0], bounds[1]], [bounds[2], bounds[3]]], {
    padding: { left: area.left, top: area.top, right: cont.width - area.right, bottom: cont.height - area.bottom },
    maxZoom: Math.max(map.getZoom(), 13), duration: 500,
  })
}
