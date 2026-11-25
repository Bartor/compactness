# Roadmap

Working list of what is done, in progress and still to do. Results and method live in `results/RAPORT.md`
(Polish); the literature review behind many of these items is `reports/Urban transit metrics research review.md`.
Last updated 2026-11-24.

## Done and published

- Phases 0–4 of the brief: inventory, density and form (13 agglomerations), frequent service and supply,
  transport performance with R5 (98 + 7 routing units), map site on GitHub Pages.
- Urban-centre variant (Eurostat 2021 clusters); DG REGIO 2020 benchmark reproduction; Google Maps check (30 trips).
- Extra layers: density x service (5 000 people/km2), ease of transfer at stop areas (walk + wait = total),
  share of 30-minute reach that needs a transfer (direct-trips variant).
- Urban form rerun on the census-scaled grid, centre sensitivity, comparison with Bertaud and Malpezzi, threshold sweep.
- Scheduled speeds: line tables by day type and time band, 1 km area speeds, tram and bus stretches with
  time above free running (data only, not on the site yet).
- Site redesign after the KBR viewer: dark theme, radio cards for value layers, switches for overlays,
  comparison and city tables with "how to read it" explanations, colours for the dark basemap.
- ui-kit 0.3.3 from the npm registry: `DataTable` (sticky heads, sorting by column or by row, one-line row headers,
  resizable columns, compact density, several actions per row).
- Layout rework: tables in a bottom dock (folded, half, whole screen with a small live map), legend in a map corner
  with the share of residents per class, class charts linked to hover and pin, the area outside the selected city
  dimmed.
- Distribution outputs and charts: share of residents below an explicit access floor (FGT, no Gini), "at least X"
  curves, the 5-60 minute reach curve with quartile band, dot strips, dumbbells and the time-of-day profile, in the
  dock and linked with the tables, legend and map.
- Comparison by the rules of the DG REGIO grid study: under like-for-like rules the Polish cities sit near the
  EU means for their size (GZM below at 45 minutes); DG REGIO's own values for four centres read from its map.
- Transfer revisions after the review: wait after the actual connecting arrival (it equals the random-arrival
  wait: timetables are not coordinated by day; the test does find night-line meeting points), a generalised-time
  band from published weights, crossings on the AMPTI W6 scale, frequent x frequent movements, and a detail
  export for 1 757 nodes (stops, walking paths, crossings, line-to-line movements).
- Routed-trip sample (135 000 trips): transfer shares against Warsaw's survey and Jakdojade (the level depends on
  the destination draw and a transfer penalty, the order of cities holds), use of stop areas for transfers, and the
  15 suburban pairs of the NIK audit.
- Site restructure after the UX review: a header bar for global state (home, city, one area switch, "O danych"),
  a sidebar with only what the map shows, a comparison view (one table of 13 agglomerations, charts) and a city
  view (highlights, all measures, charts, transfers) with real tabs, a page per metric, a short "?" everywhere,
  click a city on the map, cell tooltips, the small map beside the panel in full mode, phone fixes.
- On the site since the restructure: scheduled line speeds as an overlay (trams, buses of the selected city, metro
  and rail; day type and time band) with a "Prędkości" tab of lines per city; stop-area detail in "Przesiadki"
  (stops, walking paths, crossings, line-to-line matrix); "Dokąd dojadę stąd" isochrones from precomputed origins;
  travel-survey mode shares in the city view.
- Who and to what: frequent service and reach for residents aged 0-14 and 65+ (census 1 km grid by age), and travel
  time by public transport to the nearest secondary school (RSPO) and hospital emergency department (RPRM).
- Urban form additions: residents by 250 m density class, official Eurostat 2021 urban-centre shares, polycentricity
  (eta and density hotspots) in the tables; Angel's proximity index in the tables only (not robust among
  single-centre cities).

## In progress

- To-do items 2–4, 6, 9–11 and 13–15 below are being worked on (data and self-contained site pieces first, wiring
  into the site after each is checked).

## To do

Site
1. Charts, remaining: density-class and rank-size charts from `results/charts/form.json`; pinned cities in the
   address; pinned cities marked in the comparison table.
