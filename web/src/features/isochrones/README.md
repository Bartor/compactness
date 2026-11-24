# Isochrones: the "skąd dojadę" mode

Self-contained feature: data loading, nearest-origin lookup, MapLibre layers and a card. Nothing outside this folder
uses it yet; the wiring below is for whoever adds it to `App.jsx` / `MapView.jsx`.

## Data

- Produced by `python -m pipeline.isochrones origins|route|build` into `results/web/isochrones/<agg>.json`
  (one file per agglomeration, compact JSON) plus `_meta.json`. QA: `results/qa/isochrones/isochrones.md`.
- **The sync script does not copy it yet.** `web/scripts/sync-data.mjs` copies only the top-level files of
  `results/web/`. It needs the subfolder copied to `public/data/isochrones/` (see
  `data/interim/proposals/isochrones.md`). The loader asks for `data/isochrones/<agg>.json` and treats a missing
  file as "this city has no isochrones", so the site keeps working without it.
- File shape (all keys sorted):
  - `origins`: `[{id, kind, name, lon, lat}]`, kind = `hub` | `centre` | `stop_area` | `grid`; hubs and centres first.
  - `scenarios`: `{am, evening, walk}` with `label` and `minutes` (`[15, 30, 45, 60]`, walk `[15, 30]`).
  - `iso[originId][scenario]`: `residents` (cumulative, per band in `minutes` order), `residents_band` (inside the
    band only), `geom` (per band: `[[outerRing, hole, ...], ...]`, each ring a Google encoded polyline at 5 decimals,
    lat first). Polygons are cumulative: "do 30 min" contains "do 15 min".
  - `day`, `note`, `lattice_km`, `code_version`.

## Files

| File | What |
|---|---|
| `isoModel.js` | pure logic: `decodeRing`, `nearestOrigin(origins, [lon, lat])`, `isoGeoJSON(file, originId, scenario)`, `originGeoJSON`, `cardRows`, `formatResidents`, `formatDistance`, labels |
| `isoData.js` | `loadIsochrones(agg)` (cached per session, null when absent), `isoUrl` |
| `isoLayers.js` | `isoLayerSpecs()`, `syncIsochrones(map, layers \| null, beforeId)`, `BAND_STYLE`, `bandLegend()` |
| `useIsochroneMode.js` | React hook: `useIsochroneMode(agg, on)` -> `{file, status, origin, distanceM, scenario, setScenario, pick, pickById, clear, layers}` |
| `IsochroneCard.jsx` | the card (props below) |
| `isochrones.css` | card styles (dark panel tones) |
| `isochrones.test.js` | tests (`npm --prefix web test`) |

## `IsochroneCard` props

| Prop | Type | |
|---|---|---|
| `file` | object \| null | `useIsochroneMode().file` |
| `status` | `'off' \| 'loading' \| 'ready' \| 'missing'` | |
| `origin` | `{id, name, kind, lon, lat}` \| null | null shows "Kliknij na mapie…" |
| `distanceM` | number | metres from the click to the origin; 0 hides it |
| `scenario` | `'am' \| 'evening'` | which one the map shows |
| `onScenario` | `(s) => void` | morning / evening switch |
| `onClose` | `() => void`, optional | leaves the mode |

## Wiring (for the agent who owns `App.jsx` and `MapView.jsx`)

1. **Mode switch.** Add a boolean `isoOn` in `App` (an overlay-like switch "Skąd dojadę" in the sidebar, enabled only
   when a city is selected). In `App`:
   ```js
   const iso = useIsochroneMode(selectedId, isoOn)
   ```
   Pass `iso.layers` and `iso.pick` to `MapView` (e.g. props `isoLayers`, `onIsoPick`), and render
   `<IsochroneCard {...iso} onScenario={iso.setScenario} onClose={() => setIsoOn(false)} />` in a map corner
   (the opposite one from the legend) or at the top of the city panel.
2. **Drawing.** In `MapView`, one effect:
   ```js
   useEffect(() => { if (ready) syncIsochrones(ready, isoLayers, ANCHOR_LABELS) }, [ready, isoLayers])
   ```
   `syncIsochrones` moves its layers to just below `ANCHOR_LABELS` on every call. `syncOverlays` does the same with
   its own layers, so call `syncIsochrones` after it whenever either changes (add `isoLayers` to the dependencies of
   the `syncOverlays` effect and call both there, `syncIsochrones` second): the bands then sit above the value
   layers and the city outlines. Pass the first outline layer id instead of `ANCHOR_LABELS` to keep outlines on top. Suggest switching value layers to a lower opacity (or off)
   while the mode is on: two fills on top of each other are hard to read.
3. **Clicks.** In the existing `m.on('click')` handler, keep this order:
   1. a node hit (stop-area popup) wins, as now;
   2. if the mode is on and a city is selected, and the click is inside that city's boundary
      (`boundaryHits(e.point)` contains the selected id), call `latest.current.onIsoPick([e.lngLat.lng, e.lngLat.lat])`
      and return, so the click does not reselect the city;
   3. otherwise the current behaviour (select the clicked city). Selecting another city resets the picked origin
      (the hook clears it when `agg` changes) and loads that city's file.
   Put `onIsoPick` in `latest.current` like `onSelect`.
4. **Cursor.** While the mode is on, use `crosshair` over the selected city in the `mousemove` handler.
5. **URL (optional).** `pickById(id)` restores a shared view: store `iso=<originId>` and the scenario in the hash.
6. **Phones.** The card fits 340 px; on phones show it in the bottom sheet instead of over the map.

## Limits to say on the page

- The isochrone is for the nearest **precomputed** origin, not the clicked point (the card names it and gives the
  distance). Origins: centre and hub, every sub-centre (GZM, Trójmiasto), the 30 busiest stop areas, and a 1-3 km
  lattice (see the QA note for the spacing per city).
- Scheduled times (Wednesday 2026-11-25), median of departures every minute in the window; not real times.
- Residents: NSP 2021 on the GHSL 250 m pattern; cells outside the timetable data coverage still count if reached.
