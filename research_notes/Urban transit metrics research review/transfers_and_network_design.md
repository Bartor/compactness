# Transfers, interchange quality and network structure: literature vs. the project's "ease of transfer" layer

Scope note. These notes were written 2026-11-24 after reading RAPORT.md §20 and results/qa/transfer/transfer.md. The full texts actually read (converted from PDF) were: Wardman 1998 (ITS Leeds WP 525), Ortelli et al. 2026 (STRC), Meskell, Brazil and Whitney 2024 (NTA Ireland/UTSG), the SNAMUTS European monograph draft (Scheurer, Curtis, Mees et al. 2012), Weckström et al. 2021 (TR-A, open access), the WBR 2015 synthesis (Warsaw) and Czekała and Bryniarska 2017 (TMiR 6/2017, already in the repo). Everything else is from abstracts, repository records or search snippets, and is marked as such. The yadda.icm.edu.pl copies of TMiR 6/2014 (Olszewski et al.) and the ZTM Warszawa AMPTI calibration document returned HTTP 403, both through the fetch tool and through a plain Python request, so they were not read. No files were added to data/raw/research (both download attempts failed and the empty folders were removed).

## Q1. Empirical transfer penalties: size, drivers, and how weights could turn the project's components into a generalised transfer time

### Takeaway
The literature splits a transfer into three parts: transfer walk time, weighted at about 1.2 to 1.7 times in-vehicle time; transfer wait time, weighted at about 1.5 times in-vehicle time; and a fixed "pure" transfer penalty (PTP). Typical PTP values are 13–18 equivalent in-vehicle minutes (EIVM) in European urban studies, 16–21 for bus–bus changes, and as little as about 2.5 for uncrowded cross-platform metro changes. The newest evidence (Geneva, 2026) suggests that a large part of the "penalty" is really discomfort with the onward mode (bus vs rail) rather than the act of changing. This supports showing the project's components side by side and adding a generalised time as a band (low and high weights), not as a single score.

