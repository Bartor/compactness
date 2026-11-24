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
- ui-kit 0.3.2: `DataTable` (sticky heads, sorting by column or by row, one-line row headers, resizable columns,
  compact density). The site uses a vendored tarball until the version is on the npm registry.
- Layout rework: tables in a bottom dock (folded, half, whole screen with a small live map), legend in a map corner
  with the share of residents per class, class charts linked to hover and pin, the area outside the selected city
  dimmed.

## In progress

- To-do items 1–4, 6 and 9–16 below are being worked on (data and self-contained site pieces first, wiring into the
  site after each is checked).

## To do

Site
1. Charts: "share of residents with at least X" curves per city, the 5–60 minute reach curve with quartile band,
   dot strips or dumbbells for city comparison, time-of-day profile.
2. Line-speed overlay (tram and bus stretches, metro and rail lines) with day-type and time-band choice;
   per-city files or tiles for buses.
3. Speed tables view (lines by city, mode, band) linked both ways with the overlay; area-speed layer.
4. Node detail view: stops, walking paths, crossings, top line-to-line movements; nodes sized by actual use.
5. Network view: select a line, see its stretches and its connections with waits.
6. Isochrones from a clicked point; survey context (KBR mode shares) in the city view.
7. Switch the site to ui-kit `^0.3.2` from the registry and delete `web/vendor`; move the remaining local
   pieces (dock, legend with shares, mini-map) into the kit once the design settles.
8. Checks never done: Firefox, Safari, keyboard order, phone layout after each change; re-measure the transfer
   estimate per first visit. On a phone the city sheet covers most of the fitted city.

Method and data
9. Transfer layer revisions from the review: generalised-time band (walk x1.2–1.7, wait x1.5, penalty 5/13/18 min),
   crossing score on the AMPTI W6 scale, wait after the actual connecting arrival, share of frequent x frequent pairs,
   coordination test only for lines every 15 min or less often.
10. Speed: show time above free running in s/km with a range; fixed colour breaks; a Puls Gdańska-style check.
11. Variant comparable with the DG REGIO grid study (fastest peak trip, 1.2 km walk, 8/12 km radii).
12. Distribution outputs: share of residents below an explicit access floor (FGT), no headline Gini.
13. New open data: NSP 2021 age grid, commuting matrix, BDOT10k buildings, schools (RSPO) and hospitals as destinations.
14. Validation: about 100 random journey-planner pairs at several departure minutes; the 15 suburban pairs from
    the NIK audit; transfer shares from routed trips against Warsaw's 43 % (WBR 2015) and Jakdojade.
15. Wrocław tram what-if built on the slow stretches (target speed, re-run accessibility).
16. Form: Eurostat degree-of-urbanisation shares in the tables, Angel's proximity index, polycentricity for GZM and Trójmiasto.

## Known loose ends

- "All feeds never worse than official feeds" fails in a few cells per city; cause unknown.
- Evening and Saturday drops in Trójmiasto and GZM unexplained.
- Remainder against DG REGIO 2020 unexplained, largest for Łódź.
- Stop-area rule splits Kraków Główny and makes a few station complexes too wide.
- Street-running detection for tram track misreads some streets (lower bound); kinematic parameters are assumptions.
- No Sunday reference day (several feeds end on 2026-11-28).
- No expert review of the method.

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
