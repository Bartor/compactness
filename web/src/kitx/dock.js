// The state of a bottom dock: pure functions, no React. A dock is folded (a thin bar), half (about 46 % of the
// stage) or full (the whole stage).

export const DOCK_STATES = ['folded', 'half', 'full']
export const DEFAULT_DOCK = 'half'
export const FOLDED_PX = 44
export const HALF_RATIO = 0.46

/** A state from text (an address, say), or undefined for anything else. */
export const parseDock = (text) => (DOCK_STATES.includes(text) ? text : undefined)

/** The height of a state in px for a stage `stageH` px tall. */
export function dockHeight(state, stageH) {
  if (state === 'folded') return FOLDED_PX
  if (state === 'full') return stageH
  return Math.round(stageH * HALF_RATIO)
}

/** The state a dragged dock of `height` px settles in: the nearest of the three, by height. */
export function snapDock(height, stageH) {
  const heights = DOCK_STATES.map((s) => [s, dockHeight(s, stageH)])
  return heights.reduce((best, cur) => (Math.abs(cur[1] - height) < Math.abs(best[1] - height) ? cur : best))[0]
}

/** The state one step towards `dir` (-1: smaller, +1: larger), staying within the three. */
export function stepDock(state, dir) {
  const i = DOCK_STATES.indexOf(state)
  return DOCK_STATES[Math.min(DOCK_STATES.length - 1, Math.max(0, (i < 0 ? 1 : i) + dir))]
}

/** Whether a move from state `a` to `b` needs the map fitted again: any change (in full the map is a small inset). */
export const refitOnChange = (a, b) => a !== b
