# Selection of speed segments, right panel and what-if (`features/segments`)

Data: `pipeline/speed_segments_web.py` -> `results/web/speed/segments/` (`trams.geojson`: one feature per tram segment
between two consecutive stop places and direction, the map file of `speed_tram`; `<agg>.json`: per-city detail loaded
when a selection opens; catalog `detail_url_template`). Buses keep stretches and rail keeps lines on the map (stop-to-stop
bus files measured at 1.4-6.0 MB per city, GZM over the 5 MB cap); a selection of those works from their map properties
only (no model). Every time and speed is scheduled ("z rozkładu"), never measured.

| File | What |
|---|---|
| `segModel.js` | pure: free-running model (same as `tram_stretches.free_time` / `cap_kmh`), `parseDetail`, selection ops (`toggleId`, `stretchIds`, `patternIds`, `linesAt`), `structure` (chains / pieces), `summary` (time, speed, +-1 min per piece, trips, lines, time above free running with its range, OSM sums, band strip), `savings` / `whatIf` (rule of `pipeline/whatif_tram.py`: no segment below its free-running time, never slower), `featureSummary` (bus / rail), address `parseSel` / `selText` |
| `segText.js` | Polish numbers and words, the hover tooltip model |
| `segMap.js` | tooltip DOM, `ensureVisible` (pan / fit so the selection stays clear of the panel or the phone sheet) |
| `segData.js` | loaders (one fetch per url), `useLoaded` |
| `SegmentPanel.jsx` | the panel (kit `DetailsPanel`): desktop a 380 px column over the map's right edge, phone the kit's bottom sheet (portal to the body, above the city sheet) |
| `useSegmentSelection.jsx` | the hook the page wires: state, data, map filters, panel element, address text |
| `segments.css`, `segments.test.js` | styles; tests (`npm --prefix web test`) |

## Wiring (done)

- `App.jsx`: `const segs = useSegmentSelection({layers: mapCatalog.layers, active, selectedId, band, onBand, initial: start.sel, resolve, cityName})`;
  MapView gets `lineSel={segs.lineSel} onLinePick={segs.onLinePick} side={segs.panel} selBounds={segs.bounds} selN={segs.n}`
  and `inset` / `onInset` (the small map beside a full panel: a click brings the large map back, no popup, no selection);
  the hash gets `sel: segs.text`. On a phone a selection folds the city sheet.
- `urlState.js`: `sg=<mode>:<id>,<id>` (mode tram | bus | rail; tram ids `<CITY>-<5 hex>`, stable while the stop places stay).
- `features/speed/lineLayers.js`: layer `<layer>:sel` (white casing) under the hover highlight; `applyLines(..., {sel})`.
- `MapView.jsx`: a click on a speed feature calls `onLinePick` (the stretch popup is no longer opened when it is wired);
  hover shows one tooltip (`seg-tip-pop`) and hides the cell tooltip.