### Cited Findings
**Walk and wait weights**
- Wardman's British meta-analysis rejects the convention of weighting walk and wait at 2× in-vehicle time. For walk time, the mean ratio to in-vehicle time over 140 valuations is 1.66 (95% CI 1.54–1.78) (§4.1). The mean for wait time is 1.47 (§4.4), and for combined walk-and-wait 1.46 (§4.3) — [Wardman 1998, ITS Leeds WP 525](https://eprints.whiterose.ac.uk/2086/1/ITS195_WP525_uploadable.pdf).
- Wardman, Table 8 and §4.7 (pp. 25–26), interchange as a fixed penalty "in addition to any wait time": mean 31.3 IVT-minutes over 47 values (median 22.5). It is lower for commuting (about 14 min; the table's row labels are garbled in the text extraction, so treat the purpose split as approximate), 16.2 for suburban and 43.5 for inter-urban trips. Interchange values rise with trip distance, which is consistent with the distance-based penalties in the British Passenger Demand Forecasting Handbook. Commuters' lower values are attributed to familiarity and high frequencies, which reduce the consequences of a missed connection — [Wardman 1998](https://eprints.whiterose.ac.uk/2086/1/ITS195_WP525_uploadable.pdf).

**Pure transfer penalty (PTP)**
- Madrid: the PTP equals 15.2–17.7 EIVM. The model also controls for habit, crowding, walking, waiting, information and intermodality — [Garcia-Martinez, Cascajo, Jara-Diaz, Chowdhury, Monzon 2018, TR-A 114:52–66 (abstract only)](https://ideas.repec.org/a/eee/transa/v114y2018ipap52-66.html).
- Vitoria-Gasteiz: 18.4 EIVM in dry weather, 13.9 EIVM as an annual weighted average including bad weather. The paper cites a meta-analysis value of 17.6 EIVM and proposes 13–18 EIVM as a planning range — [Jara-Diaz, Monzon, Cascajo, Garcia-Martinez 2022, Transport Policy 125:48–55 (abstract only)](https://www.worldtransitresearch.info/research/9198).
- London Underground: a method separating transfer walking, waiting and penalty components, applied to 17 transfer stations and 303 transfer movements. The cost of transfers is uneven across stations and across platform pairs within a station — [Guo and Wilson 2011, TR-A 45(2):91–104 (abstract only)](https://www.worldtransitresearch.info/research/3709/). Secondary sources attribute two further points to this paper; neither was verified in the original. First, an average penalty of about 4.9 IVT-min. Second, significant station factors: escalators, number of stairs, horizontal distance, ramp length and same-level platforms — [search snippets citing Guo and Wilson](https://www.semanticscholar.org/paper/Assessing-the-cost-of-transfer-inconvenience-in-A-Guo-Wilson/a51e7a7378f528d3e43108a15a6956f6f854cfee).
- Range of published PTPs: from about 2.5 EIVM for uncrowded cross-platform metro changes in London (Raveau et al. 2014) to over 28 EIVM for bus–bus changes in Sydney (Douglas and Jones 2013). The penalty is modulated by wayfinding, shelter, escalators, shops, the physical configuration of the change (cross-platform, up or down, out of station), real-time information, crowding, weather and familiarity (Ortelli et al., pp. 1–2) — [Ortelli, Masse, Ravalet, Kaufmann, Reck, STRC 2026](https://strc.ch/2026/Ortelli_EtAl.pdf).
- Penalties consistently differ by mode pair, with bus-involving transfers higher than rail-only ones. Meskell et al. (2024) attribute this to bus unreliability, poorer stop facilities, the need to cross roads, and weather exposure — [Ortelli et al. 2026, p. 1](https://strc.ch/2026/Ortelli_EtAl.pdf).
- Geneva, unlabeled stated-choice experiment (1,135 respondents, 5,675 observations): once mode constants are estimated separately, the residual transfer penalty is 5–9 EIVM. The mode constants are themselves 7–22 EIVM (abstract): tram 7.4–7.8, bus 8.0–8.7, shared bike about 22 (Table 6). In the pooled model, walking is 1.21 EIVM per minute, rising for minutes beyond 5 and beyond 15 (each minute beyond 15 is valued at 1.65 EIVM); pooled waiting is 0.78. Rain adds about 1.4 EIVM per minute of walking and about 0.55–0.60 per minute of waiting (pp. 12–14) — [Ortelli et al. 2026](https://strc.ch/2026/Ortelli_EtAl.pdf).
- Dublin, bus to bus (1,037 respondents): interchange penalties are 16.9 min at a dedicated facility, 16.5 min at an ordinary stop, and 20.9 min where a walk between stops is needed (actual walk time is already in travel time). Facility vs ordinary stop is not significantly different. Infrequent bus users have penalties of about 18–24 min, frequent users about 13–16 min (Tables 2–4, pp. 8–9). In the Likert ranking of interchange features (Table 5, p. 10), the top features are service attributes (schedule adherence, real-time information, frequency) and shelter; café, toilets and staff rank lowest. The column alignment in the extracted text is offset, so only the order is reported here — [Meskell, Brazil, Whitney, UTSG 2024](https://www.nationaltransport.ie/wp-content/uploads/2024/07/Estimation-of-Bus-to-Bus-Interchange-Penalties-in-an-Irish-Context.pdf).
- The same paper cites Currie (2005) for average transfer penalties of 22 min (bus–bus) and 8 min (subway–subway) — [Meskell et al. 2024, p. 3](https://www.nationaltransport.ie/wp-content/uploads/2024/07/Estimation-of-Bus-to-Bus-Interchange-Penalties-in-an-Irish-Context.pdf); the original is [Currie 2005, J. Public Transportation 8(1):41–55](https://digitalcommons.usf.edu/jpt/vol8/iss1/3) (not read).
- Santiago (Transantiago): metro–metro, metro–bus, bus–metro and bus–bus transfers were compared. Transfer walking time and the final walk to the destination are the most heavily penalised components; information and escalators also matter — [Navarrete and Ortúzar 2013, Transport Policy 25:138–147 (abstract only)](https://ideas.repec.org/a/eee/trapol/v25y2013icp138-147.html).
- Iseki and Taylor link transfer penalties and values of time to generalised trip cost, and group transfer-facility attributes into five categories: access, connection and reliability, information, amenities, and security and safety — [Iseki and Taylor, Transport Reviews 29(6):777–800 (abstract only; the year is given as 2008 or 2009 in different indexes)](https://ideas.repec.org/a/taf/transr/v29y2008i6p777-800.html).
- Routing-based network assessment commonly uses a small explicit penalty. Weckström et al. use generalised time = t_arr − t_dep + k·b, with k = 3 min per boarding, to keep journeys with avoidable transfers out of the Pareto set (eq. 5, §3.2) — [Weckström, Mladenović, Kujala, Saramäki 2021, TR-A 147:212–229, CC BY](https://acris.aalto.fi/ws/portalfiles/portal/61334894/1_s2.0_S0965856421000471_main.pdf).

### Inferences
- **Generalised transfer time without inventing a score.** For each transfer movement: GTT = a·walk + b·wait + P. Here a is the walk weight (1.2–1.7, from Wardman's 1.66 and Ortelli's pooled 1.21), b is the wait weight (about 1.5, from Wardman's 1.47) and P is the PTP. All parameters come from published sources, so this is a transformation, not a new index. Publish it as a low/central/high band, for example P = 5 (Geneva residual) / 13 / 18 (Jara-Diaz planning range), with a and b at their low and high values. Keep the components visible. At the project's top-20 nodes (walk about 2 min, wait about 5–15 min), the walk term contributes about 3 min, the wait term 8–23 min and P 5–18 min. The penalty is therefore of the same order as the wait, and the ranking between cities is driven by the wait. This sharpens the project's finding that waiting dominates walking.
- Mode-pair dependence: if P is shown, it should differ for bus-involving vs rail-only transfers, or be shown flat with a note. Ortelli's result argues for flat P plus a separate "onward mode" label, rather than mode-specific penalties that double-count the "rail bonus".
- Crossings and steps: Guo and Wilson and Navarrete and Ortúzar treat stairs, escalators and level changes as drivers of the station-specific penalty. No source found here gives a per-crossing or per-flight minute equivalent that could be transferred. The project should therefore keep crossings and steps as counts, or map crossings to AMPTI W6 percentages (see Q2), rather than converting them to minutes.
- Wardman's finding that the penalty is lower where frequencies are high, and Dublin's 5-minute vs 25-minute split design, both suggest the penalty interacts with headway. This is consistent with the project's choice to report wait separately.

### Gaps
- The Guo and Wilson 2011 full text (minute values per station attribute) was not read; the 4.9 min figure is unverified.
- No Polish or Central European stated-preference or revealed-preference transfer-penalty estimate was found in this session. Polish model manuals (for example WBR traffic model documentation) may contain the penalties used in Warsaw's or Kraków's VISUM models; not checked.
- Wardman's later meta-analyses (Wardman, Chintakayala, de Jong 2016 on European values; the 2013 multiplier paper) were found only as records; their interchange figures were not read — [White Rose record](https://eprints.whiterose.ac.uk/104595/1/European).
- No source gave the random-arrival vs timetable-aware headway threshold. The commonly cited value of about 10–12 min comes from memory and was not verified.

## Q2. Interchange assessment methods (AMPTI, EU projects, TfL, German and Swiss practice) and what is computable from GTFS and OSM

### Takeaway
AMPTI (the 8-indicator version used in Kraków) is a field-audit method. Of its eight indicators, only W2 (compactness: distances and times between stops) and, partially, W6 (pedestrian safety by crossing type) and W4 (step-free access) can be derived from OSM and GTFS. W6's crossing-type scale maps almost directly onto tags the project already reads. TfL's guidelines and EU projects add evaluation frameworks built on themes such as efficiency, but they are audit- and design-oriented. Timetable-based quality (wait, connection) is not part of AMPTI at all, which is where GTFS adds value.

### Cited Findings
- AMPTI as applied in Kraków (2015 audit) uses eight indicators, W1–W8 (Czekała and Bryniarska, TMiR 6/2017, pp. 6–7):
  - W1: basic infrastructure (platform width and length, surface, obstacles, kerb height, shelter);
  - W2: compactness (passenger-flow-weighted mean distance and time between stops, plus mean walk length between platforms);
  - W3: legibility (number of stops or entrances visible from each other stop);
  - W4: share of elements meeting accessibility requirements (tactile paving, lowered kerbs, acoustic signals, ramps or lifts at level changes);
  - W5: personal security (lighting, CCTV);
  - W6: traffic safety of crossings, scored by type: 100% for an underpass or footbridge, 70% for a signal without turning conflicts, 50% for a signal with turning conflicts, 30% for an unsignalised zebra, 0% for an unmarked crossing;
  - W7: share of segments with full passenger information;
  - W8: additional amenities —

  [Czekała and Bryniarska 2017](https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-1b506d14-888a-4ac2-816e-b6d116664788/c/TMiR_6_2017_Czekala.pdf) (read from the copy in the repo's data/raw/ampti_tmir/).
- The 2014 methodological paper presents AMPTI as 14 quantitative indicators computable from concrete data, not subjective scores, covering compactness, legibility, amenities, basic infrastructure and accessibility. A later (2022) source says the current version has 10 indicators — [search snippets: Olszewski et al., TMiR 6/2014](https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-f92e2739-81b5-4b24-818d-d783697b8401/c/TMiR_6_2014_Olszewski.pdf) (the PDF returned HTTP 403; not read).
- ZTM Warszawa's "Wskaźniki oceny węzłów przesiadkowych" (WOWP; Krukowski, Olszewski, Wapniarski) uses an 8-indicator AMPTI variant. It introduces the concept of a "relacja przesiadkowa" (transfer relation) and weights features by user perception and expert judgement — [search snippet of the ZTM calibration document](https://ztm.waw.pl/wp-content/uploads/2019/10/Etap_III-Kalibracja-wska%C5%BAnik%C3%B3w-oceny-1.pdf) (HTTP 403; not read).
- TfL Interchange Best Practice Guidelines (Steer Davies Gleave, November 2009, replacing a 2001 guide) provide an evaluation framework for existing and proposed interchanges based on appraisal techniques, with spatial management principles and four themes, one of which is efficiency — [EMTA news](https://emta.com/news/tfl-launches-the-interchange-best-practice-guidelines); [Steer](https://na.steergroup.com/en-us/insights/delivering-world-class-public-transport-interchange) (snippets only). A refreshed 2026 edition is mentioned by one blog — [ianVisits](https://www.ianvisits.co.uk/articles/tfl-updates-the-small-print-behind-londons-big-transport-hubs-92847/) (not verified).
- Zurich practice (as described by SNAMUTS): transfer points are marked on mapping material and on in-vehicle screens with real-time connecting departures, including "hurry" advice when connections are tight. Pulse timetables between trains and buses are used where both run every 30 min — [SNAMUTS European monograph draft 2012, p. 20](https://archiv.ivt.ethz.ch/news/archive/20130903_scheurer_SNAMUTS_draft.pdf).
- Dublin's evidence that dedicated interchange facilities do not lower the bus–bus penalty relative to good stops, and that service attributes and shelter rank highest, supports prioritising timetable-derived measures over facility audits — [Meskell et al. 2024, pp. 9–10](https://www.nationaltransport.ie/wp-content/uploads/2024/07/Estimation-of-Bus-to-Bus-Interchange-Penalties-in-an-Irish-Context.pdf).

### Inferences
Computability of indicators from GTFS and OSM:

| Indicator (source) | GTFS + OSM? | Note |
|---|---|---|
| Distance and time between stops, compactness (AMPTI W2; Guo and Wilson walk) | Yes; already done | Flow-weighting is not possible without passenger counts. Weighting by vehicle trips (A arrivals × B departures) is a proxy, and the project already uses it. |
| Crossing safety (AMPTI W6) | Largely yes | OSM gives tunnel/bridge, `crossing=traffic_signals`, `crossing=uncontrolled`/`zebra` (marked) and `crossing=unmarked`. Turning-conflict detail is not in OSM, so the 70/50 split cannot be made; use 60% for any signal or report both. A per-movement "W6-style" mean would replace the bare crossing count with a published scale. |
| Step-free path (AMPTI W4, partial) | Partial; already done | Tactile paving (`tactile_paving=*`) and kerbs (`kerb=lowered/raised`) exist in OSM but coverage is patchy. Report a coverage share before using them. |
| Legibility (W3) | Approximate | Line of sight between stops could be approximated from building footprints in OSM (visibility test). Weak proxy; not recommended as a headline. |
| Shelter (W1, Dublin ranking) | Partial | `shelter=yes` on `public_transport=platform` nodes in OSM; coverage unknown. |
| Real-time information (W7) | Partial | `passenger_information_display=yes` in OSM; coverage unknown. |
| Security, amenities, platform quality, surface (W1, W5, W8) | No | Field audit only. |
| Wait, connection, frequency, reliability | GTFS (scheduled only) | Not part of AMPTI. Reliability needs GTFS-Realtime or AVL data, which the project does not have. |

### Gaps
- The full AMPTI 2014 indicator list, its formulas and the WOWP weights were not read (403).
- Detailed TfL 2009 criteria; City-HUB, NODES and PIRATE indicator sets; German (FGSV) and Swiss (VöV, SBB) interchange guidance: not reached in this session. Nothing about them is asserted here.
- OSM tag coverage for shelter, displays and tactile paving in the seven Polish agglomerations is unknown. It can be checked in the project's PBF.

## Q3. Network-design literature on transfers, and measurable signatures of a connective vs direct-service network

### Takeaway
Walker, Mees and the HiTrans/Nielsen school argue that a network of frequent lines meeting at transfer points (the "network effect") gives anywhere-to-anywhere access at affordable cost, provided transfers are cheap. That requires high frequency or timed connections, integrated fares and good interchanges. SNAMUTS operationalises this with indicators that combine travel time, frequency and the number of transfers. The measurable signatures are: the share of origin–destination pairs or trips requiring a transfer; the frequency of both legs at the meeting point; the transfer-dependence of accessibility; mean transfers per origin–destination pair (SNAMUTS degree centrality); and the travel-time and transfer trade-off seen in redesigns.

### Cited Findings
- SNAMUTS definitions (European monograph draft, May 2012):
  - Network only includes services meeting a minimum standard, "SNAMUTS 20", in the weekday inter-peak. A variant, "SNAMUTS 23", admits rail and ferry at 30-minute frequency because half-hourly rail still structures land use (p. 9).
  - Closeness centrality: the average "travel impediment", travel time divided by service frequency, between each activity node and all others (p. 10).
  - Degree centrality: the average number of transfers required to travel between activity centres, called "transfer intensity" (p. 10).
  - Contour catchment: the share of residents and jobs reachable within 30 min with at most one transfer. Both legs must run at least every 15 min, and a penalty equal to the network's average transfer time is deducted (p. 11).
  - Betweenness: the distribution of travel opportunities across nodes and segments (p. 13).
  - Later revisions de-emphasise frequency in the impediment formula and treat nodal connectivity on linear corridors differently from dead ends (p. 14) —

  [Scheurer, Curtis, Mees et al. 2012](https://archiv.ivt.ethz.ch/news/archive/20130903_scheurer_SNAMUTS_draft.pdf); method pages at [snamuts.com](https://www.snamuts.com/about-snamuts.html).
- The same monograph notes that in Zurich trams, buses and trolleybuses "form a tightly woven, grid-shaped network", while Winterthur is more radial around the station (p. 20). Integrated fares with free transfers vs operator-specific fares are recorded per city as a context variable (pp. 5–6, 11) — [SNAMUTS 2012](https://archiv.ivt.ethz.ch/news/archive/20130903_scheurer_SNAMUTS_draft.pdf).
- Mees (Transport for Suburbia, 2010): good transit depends on networks that allow easy transfers at key intersections, which needs a strong central planning body. The network effect imitates the car's flexibility by knitting routes and modes into one multimodal network. The Toronto bus network fed the subway (in Mees's earlier book), and the Zurich ZVV is the model — [review summaries found by search; book not read](https://www.greaterauckland.org.nz/2009/11/06/urban-transit-vs-commuter-transit/). The book was only accessed through reviews.
- Walker (Human Transit, 2011; revised 2024): frequency is freedom. Grid networks of frequent straight lines maximise access, with Portland's 1982 grid as the example (most lines every 15 min or better). The revised edition has a chapter "Connections or Complexity?" — [UBC Press listing](https://ubcpress.ca/human-transit-revised-edition); [TREC summary](https://trec.pdx.edu/node/3251) (secondary only; the book was not read).
- HiTrans Best Practice Guide 2, "Public Transport – Planning the Networks" (Nielsen et al. 2005, Interreg III, Rogaland), stresses commitment to networks rather than individual corridors and the importance of the network effect. A later paper cites Nielsen for transfers being integral to giving access to many destinations at affordable operator cost, provided transfer inconvenience is minimised — [Transport for Melbourne summary](https://transportformelbourne.org/network-planning-best-practice) (guide not read).
- Dublin's bus network redesign (BusConnects) explicitly requires more interchange "to take advantage of the network effect" — [Meskell et al. 2024, p. 11](https://www.nationaltransport.ie/wp-content/uploads/2024/07/Estimation-of-Bus-to-Bus-Interchange-Penalties-in-an-Irish-Context.pdf).
- A nine-city redesign assessment (Amsterdam, Auckland, Austin, Baltimore, Columbus, Helsinki, Houston, Indianapolis, Wellington) uses GTFS before and after. Its journey-level measures are the number of Pareto-optimal journey alternatives, the number of trajectory variants and the frequency of the most frequent variant (§3.3). Redesigns generally improved navigability, but in some cases at the cost of more travel time and more transfers — [Weckström et al. 2021](https://acris.aalto.fi/ws/portalfiles/portal/61334894/1_s2.0_S0965856421000471_main.pdf).
- Companion work, also by the Aalto group: Kujala et al. 2018b, "Travel times and transfers in public transport: Comprehensive accessibility analysis based on Pareto-optimal journeys", and an open GTFS dataset for 25 cities (Kujala et al. 2018a, Sci. Data) — [reference list in Weckström et al. 2021](https://acris.aalto.fi/ws/portalfiles/portal/61334894/1_s2.0_S0965856421000471_main.pdf) (2018b not read).

### Inferences
Signatures the project can compute with what it already has (GTFS, router, stop areas):
1. **Transfer dependence of access.** Reach with 0 transfers divided by reach with an unrestricted number of transfers (or ≤ 2), per origin cell, within the same time budget. This is the planned "direct trips only" measure. A connective network shows low direct share and high total reach; a direct-service radial network shows high direct share toward the centre and low reach elsewhere.
2. **SNAMUTS-style transfer intensity.** The mean minimum number of boardings between activity centres, or between population-weighted cells, at time budget T.
3. **Frequency at nodes, both legs.** The share of line-pair movements where both lines run ≤ 10 (or ≤ 15) min. This is Walker's and SNAMUTS's condition for cheap transfers. The project's wait component already contains it implicitly, but a categorical "frequent × frequent" share is easier to read.
4. **Direct vs transfer travel-time ratio.** For origin–destination pairs that have both, the ratio of the best direct trip to the best trip with a transfer (generalised with Q1's band). A ratio well above 1 means the network relies on transfers to be fast.
5. **Radiality.** The share of a city's departures or line-pairs concentrated in the top-k nodes, or the share of lines passing the centre. This is an inference, not taken from a source.

The project's finding that limiting trips to two transfers changes accessibility by at most 0.14 points is consistent with either a mostly direct network or one where a second transfer rarely pays off. It does not distinguish the two; measure 1 (0 vs 1 transfer) does.

### Gaps
- The text of Walker's, Mees's, Vuchic's and Nielsen's books was not accessed; claims rest on publisher pages and reviews.
- The SNAMUTS numerical results for any Polish city: none found. SNAMUTS European cases were Western, Southern and Northern European.
- No quantitative cross-city study was found giving the share of trips with transfers as a function of network type.

## Q4. Detecting and evaluating timed transfers from timetable data; why they may be absent or undetectable in Polish feeds

### Takeaway
Timed transfers are standard at Swiss and German nodes in clock-face systems and are aimed at low-frequency (30 to 60 min) services. In headway-based urban networks running every 5–10 min, coordination is neither expected nor detectable. GTFS can flag timed transfers in transfers.txt (transfer_type=1/2), but feeds rarely populate it. Detection from stop_times is a statistical test against chance, which the project already does. Its result (11–14% of pairs "fitting" against about 10% by chance) is what one expects from a mostly uncoordinated, frequent network.

### Cited Findings
- Swiss integrated timetables are symmetric clock-face systems. Trains arrive at and leave nodes around the full or half hour so that connections are short. The symmetry minute is about 58–58½ in Central Europe, and Bahn 2000 built a hub-and-spoke system with journey times between hubs just under an hour or a multiple of half-hours — [Wikipedia: Symmetry minute](https://en.wikipedia.org/wiki/Symmetry_minute); [Wikipedia: Rail 2000](https://Www.wikipedia.org/wiki/Rail_2000) (tertiary sources; primary STRC paper [Hürlimann 2005](https://www.strc.ch/2005/Huerlimann.pdf) not read).
- Zurich: pulse timetables between trains and buses "particularly where frequencies on both modes drop to 30 minutes" — [SNAMUTS 2012, p. 20](https://archiv.ivt.ethz.ch/news/archive/20130903_scheurer_SNAMUTS_draft.pdf).
- In GTFS, timed transfers are coded in transfers.txt (transfer_type 1 = timed; 2 = minimum time, which requires min_transfer_time). Validators flag missing min_transfer_time — [MobilityData gtfs-validator issue #2174](https://github.com/MobilityData/gtfs-validator/issues/2174). Many feeds only partially populate transfers.txt — [minotor README](https://unpkg.com/minotor@11.5.0/README.md).
- Planned transfer waiting times can be computed from GTFS schedules, as a Swedish study did as the baseline for synchronisation optimisation — [Springer, Public Transport 2018 (abstract)](https://link.springer.com/article/10.1007/s12469-018-0178-2). A broader review covers real-time synchronisation (holding, stop-skipping) — [Transport Reviews 2022](https://www.tandfonline.com/doi/full/10.1080/01441647.2022.2035014) (abstracts only).
- Wardman: lower commuter interchange penalties are partly because high frequencies reduce the consequence of missed connections — [Wardman 1998, §4.7](https://eprints.whiterose.ac.uk/2086/1/ITS195_WP525_uploadable.pdf).

### Inferences
Why the project's test finds no signal:
1. Most urban line pairs in Polish cores run every 5–12 min (Q5 waits of 5–8 min at top nodes), where coordination is pointless.
2. Coordination in Polish practice, if any, would be in suburban bus–rail feeders, the GZM's low-frequency lines, and night networks. These are diluted when all pairs are pooled.
3. Minute-rounded GTFS with no dwell time blurs 1–3 min margins.
4. Through-running or interlined trips look like perfect connections and must be removed (the project notes this).
5. One weekday captures pulses that hold all day but cannot separate them from coincidence on a single pair.

Suggested tests:
- (a) Restrict to pairs where both legs have headway ≥ 15 min, and test the distribution of feeder-arrival-to-departure gaps (mod headway) for a peak at 2–6 min versus uniform. Use a permutation test, as now, but report per node and per mode pair (rail→bus especially).
- (b) Use a positive control. Warsaw's night bus network has historically used a timed meeting at Dworzec Centralny (from memory, not verified this session). It lies outside the 06–20 window, so run the detector there. If it does not find that pulse, the detector is too weak.
- (c) Check whether any Polish feed populates transfers.txt with type 1 or 2.

Evaluation for users: for a transferring passenger the wait is set by the feeder's arrival, not random arrival. A "scheduled connection wait" (median and P90 over A-arrivals of the time to the next B departure after walking) is the transfer-specific wait. The random-arrival wait (half the headway plus irregularity) describes boarding at the start of a trip. The project computes the former inside the coordination test but publishes the latter as the wait component.

### Gaps
- No Polish source was found on timed transfers or pulse nodes in the seven agglomerations (for example regional rail–bus "węzły" in Silesia or Pomerania).
- No peer-reviewed GTFS-based coordination detector was read in full. The literature found is mostly about optimisation and real-time control.

## Q5. Polish evidence on transfer behaviour and tariff or timetable integration

### Takeaway
Warsaw's 2015 travel survey shows that 57.2% of public transport trips are made without a transfer, so about 43% involve at least one change. This is the only hard Polish transfer-share figure found. Tariff integration exists in all the agglomerations studied, in varying depth: Warsaw ZTM with rail inside the zone, GZM metropolitan tickets since 2018, and MZKZG metropolitan tickets with SKM in the Tricity since 2007. Survey transfer shares for Kraków, Wrocław, Poznań, Łódź, Tricity and GZM were not found.

### Cited Findings
- Warsaw WBR 2015: public transport is 46.8% of all trips and 56.9% of non-walking trips; three out of four non-walking trips are made without needing to transfer; and "in public transport trips, 57.2% of journeys are made without transfers" (synthesis, p. 9) — [WBR 2015 Synteza](https://transport.um.warszawa.pl/documents/62470/8560273/WBR_2015_SYNTEZA_POL.pdf/e845cef6-5f42-76a6-d2b8-50b83e486f2c?t=1634498737045).
- GZM: a joint-ticket reform for all three public transport organisers began with single tickets on 1 January 2018 — [metropoliagzm.pl/en/transport (snippet)](https://metropoliagzm.pl/en/transport).
- Tricity: MZKZG (founded 2007 by 13 municipalities) issues metropolitan tickets also valid on SKM and on a regional rail section. In March 2026, PKP Intercity, POLREGIO and SKM signed a ticket-honouring agreement across the Pomeranian voivodeship that includes MZKZG metropolitan rail-inclusive tickets — [MZKZG integration concept 2015](https://metropoliagdansk.pl/upload/files/MZKZG_Koncepcja%20Integracji_2015.pdf); [RMF24 2026](https://www.rmf24.pl/regiony/trojmiasto/news-duze-ulatwienie-dla-podroznych-na-pomorzu-rowniez-tych-przyj,nId,8074181) (snippets).
- Kraków: the 2023 KBR covered 36 gminas of the metropolitan area. No published transfer share was found; the previous (2013) study put public transport at 36.3% of trips — [BIP Kraków](https://www.bip.krakow.pl/?sub_dok_id=184386) (snippet).
- Wrocław: KBR 2024 results are published, but no transfer figures were found in the pages reached — [wroclaw.pl](https://www.wroclaw.pl/komunikacja/kompleksowe-badanie-ruchu-2024-we-wroclawiu-i-gminach-sasiednich-wyniki).
- Kraków AMPTI applications (Dworzec Główny, Rondo Mogilskie, Borek Fałęcki; later Rondo Grunwaldzkie, Podgórze SKA, and the Kurdwanów and Mały Płaszów P+R sites) combine audits with surveys of transferring passengers — [Czekała and Bryniarska 2017](https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-1b506d14-888a-4ac2-816e-b6d116664788/c/TMiR_6_2017_Czekala.pdf); [PK library record](https://suw-redirect.biblos.pk.edu.pl/resourceDetailsBPP&rId=98684).

### Inferences
- About 43% of Warsaw public transport trips involve a change, against the project's small routed sample in which most fastest trips had 0–1 transfers. Both can be true: survey trips include rail, metro and feeder trips from the outskirts, while the routed sample covers grid cells. The survey share is a useful external benchmark if the project counts transfers on a population-weighted origin–destination sample. That is the planned "node use from routed trips" step.
- Ticket integration matters for interpreting transfers. Under time-based tickets (Warsaw, Kraków, Wrocław, GZM), a transfer costs no fare. Where rail or regional operators are not integrated, it does. The project could add a binary "fare-integrated with onward line" flag per mode pair where known. SNAMUTS records this as a context variable.

### Gaps
- Transfer shares from KBR surveys for Kraków 2023, Wrocław 2024, Poznań, Łódź, Tricity (OMGGS 2014 and 2020 reports exist but were not opened) and GZM: not found or not read. The PDFs to check first are the [OMGGS 2014 detailed report](https://www.metropoliagdansk.pl/upload/files/2_Raport%20szczeg%C3%B3%C5%82owy%20badania%20i%20pomiary%20XII%202014(2).pdf) and the Kraków KBR 2023 attachments on krakow.pl.
- The current state of Poznań's tariff integration (ZTM, PEKA, Koleje Wielkopolskie) and Łódź's (MPK, ŁKA) was not checked.

## Q6. Visualisations that make transfer and network information useful to a lay user

### Takeaway
Published practice that works for lay audiences is (a) frequency-first maps (Walker-style frequent networks), (b) "where can I get from here" isochrones compared between scenarios, and (c) SNAMUTS-style maps of transfers needed or reach. No public example was found of a per-node connection matrix or a line-to-line wait diagram for a lay audience. These are inferred designs, though easy to build from the project's existing tables.

### Cited Findings
- Isochrones comparing an existing and a proposed network, which users explore from their own location (Remix static images for Yekaterinburg; a GTFS web map for the Richmond redesign): "How Does a Transit Plan Change Where You Can Go?" — [Landman, Human Transit, 2016-08-09](https://humantransit.org/?p=26634).
- GTFS isochrone tools exist; some routing libraries expose a maximum-transfers parameter (minotor's maxTransfers, default 5), which enables 0-transfer and 1-transfer reach maps — [minotor](https://unpkg.com/minotor@11.5.0/README.md); [Transitcat](https://transit.land/news/2018/10/09/transitcat.html); [IDEO "frequency is freedom"](https://github.com/ideo/frequency-is-freedom); [Conveyal on interactive isochrones](https://medium.com/conveyal-blog/shaping-conversations-about-transit-with-interactive-isochrone-mapping-1d6530d6a8a4).
- SNAMUTS publishes city maps of closeness, degree (transfer intensity) and contour catchment by node and segment — [snamuts.com, Utrecht 2021 example](https://www.snamuts.com/utrecht-2021.html).
- Navigability measures (number of alternatives, trajectory variants) are mapped by origin in the nine-city redesign study — [Weckström et al. 2021](https://acris.aalto.fi/ws/portalfiles/portal/61334894/1_s2.0_S0965856421000471_main.pdf).
- Zurich's in-vehicle real-time connection displays are an operator-side visual of the same information: "your connection leaves in X, hurry" — [SNAMUTS 2012, p. 20](https://archiv.ivt.ethz.ch/news/archive/20130903_scheurer_SNAMUTS_draft.pdf).

### Inferences
All of these are design proposals, not sourced. They use the project's existing data.
1. **"Change or not" reach map.** Per origin cell, the reach within 30 or 45 min with 0 transfers vs with ≤ 1 transfer, coloured by the ratio. This is the strongest lay message: "here you need to change to reach most of the city". It is the planned direct-only accessibility, mapped.
2. **Node card instead of a dot.** On click, show:
   - a small connection matrix, with arrival directions as rows and departure directions as columns, and each cell showing walk + scheduled wait (median and P90) coloured by generalised time with the Q1 band;
   - the drawn walking paths with crossings coloured by AMPTI W6 class;
   - one sentence such as "Typical change here: 2 min walk, 1 street crossing with lights, 7 min wait; at night 22 min".

   This answers "what is it like to change here", which the dot cannot.
3. **Line-to-line wait strip.** For a selected pair (A→B), a 24-hour strip of the wait after each A arrival. It shows whether connections are systematically good or bad, which is the honest version of the timed-transfer finding.
4. **Frequency-first base map.** Lines drawn by frequency class (Walker style). Transfer nodes are only highlighted where two frequent lines cross (the "cheap transfer" set). This ties the transfer layer to network structure and makes the GZM result (short walks, long waits) visible at a glance.
5. **City comparison chart.** A stacked bar per city of walk, wait and PTP band at the top nodes. One chart that carries the main finding.
6. **Chord or Sankey diagrams of movements.** Useful only with real flows. Routed-sample flows (planned) would support "which lines feed which" at major nodes, but should be labelled as model output.

### Gaps
- No public interactive example of per-node transfer matrices or line-pair wait strips was found. TfL or SBB station pages may have them; not checked.
- No Polish public example of transfer-dependence maps was found.

## Q7. Cross-check of the project's measure and planned extensions, with implementable recommendations (objectives b and c)

### Takeaway
The project's decomposition (walk, crossings, steps, step-free path, wait, importance) matches the literature's structure (Guo and Wilson; Iseki and Taylor; AMPTI W2, W4 and W6). The directional variant is a sound and literature-consistent fix: Guo and Wilson model movements between platform pairs, not station averages. The weak points are, first, that the published wait is a random-arrival wait rather than a connection wait. Second, nothing translates the components into the time currency the literature uses, so the reader cannot see that a 7-min wait "costs" more than a 2-min walk. Third, the map shows nodes, while the literature's network questions (transfer dependence, frequency at both ends) are about origin–destination reach.

### Cited Findings
- The project's own numbers: top-20 walk 1.5–2.7 min, wait (07–09) 5.2–15.0 min, crossings median 1; 44–73% of line pairs share a stop; coordination test 11–14% against about 10% by chance — [RAPORT.md §20](../../results/RAPORT.md); [transfer.md §3–4](../../results/qa/transfer/transfer.md).
- Walk and wait weights of about 1.5–1.7 and a PTP of 13–18 EIVM, with a lower residual of 5–9 EIVM when mode constants are separated — sources in Q1.
- The project's AMPTI comparison (Kraków, W2 only, 18–25% lower distances) is consistent with W2 being the only directly comparable indicator — [Czekała and Bryniarska 2017](https://yadda.icm.edu.pl/baztech/element/bwmeta1.element.baztech-1b506d14-888a-4ac2-816e-b6d116664788/c/TMiR_6_2017_Czekala.pdf).

### Inferences
Recommendations, in order of value and effort:
1. **Add a generalised transfer time band per movement and node** (Q1 formula; weights from Wardman and Ortelli; PTP 5/13/18). Show it as a range next to the components, with sources in the help text, and do not rank by it. Keep the additivity check.
2. **Publish the connection wait** (wait after the actual feeder arrival plus walk; median and P90) next to the random-arrival wait. The difference between them is the visible effect of coordination, positive or negative. This reuses code from the coordination test.
3. **Replace the crossing count with an AMPTI-W6-style mean per movement** (100 for grade-separated, 60–70 for signalised, 30 for marked, 0 for unmarked) and cite TMiR 6/2017. This gives a published scale without inventing one.
4. **"Frequent × frequent" share:** the share of line-pair movements at a node, and of a city's transfer movements, where both legs run ≤ 10 min (or ≤ 15 min, the SNAMUTS contour rule). This is a plain-language network-structure indicator.
5. **Ship direct-only accessibility as a mapped ratio** (Q3 measure 1; Q6 view 1). This is the single most informative lay output and answers "how much does this city make me change".
6. **Count node use from the routed sample** (planned), and benchmark the share of routed trips with ≥ 1 transfer against Warsaw's WBR 2015 figure of 42.8%. If the routed share is far lower, report that the grid-cell sample is not representative of real trips.
7. **Coordination:** restrict the test to pairs where both legs run every ≥ 15 min, report it per node and mode pair, and add a night-network positive control.
8. **Node click view:** connection matrix plus drawn paths, as in Q6 view 2. This addresses the owner's "works but adds little" criticism more directly than any new metric.
9. **Do not add:** facility indicators from OSM (shelter, displays, tactile paving) as headline values until tag coverage is measured, and mode-specific penalties (Ortelli shows they mostly capture mode preference).

### Gaps
- None of the weights are Polish. Applying British, Spanish, Swiss and Irish values to Polish users is an assumption that should be stated.
- The effect of reliability, the strongest-rated feature in Dublin, cannot be measured without real-time data.
- Whether the owner's planned "network view" should follow SNAMUTS' indicator set exactly was not assessed.
