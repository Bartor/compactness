# Urban transit speed (trams and buses): definitions, benchmarks, determinants, timetable-based methods, and a cross-check of the project's speed analysis

Scope note: research done 2026-11-24 with web search and fetch (about 20 calls). Several sources were seen only as search-result excerpts or abstracts; each is marked. No files were downloaded. Project files read first: `results/RAPORT.md` §15.3 and `results/qa/transit/supply.md` §4.

## Terminology and benchmarks: technical, commercial and operating speed; published commercial speeds; what counts as good

### Takeaway
The project's use of "prędkość komunikacyjna" (route length over end-to-end time including stops) matches Polish usage, and its timetable values agree closely with the only like-for-like Polish benchmark, Puls Gdańska's timetable-based ranking (2023): same order of cities and differences under about 1 km/h, except Poznań. European in-street tram systems typically run at 15–20 km/h. Lines with priority or segregated track reach about 23–29 km/h in Polish timetables.

### Cited Findings
- **Definitions (Polish).** Prędkość komunikacyjna (also called "handlowa") is distance over travel time **including all stops on the route**. Prędkość techniczna **excludes stop time** and depends on traffic conditions and the vehicle. Source: TMiR articles returned for the definition query (e.g. [Oskarbski, TMiR 5/2016](https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-931efea5-ee88-4bb8-a855-84df0b14f09b/c/TMiR_5_2016_Oskarbski_Wyznaczanie.pdf); [Wołek, TMiR 2/2016](https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-d7f5de09-dfec-4790-98b9-7aa7625986c2/c/TMiR_2_2016_Wolek.pdf)). Seen as search excerpts only; page numbers not checked.
- I found no source in this session that gives a textbook definition of **prędkość eksploatacyjna** as a route average including terminal layovers. In the sources found, the term appears mainly as a vehicle's "maximum operating speed" — [search excerpts, TMiR/PWr articles](https://transportation.overview.pwr.edu.pl/UPLOAD/BAZA-ARTYKULOW/PL/2023/03/A_PL_23_03_02.pdf). The project's statement that eksploatacyjna includes layovers at terminals is therefore unverified here (see Gaps).
- **Puls Gdańska tram speed ranking 2023** ([pulsgdanska.pl, 25 July 2023](https://pulsgdanska.pl/transport/transport-miejski/raport-tramwajowy-2023/EE6rwi8Us9EiYy7r2Tvj), read in full).
  - Method: theoretical speeds from timetables valid on 30 May 2023, using line lengths from the organisers. Peak = the first weekday trip on the main route after 15:00; off-peak = the first trip after 21:00; overall = weighted average of the two (weights not given). Night, weekend and tourist lines are excluded. The authors say real speeds "may be lower, but should not be higher".
  - Overall / peak / off-peak, km/h: Bydgoszcz 21.1/20.4/21.8; **Poznań 20.5/20.0/21.1**; Częstochowa 20.2; Toruń 19.7; Olsztyn 19.5; **Kraków 19.3/19.2/19.5**; Szczecin 19.0; **Warszawa 18.9/18.4/19.4**; Grudziądz 18.8; Gorzów 18.3; **GOP 18.2/18.2/18.1**; **Gdańsk 17.7/17.8/17.7**; **Wrocław 16.9/16.2/17.6**; **Łódź 16.5/16.3/16.7**; Elbląg 16.4.
  - Fastest lines: Warszawa line 2 at 27.9 (peak) and 29.6 (off-peak); Poznań line 14 (PST, Poznań's fast tram) at 26.9 and 29.4; Kraków line 21 at 23.4; GOP line 35 at 23.8.
  - Gdańsk and GOP use the same running times all day. Wrocław has the largest peak/off-peak gap.
- The 2022 values (in brackets in the same article) differ from 2023 by −1.7 to +1.1 km/h. Closures and diversions are cited as causes, e.g. Łódź −0.4 and Warszawa −0.4 ([same source](https://pulsgdanska.pl/transport/transport-miejski/raport-tramwajowy-2023/EE6rwi8Us9EiYy7r2Tvj)).
- Gdańsk's average commercial speed rose from 17.1 to 17.7 km/h over two years. Traffic signals are named as the main source of delay, and most intersections still lacked tram priority ([Puls Gdańska, "Tramwaje przyspieszają"](https://pulsgdanska.pl/transport/transport-miejski/tramwaje-przyspieszaja/osN8sL7oRf8FZs2gZwmi); search excerpt only).
- **Europe.**
  - French tramways typically have commercial speeds of 17–20 km/h, including dwell and junction delays ([SYPTE, "LRT French comparisons" report, Urban Transport Group](https://www.urbantransportgroup.org/system/files/general-docs/LRTfrenchcomparisonsreport.pdf); search excerpt only).
  - Helsinki: 14.6 km/h including stops; a Helsinki official cites Zürich at about 17 km/h ([Helsinki Times](https://www.helsinkitimes.fi/finland/finland-news/domestic/13577-helsinki-s-trams-are-among-the-slowest-in-europe.html); excerpt only; year not checked).
  - AM peak: Zürich network 15.7 km/h, Vienna 15.1, Milan 10.6 between 07:00 and 09:00 ([Chitti, "Getting bus priority right. Lessons from Bologna"](https://marcochitti.substack.com/p/getting-bus-priority-right-lessons); secondary source, excerpt only).
  - Trams and buses in mixed traffic both run at about 15–20 km/h ([Tampere/Braunschweig study, MDPI Urban Science 2022](https://www.mdpi.com/2673-7590/2/4/44); excerpt only).
- **Bus benchmarks.** I found no source in this session giving Polish bus commercial speeds by city.

### Inferences
- **Project vs Puls Gdańska.** Ranking by overall speed, the two agree on everything except Kraków and Poznań, whose order is swapped.

  | City | Project (2026) | Puls Gdańska (2023) | Difference |
  |---|---|---|---|
  | Kraków | 19.8 | 19.3 | +0.5 |
  | Poznań | 19.5 | 20.5 | −1.0 |
  | Warszawa | 18.6 | 18.9 | −0.3 |
  | Gdańsk | 18.0 | 17.7 | +0.3 |
  | GZM | 17.2 (median per trip), 18.2 (weighted by vehicle-km) | 18.2 | — |
  | Łódź | 16.9 | 16.5 | +0.4 |
  | Wrocław | 16.3 (about 16.1 at peak) | 16.9 (16.2 at peak) | −0.6 |

  This is a useful external validation of the pipeline. Differences of this size are within the range explained by method (all trips vs one trip per line; shape length vs organiser length) and by three years of network changes.
- **Poznań.** The trip-median gap probably reflects method. Puls weights each line equally, and PST line 14 (about 27–29 km/h) is a strong outlier. The project's vehicle-km-weighted median of 20.1 is closer to Puls's figure.
- **Recommendation.** Cite Puls Gdańska as the external benchmark in the report. Add a "Puls-style" check: per line, the first main-route trip after 15:00 and after 21:00, to compare like with like.
- **What counts as good.** Below about 16 km/h is slow by both Polish and European standards. About 18–20 km/h is the typical European in-street range. Polish lines that are largely segregated with priority reach 23–29 km/h.

### Gaps
- The textbook definition of prędkość eksploatacyjna (Wyszomirski, Rudnicki, or a PN standard) was not retrieved; the "includes terminal layovers" claim in RAPORT §15.3 still needs a primary citation.
- IGKM "Komunikacja miejska w liczbach" and UITP statistics: not found or not open in this session.
- Puls Gdańska rankings for 2024–2026: not checked whether they exist.
- Polish bus commercial speeds: none found.

## Determinants: time lost to signals, dwell, traffic and restrictions; stop spacing; effects of priority and segregation; kinematic parameters

### Takeaway
In a French multi-system study, running time was about two-thirds of tram journey time, dwell about a quarter, and signal delay about 7–8% (1–14% across systems). Stop spacing is a major lever: about +3 km/h per +100 m in French data. Signal priority in Polish cases gives large local gains (Gdańsk about +28% on one route; about 27 km/h on a priority corridor). Plausible low-floor tram parameters are about 1.1 m/s² acceleration, about 1.1–1.3 m/s² service braking, and 50 km/h in street running, up to 70 km/h on selected segregated sections.

### Cited Findings
- **Six French light-rail systems.** LRV running time was 65–71% of total journey time, dwell 22–27%, and signal delay 7–8%. In the off-peak, signal delay reached 14% in Paris and 1% in Strasbourg. Mean dwell was 16–31 s off-peak and 21–37 s at peak. ([Wu, McDonald et al., "Characteristics of Light Rail Travel Time: Examples from France", Journal of Public Transportation](https://digitalcommons.usf.edu/jpt/vol1/iss2/3/); also on [ScienceDirect](https://www.sciencedirect.com/science/article/pii/S1077291X22004763); search excerpt only; publication year not verified here.)
- **Stop spacing.** Commercial speed rises by 3.0 km/h for every 100 m increase in average stop spacing ([SYPTE French comparisons report](https://www.urbantransportgroup.org/system/files/general-docs/LRTfrenchcomparisonsreport.pdf); excerpt only; sample and regression not seen).
- **Gdańsk.**
  - Changing signal programmes (TRISTAR, no major infrastructure work) gave about a 28% speed gain on the Piecki-Migowo route ([Szmagliński, "Analiza efektywności wprowadzenia priorytetu dla tramwajów na przykładzie Gdańska"](https://media-prof.pl/web/files/44501/s8_p3_J.Szmaglinski_Analiza-efektywnosci-wprowadzenia-priorytetu_dla_tramwajow_na_przykladzie_Gdanska.pdf); excerpt only; baseline and target speeds not seen).
  - On ul. Marynarki Polskiej, TRISTAR priority lets trams average close to 27 km/h ([trojmiasto.pl](https://www.trojmiasto.pl/wiadomosci/Tu-tramwaje-jada-najszybciej-Maja-specjalny-priorytet-n228335.html); excerpt).
- **Kraków.**
  - Full priority at six signals in the Krowodrza area ([Gryga, TMiR 06/2013](https://bibliotekanauki.pl/articles/192719.pdf); excerpt only).
  - A microsimulation of Prądnik Czerwony compares absolute, relative and fixed-time priority. One priority variant raises average tram speed to 23.60 km/h ([Bakalarz & Horowska, Journal of Translogistics](https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-5dd5f8d5-ed5b-45aa-993a-2c0b465ceac9/c/bakalarz.pdf); excerpt only; baseline not seen).
- **Wrocław.**
  - A June 2024 city reply names signalling, crossing lines and the lack of separated track as factors limiting tram speed ([wroclaw.pl, "W ruchu drogowym potrzebna jest równowaga"](https://www.wroclaw.pl/dla-mieszkanca/w-ruchu-drogowym-potrzebna-jest-rownowaga); excerpt).
  - A city interview says priority is not granted where simulation shows an excessive capacity cost at the intersection ([wroclaw.pl, "O priorytetach w komunikacji i ITS-ie"](https://www.wroclaw.pl/komunikacja/o-priorytetach-w-komunikacji-i-itsie); excerpt).
  - No quantified time-loss study for Wrocław was found.
- **Simulation studies of signal priority** (Chinese corridors, not directly transferable): optimised priority reduces tram running time by 11–13% and stops at signals by 82–85% ([Wiley J. Adv. Transp. 2019](https://onlinelibrary.wiley.com/doi/10.1155/2019/4802967); [ResearchGate](https://www.researchgate.net/publication/337730339_Timetable_Optimization_for_a_Two-Way_Tram_Line_With_an_Active_Signal_Priority_Strategy); excerpts).
- **Vehicle kinematics.** One low-floor tram specification (NGT6) gives starting acceleration with load 1.1 m/s², braking deceleration with load 1.14 m/s², emergency deceleration 3 m/s², and maximum speed 80 km/h (Tramwaje Śląskie tender attachment, [Załącznik nr 1 do SIWZ](https://www.tram-silesia.pl/www/wp-content/uploads/2014/05/Zalacznik_nr_1_do_SIWZ.pdf), per search excerpt; not opened).
- **Intersection modelling.** An intersection clearance-time method assumes 1.2 m/s² as the maximum acceleration of approaching trams ([Gondek, "Prędkość…" 10/2013](https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-85e62608-cac4-4dc8-8805-db910169ac23/c/Gondek_Predkosc_10_2013.pdf); excerpt).
- **Regulation.** Tram technical conditions are set in Rozporządzenie MI, Dz.U. 2011 nr 65 poz. 344. Chapter 8 distinguishes the service brake from the emergency brake. The noise test is at a constant 50 km/h on segregated ballasted track ([ELI PDF](https://eli.gov.pl/eli/DU/2011/344/ogl/pol/pdf); [infor.pl](https://www.infor.pl/akt-prawny/DZU.2011.065.0000344,rozporzadzenie-ministra-infrastruktury-w-sprawie-warunkow-technicznych-tramwajow-i-trolejbusow-oraz-zakresu-ich-niezbednego-wyposazenia.html); excerpts; no deceleration figures seen).
- **Speed limits.** A search summary stated a 50 km/h general maximum for trams and up to 70 km/h on selected sections (the Kraków and Poznań fast trams). The primary source was not identified (see Gaps).

### Inferences
- **Free-running benchmark for the kinematic model** (own calculation). Assumptions: a = 1.1 m/s², b = 1.14 m/s², v_max = 50 km/h (13.9 m/s), dwell 20 s, no signals.
  - At 445 m spacing (Wrocław): accelerating takes 12.6 s over 88 m, braking 12.2 s over 85 m, and cruising 19.6 s. That gives about 44 s of running plus 20 s dwell, or about **25 km/h**.
  - At 533 m spacing (Kraków): about **27 km/h**.
  - Scheduled values of 16–20 km/h therefore imply that roughly **30–40% of scheduled time is "slack"**: signals, traffic, speed restrictions such as switches, curves and 30–40 km/h zones, longer dwells, and padding.
  - This is consistent in order of magnitude with the French breakdown, but slack is not the same as signal delay: the French "running time" also contains below-cap running.
- **Stop spacing in the Wrocław–Kraków gap.** The 88 m spacing difference "explains" about 2.6 km/h of the 3.5 km/h gap by the French rule of thumb. My kinematic calculation gives about 2 km/h. So stop spacing is plausibly the largest single factor, which RAPORT should state cautiously.
- **The speed cap dominates the result.** v_max is the most sensitive parameter. Use OSM `maxspeed` where tagged on `railway=tram`, else 50 km/h on street-running track and 60–70 km/h on segregated track. Apply 15–25 km/h limits through switches and tight curves; derive curves from geometry using radius thresholds.
- **Run a sensitivity table.** Use a ∈ {0.9, 1.1, 1.3}, dwell ∈ {15, 20, 30} s and the v_max variants, so that "implied slack" is reported as a range.

### Gaps
- The primary legal source for tram speed limits in Poland was not found. Candidates: Prawo o ruchu drogowym art. 20 (trams follow road limits in mixed traffic) and operators' internal "Instrukcja ruchu" for segregated track. Not verified.
- TCQSM 3rd ed. (TCRP Report 165) chapters on running time, dwell and signal delay, and TCRP Synthesis reports on TSP, were not retrieved this session.
- Measured before/after priority results for Zürich, Poznań and Warszawa were not found.
- Kraków AMPTI or ZTP priority monitoring reports were not found.

## Timetable-derived analysis: segment speeds, padding and recovery from GTFS; whole-minute rounding; "scheduled minus free-running" precedents; pitfalls

### Takeaway
Scheduled segment speeds from GTFS are standard; several open tools compute them. "Padding" has been measured as scheduled time minus a best-case reference time, but in published work the reference comes from real-time data, not from a kinematic model. The project's kinematic "implied slack" is a reasonable, transparent variant, but it measures everything not modelled (signals, traffic, restrictions, extra dwell, padding), not padding alone. Whole-minute times make stop-to-stop speeds unusable at about 450 m spacing; aggregate to stretches of several minutes.

### Cited Findings
- **Wessel & Widener (2017).** "Discovering the space–time dimensions of schedule padding and delay from GTFS and real-time transit data", J. Geographical Systems 19(1): 93–107, doi:10.1007/s10109-016-0244-8.
  - Padding is defined as extra time added to schedules to reduce the risk of delay.
  - It is located at the stop-to-stop segment level by comparing GTFS with real-time vehicle positions.
  - Where there is more random delay, there should be more padding.
  - ([RePEc abstract](https://ideas.repec.org/a/kap/jgeosy/v19y2017i1d10.1007_s10109-016-0244-8.html); abstract only. The full text on the U of T repository returned HTTP 403.)
- A search summary of the same paper reports padding at 29.4% of total scheduled service for the TTC, measured against a "theoretical best time" per segment ([U of T repository record](https://utoronto.scholaris.ca/server/api/core/bitstreams/1ebf3f74-a1b5-44e4-861e-bac3e5df983e/content)). Not read (403); treat as unverified.
- **Free-flow from early-morning trips.** A bus reliability study defines free-flow as travel with zero delays and estimates it from early-morning trips ([arXiv 2303.17888](https://arxiv.org/pdf/2303.17888); excerpt).
- **Open tools for scheduled segment speeds.**
  - GTFSwizard `get_speeds` computes distance over duration in km/h ([rdrr.io](https://rdrr.io/cran/GTFSwizard/man/get_speeds.html)).
  - `gtfs_functions` produces per-segment speeds and a `segment_max_speed_kmh` column ([GitHub](https://github.com/Bondify/gtfs_functions)).
  - gtfs2emis falls back to constant-speed interpolation or to the feed's average speed where segment speeds are missing ([GitHub PR #120](https://github.com/ipea/gtfs2emis/pull/120)).
- **Penn State GTFS-RT delay study.** Reports that high-pace segments create opportunities for large stochastic speed-ups and that a network may carry excessive padding ([Penn State Pure](https://pure.psu.edu/en/publications/measurement-and-classification-of-transit-delays-using-gtfs-rt-da/); abstract only).
- **Puls Gdańska on Gdańsk and GOP.** Both use identical running times all day, so time-of-day speed differences in their timetables are zero by construction ([Puls Gdańska 2023](https://pulsgdanska.pl/transport/transport-miejski/raport-tramwajowy-2023/EE6rwi8Us9EiYy7r2Tvj)).

### Inferences
- **Precedent and interpretation.** Published padding work uses an empirical best time from AVL, typically a low percentile of observed run times. The kinematic free-running time is a stricter, physical lower bound. Call it "time above free running" or "implied slack" (the project's term), and avoid "padding" or "loss to signals".
  - Slack mixes infrastructure delay (signals, mixed traffic, slow orders) with operator policy (recovery time, generous dwell).
  - Slack that varies by time of day on the same stretch indicates traffic or congestion allowance.
  - Constant slack, as in Gdańsk and GZM's single running-time sets, indicates infrastructure or policy.
- **Rounding.** With whole-minute times, each stop-to-stop time has up to ±1 min of error (both ends rounded). At 445 m and about 1 min per segment, stop-level speed is meaningless.
  - Aggregate to stretches of at least 4–5 scheduled minutes, or 2–3 km, giving roughly ±10–20% speed uncertainty.
  - Better: average many trips. Rounding offsets vary across trips, so the mean over trips converges, while the median does not.
  - Report a speed interval: length / (t + 1 min) to length / (t − 1 min).
  - Check the GTFS `timepoint` field. Where non-timepoint times are interpolated by the producer, stop-level times carry no information.
- **Other pitfalls.**
  - The trip split defines what "end-to-end" means (already noted in supply.md §4).
  - Short turns and depot trips bias line medians.
  - Shape length vs straight-line length shifts speeds by 0.5–1 km/h (supply.md).
  - Holding time inside trips is rare here (under 0.1% of trips).
  - Recovery at termini is invisible in commercial speed. Operating speed with layovers needs `block_id`, which only some feeds populate.
  - Diversions in the reference week change stretch speeds; flag stretches whose trip set differs from the usual week.
  - For buses, GTFS shapes may not follow the actual road path.

### Gaps
- No published study using a kinematic free-running model as the reference for GTFS slack was found. Railway timetabling uses "running time supplements" relative to a technical minimum (UIC 451-1), but this was not verified this session.
- Wessel & Widener full methods and numbers: abstract only.

## Real versus scheduled: what comparisons find; minimum validation; which cities publish real-time data

### Takeaway
Schedule-based GTFS overstates real accessibility, by about 5–15% in high-access zones, with strong spatial patterns. A small real-time validation is feasible: Kraków, Gdańsk and GZM appear to publish GTFS-RT, Warszawa offers vehicle positions through an API (key needed), and Wrocław, Poznań and Łódź were unconfirmed.

### Cited Findings
- **Wessel & Farber (2019).** "On the accuracy of schedule-based GTFS for measuring accessibility", JTLU 12(1). They used archived AVL from four North American agencies over five days, reconstructed as retrospective GTFS. In high-access zones, real accessibility converged about **5–15% below** the schedule-based estimate. Low-access origins were less reliable and more variable, and errors had strong spatial patterns ([JTLU](https://jtlu.org/index.php/jtlu/article/view/1502); abstract page read).
- **Cal-ITP California Transit Speed Maps.**
  - Speeds are interpolated between the two nearest GTFS-RT positions per trip.
  - The **20th percentile** per segment and period is the headline measure; variability is the p80/p20 ratio.
  - Segments run stop to stop, split every 1 km when stops are far apart.
  - The data is a single day, usually a Wednesday, with a move to rolling averages in progress.
  - ([Cal-ITP README](https://analysis.dds.dot.ca.gov/rt/README.html); [Caltrans ArcGIS Speeds_by_Stop_Segments](https://caltrans-gis.dot.ca.gov/arcgis/rest/services/CHrailroad/Speeds_by_Stop_Segments/MapServer))
- **Polish real-time feeds** (existence from listings; live status not checked):
  - Kraków: tram and bus GTFS-RT on [Transitland](https://www.transit.land/feeds/f-ztp~krakow~bus~rt).
  - Gdańsk: [Transitland ztm~gdansk~rt](https://www.transit.land/feeds/f-u3tm-ztm~gdansk~rt).
  - GZM: GTFS-RT for buses, trolleybuses and trams via its open-data platform, built by Vooom ([metropoliagzm.pl](https://metropoliagzm.pl/tag/vooom/?print=pdf); [Transitland](https://www.transit.land/feeds/f-transport~gzm~pl)).
  - Warszawa: city API vehicle positions; the community WarsawGTFS builds GTFS-RT from it, API key required ([GitHub MKuranowski/WarsawGTFS](https://github.com/MKuranowski/WarsawGTFS)).
  - Szczecin (outside scope): vehicle positions every about 10 s ([ZDiTM](https://www.zditm.szczecin.pl/en/zditm/for-developers)).
  - Poland's implementation of the EU open-data requirement was described as weak in 2024 ([Spider's Web, Jan 2024](https://spidersweb.pl/2024/01/rozklady-jazdy-dostep-w-polsce.html)).

### Inferences
- **Minimum validation (proposed).**
  - Log GTFS-RT vehicle positions at 10–30 s for 2–3 ordinary weekdays (Tue–Thu, outside holidays) in two contrasting cities: Kraków (fast) and GZM or Gdańsk. Warszawa can be added via the API if a key is acceptable to the project.
  - Compute observed stretch times on the same stretches, then compare scheduled vs observed p50 and p20 by time band.
  - This is a small, reversible collection: one script and a few hundred MB. It contradicts the shelved decision only in scale.
- **Wrocław.** It has the most interesting result (slowest network, peak dip), but no open real-time feed was confirmed. Validation there would depend on finding the MPK/iMPK positions source; not checked.
- **Expectations.** Scheduled times are generous where padding is large, so observed off-peak speeds may exceed the schedule. Puls Gdańska's "should not be higher" assumes trams cannot run early, which holds only where drivers hold at timepoints.

### Gaps
- Live status and licences of the Kraków, Gdańsk and GZM GTFS-RT feeds were not checked.
- Wrocław, Poznań and Łódź real-time availability: unknown.
- No Polish study comparing GTFS with AVL tram speeds was found.

## Presentation: transit speed maps and dashboards; encodings; readability

### Takeaway
The best open precedent is Cal-ITP's speed maps: stop-to-stop segments coloured by a low-percentile speed per time period, with a separate variability layer and a period selector. For a timetable-only project, the same encoding works with scheduled speed and implied slack.

### Cited Findings
- **Cal-ITP speed maps.**
  - Segment colour shows p20 speed per period. One version uses AM Peak 07–10, Midday 10–15, PM Peak 15–20 and Evening 20–24; an older mirror uses different windows.
  - A second metric, p80/p20, shows variability.
  - Long inter-stop gaps are split into about 1 km segments.
  - Data is published as ArcGIS services with p20, p50 and p80.
  - ([Cal-ITP README](https://analysis.dds.dot.ca.gov/rt/README.html); [netlify mirror](https://rt--cal-itp-data-analyses.netlify.app/readme))
- The Brussels study "The (in)efficiency of trams and buses in Brussels: a fine geographical analysis" maps speeds at fine segment level ([ResearchGate](https://www.researchgate.net/publication/312442673_The_inefficiency_of_trams_and_buses_in_Brussels_a_fine_geographical_analysis); title and listing only).

### Inferences (recommendations, own)
- **Map layer "Prędkość rozkładowa".**
  - Stretches drawn on the track geometry.
  - Colour: scheduled speed in a sequential ramp with fixed, city-independent breaks (<12, 12–15, 15–18, 18–21, 21–25, >25 km/h), so cities compare.
  - Width: trips per hour, square-root scaled.
  - Directions: offset left and right, since speeds differ by direction near terminals and on hills.
  - Time band selector: peak 7–9, midday, peak 15–18, evening after 20, plus Saturday.
- **Second layer "Czas ponad jazdę swobodną" (implied slack).**
  - Show slack as seconds per km, or the ratio scheduled / free-running, rather than km/h. It is additive along a route and readable as "minutes lost here".
  - Use a diverging or sequential ramp with an explicit "model, not measured" label, and show the parameter set in a tooltip.
- **Tooltip.**
  - Length, scheduled time (with ±1 min interval), speed, free-running time, slack, and the number of stops, signals and crossings from OSM.
  - Share of street-running vs separated track.
  - Number of trips aggregated.
- **Tables.**
  - Per line × day type × time band: median and IQR of trip speed, vehicle-km weighted.
  - Stop spacing per line.
  - The Puls-style comparison column.
- **Suppression.** Suppress stretches under about 4 scheduled minutes or with fewer than 4 trips in the band, because of rounding noise.
- **Statement for readers.** Present all speeds as schedule-based, in line with Wessel & Farber's 5–15% overstatement for accessibility.

### Gaps
- Agency bus speed maps were not opened this session: NYC MTA bus speeds, TransitCenter or Bus Turnaround scorecards, TfL bus performance, the Vienna or Zürich priority monitors. Their encodings are not documented here.
- No public Polish tram speed map was found.

## What-if: precedents for "speed up corridor X" with accessibility or ridership outcomes; realistic targets

### Takeaway
Accessibility what-ifs for speed are established, especially in US work on bus lanes and BRT. Gains depend on keeping lanes clear and on the share of the route improved. Realistic Polish tram targets are corridor-level: priority corridors reach about 23–27 km/h in timetables, and a city-wide lift of about 0.5–1 km/h over two years is what Gdańsk achieved.

### Cited Findings
- **Washington, DC (Urban Institute, WMATA data).**
  - Fully clear priority bus lanes would raise jobs reachable in 30 min by about 90% for the average resident.
  - Obstruction along a quarter of the route cuts the gain to about 20,000 jobs, against 40,000 with clear lanes.
  - More frequent buses add about 30,000 jobs, mostly through shorter waits.
  - ([Smart Cities Dive summary](https://www.smartcitiesdive.com/news/dedicated-bus-lanes-enforcement-increase-equity-job-access/714190/); secondary, excerpt only)
- **Twin Cities.** Five transitway scenarios; the prospective network improves average worker accessibility by 5.51% ([UMN Accessibility Observatory / CTS](https://www.cts.umn.edu/publications/catalyst/2020/april/transitway); excerpt).
- **Met Council Transit Service Allocation Study.** Scenarios give +8.4% and +2.3% job access, averaged over travel-time thresholds ([Appendix F](https://metrocouncil.org/Transportation/System/Transit/Studies/Transit-Service-Allocation-Study/FinalDocs/Transit-Service-Allocation-Study-Appendix-F.aspx); excerpt).
- **Lima BRT.** Reduced travel times to jobs for residents within walking distance of the line ([IADB](https://publications.iadb.org/en/node/18495); excerpt).
- **Polish speed targets observed.**
  - Gdańsk Marynarki Polskiej with priority: about 27 km/h ([trojmiasto.pl](https://www.trojmiasto.pl/wiadomosci/Tu-tramwaje-jada-najszybciej-Maja-specjalny-priorytet-n228335.html)).
  - Gdańsk Piecki-Migowo: +28% from signal changes ([Szmagliński](https://media-prof.pl/web/files/44501/s8_p3_J.Szmaglinski_Analiza-efektywnosci-wprowadzenia-priorytetu_dla_tramwajow_na_przykladzie_Gdanska.pdf)).
  - Kraków simulated priority: 23.6 km/h ([Bakalarz & Horowska](https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-5dd5f8d5-ed5b-45aa-993a-2c0b465ceac9/c/bakalarz.pdf)).
  - Gdańsk network: 17.1 → 17.7 km/h in two years ([Puls Gdańska](https://pulsgdanska.pl/transport/transport-miejski/tramwaje-przyspieszaja/osN8sL7oRf8FZs2gZwmi)).
  - Fastest Polish lines: 27–30 km/h ([Puls Gdańska 2023](https://pulsgdanska.pl/transport/transport-miejski/raport-tramwajowy-2023/EE6rwi8Us9EiYy7r2Tvj)).

### Inferences (recommendations, own)
- **Define targets relative to evidence, not as one number.**
  - (a) Raise each stretch to the city's p75 stretch speed for the same track type (street vs segregated).
  - (b) Cap slack at X s/km, with X taken from the best-performing stretches in Kraków or Poznań.
  - (c) Make the stretches with OSM `railway:signal` or crossing density above a threshold "priority-equipped", with a gain of 15–28% (Gdańsk range) bounded by free-running time.
  - Never exceed free-running time.
- **Report the accessibility result** as the change in a fixed metric the project already uses, per city and per hour.
- **Keep frequency fixed.** In a what-if, the scenario should keep headways and change only running times. The DC case shows wait time and speed effects are of similar size, and mixing them muddies attribution.
- **Treat the result as an upper bound** for schedule-based access (Wessel & Farber).

### Gaps
- Zürich, Vienna and Kraków before/after programme evaluations with measured speed and ridership were not retrieved.
- No European tram accessibility what-if study was found this session.
