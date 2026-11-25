// The reader's last hand-made selection of measures, kept in the browser. Local storage is shared by all projects on the
// host, so the key starts with the project's name; every access is guarded (blocked or full storage is not an error).
export const OWN_KEY = 'compactness-table-own'

const open = () => (typeof window !== 'undefined' ? window.localStorage : null)

/** The saved list of measure ids, or [] (nothing saved, bad content, or storage not available). */
export function readOwn(storage) {
  try {
    const v = JSON.parse((storage ?? open())?.getItem(OWN_KEY) || '[]')
    return Array.isArray(v) ? v.filter((x) => typeof x === 'string') : []
  } catch {
    return []
  }
}

/** Saves the list; an empty list removes the entry. */
export function writeOwn(ids, storage) {
  try {
    const s = storage ?? open()
    if (!s) return
    if (ids.length) s.setItem(OWN_KEY, JSON.stringify(ids))
    else s.removeItem(OWN_KEY)
  } catch {
    // storage blocked: the table works, it only does not remember
  }
}
