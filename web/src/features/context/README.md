# Survey context block

A compact block for the city view: how residents travel according to the latest household travel survey (KBR),
as a stacked bar with the year and a source link, one plain sentence on what limits comparison between cities, and
"brak badania" where there is no survey.

## Data

- `results/web/survey_context.json`, written by `python -m pipeline.survey_context` (values typed in from the
  sources, never computed). The sync script copies top-level files of `results/web/`, so it arrives as
  `data/survey_context.json` with no change to the script. QA note with every value and its source:
  `results/qa/survey_context/survey_context.md`.
- Shape: `agglomerations[agg]` with `status` (`published` | `partial` | `in_progress` | `none`), `survey`, `year`,
  `base`, `modal_split` (`walk`, `bike`, `pt`, `car`, `other`; each `{v, src, loc[, note]}` or null), `partial`
  (Warszawa: bars by destination zone), `avg_trip_min`, `avg_trip_min_pt`, `trips_per_person`,
  `pt_transfer_share` (null everywhere: no source publishes it), `comparability` (one Polish sentence), `upcoming`;
  `sources[key]` = `{title, url, primary}`.

## Files

| File | What |
|---|---|
| `surveyModel.js` | `loadSurveyContext()` (null when absent), `surveyView(data, agg)`, `barSegments(split)`, colours and labels |
| `SurveyContext.jsx` | the block |
| `context.css` | styles (dark panel tones) |
| `surveyContext.test.js` | tests; they read the real `results/web/survey_context.json` |

## Props of `SurveyContext`

| Prop | Type | |
|---|---|---|
| `data` | object \| null | the loaded file; null renders nothing |
| `agg` | string | agglomeration id (`warszawa`, `krakow`, `wroclaw`, `poznan`, `lodz`, `trojmiasto`, `gzm`) |

## Wiring (for the agent who owns `App.jsx` and `CityView.jsx` / `CityPanel.jsx`)

1. In `App`'s `Loaded`, load once: `const [survey, setSurvey] = useState(null); useEffect(() => { loadSurveyContext().then(setSurvey) }, [])`.
   Optionally add `surveyContext: 'survey_context.json'` to `DATA_FILES` in `config.js` (the module uses its own
   constant `SURVEY_FILE` today).
2. Pass `survey` in `cityProps` and render `<SurveyContext data={survey} agg={city.id} />` in `CityView` and
   `CityPanel`, after the transport metrics (it is context, not a result of this project).
3. Nothing else: the block hides itself when the file or the city record is missing.

## What the block must keep saying

- Shares are not comparable one to one between cities (different bases: all trips vs non-walking trips, trip from
  100 m vs 250 m, Gdańsk counts every mode used). The `comparability` sentence is per city; do not drop it.
- Unpublished values are shown as "nie podano" (hatched), never as a share or as 0.
