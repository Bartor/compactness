// File names of exports: zwartosc-miast_<view>_<subject>_<area>_<yyyy-mm-dd>.<ext>, ASCII only.

const FROM = 'ąćęłńóśźżĄĆĘŁŃÓŚŹŻ'
const TO = 'acelnoszzACELNOSZZ'

/** Lower-case ASCII with single hyphens: "Wrocław, rdzeń" -> "wroclaw-rdzen". */
export function slug(text) {
  return String(text ?? '')
    .replace(/[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]/g, (c) => TO[FROM.indexOf(c)])
    .normalize('NFD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')
}

/** yyyy-mm-dd of a Date in local time. */
export const isoDate = (d = new Date()) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

/**
 * `view` what is exported ("porownanie", "miasto", "miara", "wykres"), `subject` the city, metric or chart, `area` the
 * area id; empty parts are left out, so the name never has doubled underscores.
 */
export function exportFilename({ view, subject, area, ext = 'csv', date = isoDate() }) {
  const parts = ['zwartosc-miast', slug(view), slug(subject), slug(area), date].filter(Boolean)
  return `${parts.join('_')}.${ext}`
}
