// Names as the data has them, except that a name written entirely in capitals is shown in title case ("DWORZEC GŁÓWNY"
// -> "Dworzec Główny"); mixed-case names are left alone.

/** True when the text has letters and no lower-case letter. */
export const isAllCaps = (s) => /\p{L}/u.test(s) && s === s.toUpperCase() && s !== s.toLowerCase()

/** Title case for an ALL CAPS name; any other name is returned as it is. Short words like "im." and "w" stay lower-case. */
export function titleCase(name) {
  const s = String(name ?? '')
  if (!isAllCaps(s)) return s
  return s.toLowerCase().replace(/(^|[\s(\-–/])(\p{L})/gu, (_, sep, ch) => sep + ch.toUpperCase())
}
