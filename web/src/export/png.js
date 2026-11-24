// A chart's SVG as a PNG: the SVG is cloned with the computed styles written into it (the page's CSS and its custom
// properties do not exist inside an image), drawn on a canvas at twice the size over the page's own dark background, and
// a header with the chart's title and a footer with the area, the project, the data date and the short source are
// drawn under and over it. No library. The pure parts (text, sizes, support check) are tested; the rest needs a DOM.

export const SCALE = 2
export const PAD = 16
export const APP_NAME = 'Zwartość miast'

/** The style properties copied from the computed style into each SVG element. */
export const STYLE_PROPS = [
  'fill', 'fill-opacity', 'stroke', 'stroke-width', 'stroke-opacity', 'stroke-dasharray', 'stroke-linecap', 'stroke-linejoin',
  'opacity', 'font-family', 'font-size', 'font-weight', 'font-style', 'letter-spacing', 'text-anchor', 'dominant-baseline',
  'text-decoration', 'visibility', 'display', 'paint-order', 'shape-rendering',
]

/** Lines under the chart: what it is, whose and when. */
export function footerLines({ title, area, date, source }) {
  const first = [title, area].filter(Boolean).join(' · ')
  const second = [APP_NAME, date ? `dane z dnia ${date}` : null, source].filter(Boolean).join(' · ')
  return [first, second]
}

/** Words wrapped to lines of at most `max` characters (a longer word stays whole). */
export function wrapWords(text, max) {
  const lines = []
  let line = ''
  for (const w of String(text).split(/\s+/).filter(Boolean)) {
    if (line && `${line} ${w}`.length > max) { lines.push(line); line = w } else line = line ? `${line} ${w}` : w
  }
  if (line) lines.push(line)
  return lines
}

/** The pixel sizes of the picture for an SVG of w x h CSS px and `lines` text lines in the footer. */
export function pictureSize(w, h, { headerH = 30, lineH = 18, lines = 2, scale = SCALE, pad = PAD } = {}) {
  const width = Math.round((w + 2 * pad) * scale)
  const height = Math.round((h + headerH + lines * lineH + 3 * pad) * scale)
  return { width, height, cssW: w + 2 * pad, cssH: h + headerH + lines * lineH + 3 * pad }
}

/** Whether to offer PNG: a browser with canvas and blobs, and not Safari, where SVG drawn to a canvas has not been verified. */
export function pngSupported(nav = typeof navigator !== 'undefined' ? navigator : null, doc = typeof document !== 'undefined' ? document : null) {
  if (!nav || !doc || typeof Image === 'undefined') return false
  const ua = nav.userAgent || ''
  const safari = /safari/i.test(ua) && !/chrome|chromium|crios|fxios|edg|android/i.test(ua)
  if (safari) return false
  try {
    const c = doc.createElement('canvas')
    return !!(c.getContext && c.toBlob)
  } catch {
    return false
  }
}

function inlineStyles(source, clone) {
  const from = [source, ...source.querySelectorAll('*')]
  const to = [clone, ...clone.querySelectorAll('*')]
  from.forEach((el, i) => {
    const cs = getComputedStyle(el)
    let css = ''
    for (const p of STYLE_PROPS) {
      let v = cs.getPropertyValue(p)
      if (!v) continue
      if (p === 'font-family') v = `${v}, system-ui, sans-serif`
      css += `${p}:${v};`
    }
    to[i].setAttribute('style', css)
    to[i].removeAttribute('class')
    to[i].removeAttribute('tabindex')
  })
}

function backgroundOf(el) {
  for (let e = el; e; e = e.parentElement) {
    const c = getComputedStyle(e).backgroundColor
    if (c && c !== 'transparent' && !/rgba\(\s*0,\s*0,\s*0,\s*0\s*\)/.test(c)) return c
  }
  return getComputedStyle(document.body).backgroundColor || '#1c1f26'
}

const loadImage = (url) => new Promise((resolve, reject) => {
  const img = new Image()
  img.onload = () => resolve(img)
  img.onerror = () => reject(new Error('Nie udało się narysować wykresu'))
  img.src = url
})

/** The PNG (a Blob) of an SVG element with its header and footer. `info` is {title, area, date, source}. */
export async function svgToPngBlob(svg, info, scale = SCALE) {
  if (document.fonts?.ready) await document.fonts.ready
  const box = svg.getBoundingClientRect()
  const w = Math.round(box.width)
  const h = Math.round(box.height)
  const clone = svg.cloneNode(true)
  clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  clone.setAttribute('width', String(w))
  clone.setAttribute('height', String(h))
  inlineStyles(svg, clone)
  const img = await loadImage(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(new XMLSerializer().serializeToString(clone))}`)

  const bg = backgroundOf(svg)
  const ink = getComputedStyle(document.body).color || '#e7e9ee'
  const family = `${getComputedStyle(svg).fontFamily || ''}, system-ui, sans-serif`
  const probe = document.createElement('canvas').getContext('2d')
  probe.font = `12px ${family}`
  const maxChars = Math.max(30, Math.floor((w + PAD) / 6.4))
  const lines = footerLines(info).flatMap((l) => wrapWords(l, maxChars))
  const size = pictureSize(w, h, { lines: lines.length, scale })
  const canvas = document.createElement('canvas')
  canvas.width = size.width
  canvas.height = size.height
  const g = canvas.getContext('2d')
  g.scale(scale, scale)
  g.fillStyle = bg
  g.fillRect(0, 0, size.cssW, size.cssH)
  g.fillStyle = ink
  g.textBaseline = 'alphabetic'
  g.font = `600 15px ${family}`
  g.fillText(info.title || '', PAD, PAD + 16)
  g.drawImage(img, PAD, PAD + 30, w, h)
  g.globalAlpha = 0.7
  g.font = `12px ${family}`
  lines.forEach((l, i) => g.fillText(l, PAD, PAD + 30 + h + PAD + 12 + i * 18))
  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error('Nie udało się zapisać obrazu'))), 'image/png'))
}
