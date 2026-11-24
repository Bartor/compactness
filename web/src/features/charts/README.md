# Charts feature (`web/src/features/charts/`)

Small SVG charts for the distribution outputs of `pipeline.distribution` (`results/web/charts.json`, copied to
`public/data/charts.json` by `npm run sync`). Self-contained: nothing here imports app files, no chart library.
Dark theme through the kit's `--kit-*` variables (with fallbacks), class prefix `chx-`. Every chart has a
"Tabela / Wykres" switch (`aria-pressed`), a focusable plot (`tabIndex=0`) driven by the keyboard, and a polite
live region with the current read-out. Missing values are drawn as gaps or "brak danych", never as 0.

```js
import { loadCharts, AtLeastCurve, ReachCurve, DotStrip, Dumbbell, TimeOfDay,
  atLeastSeries, headwaySeries, reachSeries, dotStripRows, dumbbellRows, timeOfDayRows,
  layerMarks, floorOf } from './features/charts'
```

`index.js` imports `charts.css`, so importing the feature once is enough.

## Data

| Function | Returns |
|---|---|
| `loadCharts({base = './data/', fetchImpl})` | the parsed file or `null` (any failure; hide the charts then) |
| `cityIds(c)` | city ids in the fixed order Warszawa … GZM |
| `atLeastSeries(c, {aggs, domain, series})` | `[{key, label, xs, ys}]`; series `pt_am_30`, `pt_am_45`, `walk_30`, `bike_lts3_30`, `bike_lts4_30`; x = 0, 2, …, 100 |
| `headwaySeries(c, {aggs, domain})` | the same shape, x = 5, 10, 15, 20, 30 min (share with service at least every N min) |
| `reachSeries(c, {aggs, domain, mode})` | `[{key, label, xs, rom, mor, p25, p50, p75}]`, x = 5 … 60 min; mode `pt_am`, `walk`, `bike_lts3`, `bike_lts4`; not for `urban_centre` |
| `dotStripRows(c, {measure, domain})` | `{rows, median, label, unit}`; measures in `MEASURES` (`below_floor_30`, `below_floor_45`, `fgt1_30`, `rom_30`, `rom_45`, `p50_30`, `headway_le10`, `palma_30`) |
| `dumbbellRows(c, pair)` | `{rows: [{key, label, a, b}], label, aLabel, bLabel, unit}`; pairs in `PAIRS`: `30v45`, `peak_evening`, `peak_evening_floor`, `core_uc` |
| `timeOfDayRows(c, {agg, domain, measure})` | four rows (`pt_am`, `pt_midday`, `pt_evening`, `pt_saturday`) with `v30`, `v45`; measure `ratio_of_means` (default), `mean_of_ratios`, `p50`, `below_floor` |
| `layerMarks(c, layerId)` | `{series, stops}` for `transport_performance_30` (series `pt_am_30`) and `frequent_transport` (series `headway`), else `null` |
| `floorOf(c, 30 \| 45)` | the access floor (16 and 28 % with the 2026-11-25 data) |

Domains: `core` (city proper; transit only in the GTFS mask), `covered` (FUA cells in the mask), `urban_centre`
(30 and 45 min only, its own denominator: compare between cities, not with the core).

## Components and props

All five take the linking props; keys are strings.

| Component | Main props | Linking keys (`hot`, `onHot`, `pinned`, `onPin`) |
|---|---|---|
| `AtLeastCurve` | `series`, `highlight` (≤ 3 keys) or `colors` ({key: colour}), `unit` ('%' or 'min'), `marks` (class limits), `markColors`, `floor`, `what` ('kursy' for headway), `title`, `note`, `xLabel`, `height` | **classes** `c0`…`cN` of the map legend (`c0` below the first limit). Cities: `hotSeries`, `onHotSeries`, `pinnedSeries`, `onPinSeries` |
| `ReachCurve` | `series`, `focus` (city with the quartile band), `highlight` or `colors`, `title`, `note`, `height` | cities |
| `DotStrip` | `rows`, `median`, `label`, `unit`, `better` ('high' / 'low'), `selected`, `title`, `note`, `zero` | cities |
| `Dumbbell` | `rows`, `aLabel`, `bLabel`, `unit`, `selected`, `sort` (null = fixed city order, 'a', 'b', 'gap'), `title`, `note` | cities |
| `TimeOfDay` | `rows`, `unit`, `compare` (e.g. the seven-city median rows), `compareLabel`, `title`, `note`, `height` | windows `pt_am` … `pt_saturday` |