3. Area-speed layer (the 1 km scheduled speeds as a grid layer); the map behaviour of the new overlays was checked
   in headless Chrome only (speed stretches and popup, stop-area detail, isochrones), not by hand.
5. Network view: select a line, see its stretches and its connections with waits.
7. Move the remaining local pieces (dock, tabs, legend with shares, stacked bars, SVG to PNG export) into the kit
   once the design settles.
8. Checks never done: Firefox, Safari, keyboard order, phone layout after each change; re-measure the transfer
   estimate per first visit. On a phone the city sheet covers most of the fitted city.

Method and data
9. Transfer revisions, remaining: wire the node detail view and popup rows (connection wait, generalised-time
   band, W6 crossing score); an optional W6 map layer; W6 classes not checked on the ground.
10. Speed: show time above free running in s/km with a range; fixed colour breaks; a Puls Gdańska-style check.
11. DG REGIO grid-study variant, remaining: the cause of Warszawa's 8-point gap to DG REGIO's own value; the
    total-walk limit (R5 limits each leg, not the trip); register `data/raw/dgregio_gridstudy/` in the manifest.
12. Distribution, remaining: the same outputs on the raw GHSL grid as a sensitivity variant.
13. Who and to what, remaining: emergency departments on the site once the register is checked (it lists 4 units
    for the whole GZM area); map layers of travel time to the nearest school and emergency department; the
    commuting matrix and BDOT10k buildings were not used; licences of the two register downloads not stated.
14. Validation, remaining: about 100 random journey-planner pairs at several departure minutes; the cause of the
    10-22 minute gap to the NIK audit's times around Poznań; nodes sized by use on the map (data ready in
    `results/layers/node_use.parquet`).
15. Wrocław tram what-if, remaining: a map layer of the gain and a block in the city view; other cities; Saturday and evening windows.
16. Form, remaining: Eurostat's official medium-density clusters (level 2 classes) were not downloaded; town halls
    not checked against official registers.

## Known loose ends

- "All feeds never worse than official feeds" fails in a few cells per city; cause unknown.
- Evening and Saturday drops in Trójmiasto and GZM unexplained.
- Remainder against DG REGIO 2020 unexplained, largest for Łódź.
- Stop-area rule splits Kraków Główny and makes a few station complexes too wide.
- Street-running detection for tram track misreads some streets (lower bound); kinematic parameters are assumptions.
- No Sunday reference day (several feeds end on 2026-11-28).
- No expert review of the method.
- Independent first-use UX review: `reports/UX review 2026-11-24.md` (55 findings). The five left open after the
  restructure were closed on 2026-11-25: popups are placed inside the visible map (35), columns slide to their new
  places on a sort (24, ui-kit 0.3.4), one fit per city and the same fit for the first view and "home" (19), chart
  tables wrap instead of scrolling (31), plain measure names and a glossary in "O danych" (40). Still not checked by
  hand: a real browser other than headless Chrome, Firefox and Safari, keyboard use, touch gestures; popups in the
  small map of the full panel and popups of speed lines; a popup as tall as the map still overlaps the legend; the
  phone city panel cuts the chart buttons at the right edge; the panel height set by dragging is not kept in the link.
- Column widths set by the reader are kept in the browser (ui-kit 0.3.4, `widthsKey`); needs the kit published and
  the dependency raised to `^0.3.4`.

## Decided against, or shelved

- Live vehicle positions (GTFS-RT): shelved by the owner twice; the timetable-versus-reality gap (5–15 % in
  published studies) is stated as a limit, not measured.
- Competition-adjusted accessibility (2SFCA), a headline Gini, mode-specific transfer penalties, a blended
  transfer score, a 3 x 3 bivariate colour grid.

## Waiting on the owner

- Fare-integration table for the common-ticket network variant.
- Which cycling variant is the headline (calm streets only, or including busier streets).
- Whether to link the map publicly, and under which domain; basemap provider.
- GitGuardian incident from 2026-11-23: mark as false positive.
- Sources that need a human download: see the ranked table at the end of the research review.
