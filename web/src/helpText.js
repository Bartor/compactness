// Short forms of long texts, for the one help pattern ("?": a sentence, the direction, a link to more).

/** The first sentence of a text (up to `max` characters, cut at a word with an ellipsis when it is longer). */
export function firstSentence(text, max = 230) {
  const t = String(text ?? '').replace(/\s+/g, ' ').trim()
  if (!t) return ''
  const m = /^(.+?[.!?…])(?:\s+[A-ZĄĆĘŁŃÓŚŹŻ„"(]|$)/.exec(t)
  const s = m ? m[1] : t
  if (s.length <= max) return s
  const cut = s.slice(0, max)
  return `${cut.slice(0, Math.max(cut.lastIndexOf(' '), 40))}…`
}