`pinned` may be a Set, an array or one key. Hover calls `onHot(key)` and `onHot(null)` on leave; click (and Enter /
Space on the focused plot) calls `onPin(key)`, which the app toggles. Lit keys (hot + pinned) stay bright and the
rest dims, as in the map legend. Keyboard: arrows move the cursor (left / right on curves and time of day, up / down
on the row charts), Home / End jump, Escape clears.

Colours: at most three cities get a category colour (`SERIES_COLORS`, validated for colour-vision deficiency and
3:1 contrast on `#1c1f26`); the rest are grey context lines. To keep one colour per city across charts, pass
`colors` from the app (e.g. selected city → `SERIES_COLORS[0]`, first pinned → `[1]`, second → `[2]`).

## Wiring into the bottom dock (for the agent building the dock)

Nothing below is done; the app files belong to the layout rework.

1. **Load once** next to the other optional files (e.g. in `App.jsx` with `loadClassShares`):
   `const [charts, setCharts] = useState(null); useEffect(() => { loadCharts().then(setCharts) }, [])`
   (`DATA_FILES` in `config.js` may get `charts: 'charts.json'`; `loadCharts({ base: DATA_BASE_URL })`). If `charts`
   is `null`, render no chart section.
2. **Shared highlight state** in the app: `hotCity`, `pinnedCities` (the dock's comparison table and the FUA outline
   on the map use the same keys, the agglomeration ids) and the legend's `hotClass` / `pinnedClasses` (`c0`…`cN`,
   the same index order as `layer.ramp.colors`).
3. **Comparison view (no city selected)**, in this order:
   - `DotStrip {...dotStripRows(charts, {measure: 'below_floor_30'})} better="low"` titled "Mieszkańcy poniżej
     minimalnego zasięgu (30 min)" with the note "Próg: połowa mediany siedmiu miast (16 %)" — the headline
     distribution figure (tier `main`);
   - `AtLeastCurve` of all seven cities for the active value layer: `series = layerMarks(charts, activeLayer)?.series
     === 'headway' ? headwaySeries(charts) : atLeastSeries(charts, {series: 'pt_am_30'})`, `marks = layerMarks(...).stops`,
     `markColors = activeLayer.ramp.colors`, `floor = floorOf(charts, 30)` for the performance layer;
     `hotSeries` / `pinnedSeries` linked to the city state, `hot` / `pinned` linked to the legend classes;
   - `Dumbbell {...dumbbellRows(charts, '30v45')}`, then `'peak_evening_floor'` and `'core_uc'` (tabs or a select);
   - `ReachCurve series={reachSeries(charts)}` with `highlight` = pinned cities.
4. **City view (a city selected)**:
   - `AtLeastCurve` with that city coloured (`colors={{[agg]: SERIES_COLORS[0]}}`) and the others grey, same marks
     and floor as above;
   - `ReachCurve series={reachSeries(charts)} focus={agg}` (the band of the city, others grey);
   - `TimeOfDay rows={timeOfDayRows(charts, {agg})}`, optionally `compare` = the median across cities of each window
     (compute in the app from `timeOfDayRows` of all cities with `median` from `scales.js`), and a second one with
     `measure: 'below_floor'`;
   - `DotStrip ... selected={agg}` with the same measure as the comparison view, so the city is placed among seven.
5. **Map link**: when the map hovers a cell, set the legend class (already done by the legend) and the charts follow
   through `hot`. When a chart sets `onHot('c3')`, use the existing class-focus path of the legend. City hover in a
   chart may outline the FUA on the map.
6. **URL** (optional): add the pinned cities and the chosen dumbbell pair to `urlState.js`.
7. A dev-only preview is `preview.html` here (`http://localhost:5173/src/features/charts/preview.html` with the dev
   server and synced data); it is not part of the build (`vite build` only bundles `web/index.html`).

## Tests

`charts.test.js` (vitest, as the rest of `web/src`): formatting, scales, selectors on a fixture, server rendering of
every component, and, when `results/web/charts.json` exists, checks on the real file (seven cities, curves start at
100 % and never rise, floor 16).
