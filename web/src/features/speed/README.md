# Scheduled-speed overlay and line table (`features/speed`)

Self-contained: nothing here imports app files. Data come from `pipeline/speed_web.py`
(`results/web/speed/`): `trams.geojson`, `bus_<agg>.geojson` (one per agglomeration), `rail.geojson`, `lines.json`.
Since the stop-to-stop work the tram layer draws `segments/trams.geojson` (`pipeline/speed_segments_web.py`, one
feature per segment between consecutive stops); clicks select features and open the right panel of
`features/segments` (README there); `stretchPopup.js` is kept for a page that does not wire the selection.
Every speed is scheduled ("rozkład, nie pomiar"): rozkładowa prędkość komunikacyjna, stops included.

## Files

| File | What |
|---|---|
| `speedModel.js` | fixed speed classes (below 12, 12–15, 15–18, 18–22, 22–26, 26+ km/h; colours for the dark basemap, brighter = faster), the 13 band keys (`w_am` = Wednesday 07–09, `s_d` = Saturday 09–18, …), property names, ±1 min rounding interval, line keys |
| `lineLayers.js` | MapLibre specs of a `lines` layer (`lineSpecs`), `applyLines` (band, class focus, table highlight without restacking), filters (`linesFilter`, `idsFilter`), hit testing (`hitTest`, `lineLayerIds`, `hitBox`) |
| `stretchPopup.js` | popup model and DOM builder in the style of `nodePopup.js` (CSS classes `node-popup`, `np-*` reused, plus `sp-*`) |
| `lineTable.js` | pure logic of the table: parse `lines.json`, filters, sort values, link keys |
| `SpeedTable.jsx` | the line table on the kit's `DataTable` (`sortBy="column"`) with filter chips |
| `SpeedLegend.jsx` | legend body of the overlay (classes with hover / pin, widths, dashes) |
| `loader.js` | `loadSpeedLines(resolve)`, `layerUrl(layer, agg)` for the per-city bus files |
| `speed.css` | styles of the table, legend keys and popup bars (imported by `SpeedTable.jsx`) |
| `speed.test.js` | tests (`npm --prefix web test`) |

## Props

`<SpeedTable data cityNames filters onFilters hot onHot pinned onPin />`
- `data`: `await loadSpeedLines(absoluteUrl)`.
- `cityNames`: `{agg: name}`; with an empty object there is no city chip row.
- `filters` / `onFilters`: `{city, mode: 'tram'|'bus'|'rail'|'all', day: 'weekday'|'saturday', band}` (controlled);
  leave out for an uncontrolled table. Keep `filters.band` equal to the map's variant to show the same band.
- `hot`: array of row keys `"agg|feed|line"` to light (from the map); `onHot(keys | null)` when a row is hovered
  or its line button gets focus.
- `pinned`: array of row keys; `onPin(key)` on a click on a row (use `togglePin` from `lineTable.js`).

`<SpeedLegend layer band focus onHover onToggle onClear />`: same callbacks and focus object as `LegendBody` in
`Legend.jsx` (`focusOf(focuses, layer.id)`), so the class hover / pin goes through `classFocus.js` unchanged.

Popup: `renderStretchPopup(stretchPopupModel(feature.properties, band, catalogTimetableDates))`.

## Wiring (for the agent who owns the app files)

1. **Data sync.** `web/scripts/sync-data.mjs` copies only the top-level files of `results/web/`; add the
   `speed/` folder (copy `results/web/speed/*` to `public/data/speed/`).
2. **Catalog.** Add the three entries from `data/interim/proposals/speed.md` to `results/web/catalog.json`
   (kind `lines`, `variants` = the 13 band keys, `ramp` = the fixed classes, `size_property: "t"`, `mode_group`).
   The bus entry has `url_template: "data/speed/bus_{agg}.geojson"` and `cities` instead of `url`.
3. **`layerControl.js`**: add to `OVERLAY_KINDS`
   `lines: { label: 'Prędkość z rozkładu', order: 3 }`. The three layers become one group with chips
   (tramwaje / autobusy / metro i kolej); variants are already supported (`variantOf(state, layer)` gives the band).
4. **`mapLayers.js`**:
   - `KIND_ORDER`: add `lines: 1.5` (above the hatch, below stop areas and outlines).
   - `layerSpecs(layer, …)`: `else if (layer.kind === 'lines') specs.push(...lineSpecs(layer, band))`; the band is the
     layer's variant, so pass it in (e.g. a 4th argument `variants`, `band = variants?.[layer.id] ?? layer.variants[0].key`).
   - `sourceSpec`: for a layer with `url_template` use `resolvedLayer(layer, selectedAgg)` from `loader.js`; without a
     selected city the bus layer has no source and is skipped (`syncOverlays` should drop layers whose url is null).
     When the city changes, `map.getSource(sourceId(layer)).setData(newUrl)`.
   - After `syncOverlays`, and on band / focus / table-hover changes, call
     `applyLines(map, layer, band, { classes, match, hot })` where `classes = emphasised(focusOf(focuses, layer.id), layer.id)`,
     `match = pinned.length ? linesFilter(pinned) : null` and `hot = linesFilter(hotKeys)` (or `idsFilter([hoveredId])`).
5. **`Legend.jsx`**: in `LegendBody`, `if (layer.kind === 'lines') return <SpeedLegend layer={layer} band={band} focus={focus} … />`.
   The legend needs the band (pass `variants` down, or the resolved band per layer).
6. **`MapView.jsx`**:
   - hover: `map.queryRenderedFeatures(hitBox(e.point), { layers: lineLayerIds(layer) })` → `hitTest(layer, feats, band)`;
     put `{[layer.id]: hit.cls}` into the existing `hoverOnMap` hits (class focus) and `hit.keys` into the table's `hot`;
     `applyLines(..., { hot: idsFilter([hit.id]) })` lights the stretch itself.
   - click: popup with `renderStretchPopup(stretchPopupModel(hit.properties, band, dates))`, as for stop areas.
   - the line layers must be in the list of layers whose hover is handled (like `pointLayerIds`).
7. **Table placement**: `<SpeedTable>` belongs in the bottom dock next to the other tables (another agent is reworking
   the layout); keep `hot` / `pinned` in the page state so the map and the table share them.

## Rules the code keeps

- No data never looks like a value: a stretch without trips in the band is not drawn; missing cells are "–" / "brak danych".
- Time above free running is shown only for trams, in s/km with its range and the caveat; where the timetable is
  faster than the model the popup says so and gives no number (never a negative one).
- Dashed lines: below the 5-minute minimum (`short`), straight-line geometry (`straight`), unofficial feed (`unoff`).
- Zoom: trams and rail from 10, buses from 12, stretches with fewer than 4 trips an hour 1.5 levels later.
