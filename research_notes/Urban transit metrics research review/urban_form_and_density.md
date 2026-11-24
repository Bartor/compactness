# Urban form, compactness and density: literature measures vs the project's measures

Scope: measures of compactness, density and mono/polycentricity; values for European and Polish cities; transit density thresholds; cross-check of the project's measures (RAPORT.md §14, §16, §19; qa/density/density.md); recommendations. Research date 2026-11-24. Budget-limited review (about 20 tool calls): several standard sources could only be located, not read; these are listed in the Gaps sections and must not be cited as read.

Reading status of the main sources:
- Bertaud & Malpezzi (2003), "The Spatial Distribution of Population in 48 World Cities", working paper dated 17 Dec 2003 — **full text read** (public copy on a university server). Old source; data from the 1990s.
- Angel, Arango Franco, Liu & Blei, "The shape compactness of urban footprints", Progress in Planning (DOI 10.1016/j.progress.2018.12.001; article in press, c. 2019) — **full text read** (Marron Institute copy).
- Angel, Blei, Parent & Civco, "The Decline in Transit-Sustaining Densities in U.S. Cities, 1910–2000", ch. 8 in Ingram & Hong (eds.), *Climate Change and Land Policies*, Lincoln Institute 2011 — **full text read**. Old source.
- Eurostat degree-of-urbanisation manual (2021 edition), OECD *Rethinking Urban Sprawl* (2018), OECD *Urban-Rural Linkages in Poland*, Guerra & Cervero (2011), Schwarz (2010), Polish PAN reports — **search snippets / summaries only, not read in full** (OECD page returned HTTP 403, PAN PDF returned HTTP 502). Marked "(snippet)" below.

Nothing was downloaded into the repository. The PDFs were fetched by the web tool into its session cache only and text-extracted in the scratchpad, so no `data/raw/research/` folder or SOURCE.json was created. No repository file other than this note was touched.

---

## Q1. Which measures of compactness and sprawl are standard today, and what are their pitfalls?

### Takeaway
The core toolbox consists of gross density, population-weighted ("experienced") density, the negative-exponential (Clark) density gradient, Bertaud's dispersion index ρ, Angel's shape-compactness indices (proximity, cohesion, exchange) on a satellite-derived urban extent, the Eurostat/OECD grid-based degree of urbanisation, and multi-dimensional sprawl indices (OECD 2018, and Ewing/Galster in the US). Every one of these depends on how the "built-up area" or "urban extent" is drawn, on the grid size, and, for centre-based measures, on the choice of centre. The literature's own authors warn that centre-based measures lose meaning in polycentric cities, or where the CBD is far from the population's centre of gravity.

### Cited Findings

**Bertaud dispersion index ρ (Bertaud & Malpezzi 2003)**
- Definition: ρ is the ratio between the average distance per person to the CBD and the average distance to the centre of a cylinder whose base equals the built-up area. A city that matches the cylinder has ρ = 1. The authors state they "are not arguing that cylindrical cities are in some sense optimal" (pp. 20–21) — [Bertaud & Malpezzi 2003](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf)
- Built-up area: density is measured in census tracts "net of areas that are not built up such as large parks, lakes, greenbelts, mountains and other rugged terrain" (p. 24). Only *large* open areas are removed, not every low-coverage block — [Bertaud & Malpezzi 2003, p. 24](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf)
- Centre-choice pitfall: in most cities the CBD and the population's centre of gravity coincide, but in some they are far apart. Cracow is named as a monocentric city with an eccentric CBD (alongside Bombay and Curitiba). The authors write that ρ "might have less significance for polycentric cities where the CBD is eccentric" (p. 20) — [Bertaud & Malpezzi 2003](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf)
- Gradient pitfall: negative-exponential density and land-price gradients "require strong assumptions" (footnote, p. 85). Brasilia, Capetown, Moscow and Seoul have inverted gradients over some range (p. 25) — [Bertaud & Malpezzi 2003](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf)
- The sample was "opportunistic", collected city by city by Bertaud over about a decade (p. 24), so the values are not from a harmonised dataset — [Bertaud & Malpezzi 2003](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf)

**Angel et al.: shape compactness of urban footprints (Atlas of Urban Expansion family)**
- Proximity Index (PRX) = average beeline distance from all points of the Equal Area Circle to its centre ÷ average beeline distance from all points of the urban extent to the CBD, "identified by its City Hall". Cohesion Index = the same ratio using the average distance between all pairs of points. Exchange Index = the share of the urban extent inside an Equal Area Circle centred on the extent's centroid. Fullness Index = the share inside a Buildable Land Circle (dry land with slope < 15 %). All indices run from 0 to 1, with 1 = circle (pp. 10–11) — [Angel et al., Progress in Planning](https://marroninstitute.nyu.edu/uploads/content/Shape_Compactness_of_Urban_Footprints.pdf)
- PRX is therefore the land-based (not population-weighted) inverse of Bertaud's ρ. The CBD is fixed at City Hall, which makes the centre choice explicit and reproducible — [Angel et al.](https://marroninstitute.nyu.edu/uploads/content/Shape_Compactness_of_Urban_Footprints.pdf)
- Measured on satellite-derived urban footprints for a stratified global sample of 200 cities in 1990, 2000 and 2014. Shape compactness was found to be independent of city size, area, density and income, strongly affected by topography, and declining overall from 1990 to 2014 (abstract) — [Angel et al.](https://marroninstitute.nyu.edu/uploads/content/Shape_Compactness_of_Urban_Footprints.pdf)
- Few Proximity Index values are low, none below 0.35 (p. 11) — [Angel et al.](https://marroninstitute.nyu.edu/uploads/content/Shape_Compactness_of_Urban_Footprints.pdf)
- Atlas of Urban Expansion 2016, Volume 1 "Areas and Densities" and Volume 2 "Blocks and Roads" (snippet; not read) — [Lincoln Institute, Atlas 2016](https://www.lincolninst.edu/publications/other/atlas-urban-expansion-2016-edition/)

**Eurostat / OECD degree of urbanisation (DEGURBA, 2021 edition)** (snippet)
- Urban centre: contiguous 1 km² cells with ≥ 1,500 inhabitants/km² (4-point contiguity, with gap filling), total population ≥ 50,000. Dense urban cluster: ≥ 1,500/km², 5,000–50,000 inhabitants. Urban cluster: ≥ 300/km² (8-point contiguity), ≥ 5,000 inhabitants — [Eurostat, Applying the Degree of Urbanisation manual](https://ec.europa.eu/eurostat/statistics-explained/index.php/Applying_the_degree_of_urbanisation_manual_-_Methodology_for_applying_level_1_of_the_degree_of_urbanisation_classification)
- Eurostat warns that a higher-resolution grid could fragment single settlements, and that "a small linear park" could split one in two. This is the explicit reason for 1 km cells (snippet) — [Eurostat, Population grids / DEGURBA manual](https://ec.europa.eu/eurostat/statistics-explained/index.php/Population_grids)
- Grid cells of equal shape and area avoid distortions from administrative units of differing size, i.e. they mitigate the MAUP (snippet) — [Eurostat, Population grids](https://ec.europa.eu/eurostat/statistics-explained/index.php/Population_grids)

**OECD multi-dimensional sprawl (Rethinking Urban Sprawl, 2018)** (snippet)
- Urban-form indicators are measured for 1,156 urban areas (FUAs) in 29 OECD countries. Fragmentation of urban land, variation in urban population density and the share of urban land at very low density have grown in most countries since 1990 — [OECD 2018](https://www.oecd.org/en/publications/rethinking-urban-sprawl_9789264189881-en/full-report/component-7.html)

**Gini and polycentricity (already used by the project in QA)**
- Volpati & Barthelemy (2018), arXiv:1804.00855: Gini of cell populations, LouBar hotspot threshold, and η = mean distance between hotspots ÷ mean distance between all cells — [Volpati & Barthelemy](https://arxiv.org/abs/1804.00855)

**European landscape-metric approach**
- Schwarz (2010), *Landscape and Urban Planning* 96(1): 29–47, 231 European cities, CORINE + Urban Audit. Uses landscape and population metrics (e.g. edge density, mean patch size, compactness of the largest patch, population density). Conclusion: a few indicators suffice, because single indicators are strongly inter-correlated (snippet) — [Schwarz 2010, U. Twente record](https://research.utwente.nl/en/publications/urban-form-revisited-selecting-indicators-for-characterising-euro/)

### Inferences
- The project's ρ and the literature's ρ differ in the denominator area. Bertaud nets out only large non-built areas. The project nets out every 100 m cell below 20 % building coverage, which removes parks, river valleys, rail land and open-plan large estates (density.md §4). This is the most likely reason the project gets ρ > 1 almost everywhere: a smaller A gives a smaller ⅔R, and a star-shaped mask gives larger mean distances. The project already says this, correctly.
- Angel's PRX is the closest modern, documented analogue of ρ. It has a fixed, citable centre rule (City Hall) and a published urban-extent method. Adding it would make the project's compactness number citable against a 200-city global sample.
- Pitfalls the literature names, mapped to the project:
  - MAUP / grid size: PWD at 1 km vs 250 m (see Q2).
  - Boundary: FUA vs core. The project's own finding that FUA shares re-rank cities because of FUA size is consistent with the OECD/Eurostat motivation for grids.
  - Threshold: 10/20/30 % built-up.
  - Centre: config centre vs centroid vs City Hall.
  The project already handles the first three well and has not yet handled the fourth (§14.6 lists "sensitivity to centre coordinates" as unverified).

### Gaps
- **Ewing & Hamidi compactness index and Galster et al. (2001) eight sprawl dimensions** (density, continuity, concentration, clustering, centrality, nuclearity, mixed use, proximity): not fetched in this session. They are US-tract-based and can only be described from background knowledge, not cited. Ewing–Hamidi needs street-network and land-use-mix variables, and US calibration makes their index values non-transferable.
- **OECD 2018 exact indicator definitions and Polish values**: the page returned 403. Only the summary statement about Poland (below) was seen.
- Eurostat manual read via the Statistics Explained summary only. Exact page numbers are not verified.
- No source was found that quantifies PWD grid-size dependence across European cities (Ottensmann, Craig and similar were not found). The quantification below comes from the project's own data.

---

## Q2. What do comparative studies report for European and Polish cities (values, rankings, suburbanisation)?

### Takeaway
The only harmonised, citable set of ρ and Clark gradients that includes Polish cities is Bertaud & Malpezzi (2003, data c. 1990s). It gives Warsaw ρ = 0.99 and Cracow ρ = 1.18, with gradients of −0.170 and −0.174 per km. The project's Clark gradients (Warsaw 0.167, Kraków 0.168) are strikingly close to these. The project's FUA ρ (1.40 and 1.46 at 20 %) is higher, while its core ρ at the 10 % threshold (1.05 and 1.18) is close. OECD sources describe Poland as a country of strong, multi-dimensional sprawl since 1990, with an unusually large commuting-zone share of FUA population.

### Cited Findings

**Bertaud & Malpezzi 2003, Table 1 (p. 86 ff.).** Columns: city population, built-up km², people per ha of built-up area, dispersion index, Clark gradient β (per km). Read from the raw text layer. The layout-mode extraction misaligns rows, so the raw-mode row order was used.

| City | Pop. | Built-up km² | p/ha | ρ | Gradient β |
|---|---|---|---|---|---|
| Warsaw | 1,639,675 | 235 | 70 | 0.99 | −0.170 |
| Cracow | 730,600 | 112 | 65 | 1.18 | −0.174 |
| Prague | 1,210,000 | 171 | 71 | 1.22 | −0.113 |
| Berlin | 4,212,381 | 1,176 | 36 | 0.98 | −0.043 |
| Budapest | 1,937,162 | 309 | 63 | 0.96 | −0.105 |
| Riga | 759,255 | 119 | 64 | 1.23 | −0.154 |
| Paris | 7,877,729 | 893 | 88 | 0.89 | −0.097 |
| London | 6,626,272 | 1,062 | 62 | 1.03 | −0.024 |
| Barcelona | 2,775,000 | 163 | 171 | 1.32 | −0.100 |
| Stockholm | 1,426,922 | 400 | 36 | 1.32 | −0.039 |
| Moscow | 8,543,867 | 470 | 182 | 1.39 | +0.047 |

Source: [Bertaud & Malpezzi 2003, Table 1](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf). Warsaw and Cracow are coded as socialist economies, regulation category 1 ("mixed").
- Summary over all cities: mean gradient −0.10, median −0.08, range −0.49 (Guangzhou) to +0.05 (Moscow), N = 47 (Table 2) — [Bertaud & Malpezzi 2003](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf)
- Regulation and natural constraints are the most consistent determinants of ρ; income and population matter much less (abstract/introduction) — [Bertaud & Malpezzi 2003](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf)
- The authors suggest Warsaw's zoning approach could be a model for transition-economy cities (p. 40) and list a separate Bertaud & Bertaud study of the Warsaw metropolitan area in the references — [Bertaud & Malpezzi 2003](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf)

**Project values for comparison** (from RAPORT.md §14 and density.md tables 3, 5, 5a):

| | B&M ρ | Project ρ core, 10 % | Project ρ core, 20 % | Project ρ FUA, 20 % | B&M β | Project Clark b |
|---|---|---|---|---|---|---|
| Warsaw | 0.99 | 1.054 | 1.205 | 1.397 | −0.170 | 0.1665 |
| Kraków | 1.18 | 1.178 | 1.392 | 1.455 | −0.174 | 0.1684 |

**Poland: OECD** (snippets)
- Poland is listed among countries whose cities "have been sprawling along most of the considered dimensions since 1990", with the Czech Republic, Denmark, France, Hungary and Slovakia — [OECD, Rethinking Urban Sprawl 2018](https://www.oecd.org/en/publications/rethinking-urban-sprawl_9789264189881-en/full-report/component-7.html)
- 56 % of Poland's population lives in an FUA (OECD average 66 %). 43 % of FUA residents live in commuting zones (OECD average 25 %). Between 1990 and 2015, core cities lost 8.6 % of their population while semi-dense (suburban) areas grew 5.2 % — [OECD, Urban-Rural Linkages in Poland](https://www.oecd.org/regional/urban-rural-linkages-in-poland-94b5c782-en.htm)
- World Bank Poland snapshot (GHSL-based): only 3 of the 15 largest Polish cities (Warsaw, Kraków, Białystok) grew in 2003–2011; the fastest-growing municipalities were mostly around Warsaw (snippet) — [World Bank, Poland snapshot](https://documents1.worldbank.org/curated/fr/637261511934938547/pdf/121729-BRI-P154478-PUBLIC-Poland-Snapshot-Print.pdf)

**Poland: Polish institutes** (snippets / presentations)
- 2013 report on the economic losses and social costs of uncontrolled urbanisation (Fundacja Rozwoju Demokracji Lokalnej + IGiPZ PAN; Kowalewski, Mordasewicz, Osiatyński, Regulski, Śleszyński). Excess transport costs, including commuting, estimated at about 34 bn PLN/yr for Poland and 1–2 bn PLN for Warsaw. The same material says these sums could be up to half lower — [Śleszyński, IGiPZ PAN presentation](https://www.igipz.pan.pl/tl_files/igipz/ZGMiL/osoby/sleszynski/Sleszynski_ZBP_2015.pdf)
- Expanded version: KPZK PAN, "Studia nad chaosem przestrzennym" (eds. Kowalewski, Markowski, Śleszyński), about 841 pages (snippet) — [Śleszyński, IGiPZ PAN](https://www.igipz.pan.pl/tl_files/igipz/ZGMiL/osoby/sleszynski/3_Sleszynski_KWoM_2014.pdf)
- PAN 2021 monograph on suburbanisation in Poland (KPZK). The chapter by Hołuj & Lityński assesses uncontrolled suburbanisation with morphological indicators: density, continuity, concentration (snippet) — [PAN, Suburbanizacja 2021, contents](https://publikacje.pan.pl//Content/122129/PDF/2021-SUBR-00-Spis.pdf)
- Remote-sensing studies: uneven sprawl in Polish county-rights cities 2006–2012 vs 2012–2018 (CORINE). Urban Atlas 2006/2012/2018 shows the most intense sprawl in southern and south-eastern Poland (snippets) — [Cieślak et al., Remote Sensing 2020 (DOAJ)](https://doaj.org/article/5411d9ba1fb7403cae46534b10498d48); [Land 2021](https://www.mdpi.com/2073-445x/10/12/1291)

### Inferences
- **Clark gradients validate.** The project's b for Warsaw and Kraków lies within 0.004–0.006 per km of Bertaud & Malpezzi's, despite about 25 years and completely different data (census tracts vs GHSL 100 m). This is a strong, citable sanity check and should be stated in the report. (Caveat: the project fits rings 1–25 km of the FUA, while B&M fit tracts of the city's built-up area.)
- **ρ is consistent once the area definitions match.** B&M's Warsaw built-up area is 235 km², and the population is the 1990s city. The project's core mask at 10 % for Warsaw gives ρ 1.05 vs 0.99, and Kraków 1.18 vs 1.18. The FUA value at 20 % is not comparable. Suggested wording: "With a built-up area close to Bertaud's definition (core, 10 % threshold), our values are close to Bertaud & Malpezzi's 1990s values; the FUA/20 % values are higher by construction." This partly revises the project's current statement that the level is "not comparable", which was made without checking the numbers. The match is suggestive, not proof.
- B&M built-up densities of 65–70 p/ha (6,500–7,000 /km²) for Warsaw and Cracow are in the same range as the project's core PWD of 7,500–9,100 /km² (1 km census grid). This is plausible, because PWD exceeds the area-average built-up density.
- The OECD figure of 43 % of FUA population in commuting zones is consistent with the project's large gap between core PWD and FUA PWD and its gross FUA densities of 325–792 /km².

### Gaps
- No recent (post-2015) harmonised ρ, PRX or PWD values for Polish cities were found. The Atlas of Urban Expansion 200-city sample includes no Polish city that could be confirmed: not checked.
- OECD 2018 per-FUA Polish values were not retrieved (403).
- No Polish Economic Institute (PIE) or Institute of Urban and Regional Development (IRMiR) report with comparable density figures was found within budget. The IRMiR and PIE suburbanisation reports were not verified.
- PAN 2021 monograph: abstract PDF returned 502, so no figures were taken from it.

---

## Q3. Density thresholds for viable public transport, and how the project's 2,500 /km² on 250 m cells compares

### Takeaway
Classic thresholds:
- 30–40 persons/ha (3,000–4,000 /km²) as an urban-area average, Newman & Kenworthy.
- 30 p/ha for basic bus and 50 p/ha (5,000 /km²) for frequent bus, Angel et al. 2011 on US census tracts.
- About 30 people + jobs per gross acre (≈ 74 /ha ≈ 7,400 /km²) within station catchments for cost-effective light rail, Guerra & Cervero 2011.
- DEGURBA urban centre: 1,500 /km² on 1 km cells.

Every one of these is defined on a larger and coarser unit than a 250 m cell. A 250 m cell at 2,500 /km² (≈ 156 residents) is therefore a *lenient* threshold relative to the transit literature. It sits between the Eurostat "urban" floor and the classic bus thresholds, and it is not a viability threshold.

### Cited Findings
- Angel et al. (2011): "We concur with Newman and Kenworthy (1989) and Holtzclaw (1994) that a density of approximately 30 persons per hectare is a good rule of thumb for basic bus service". About 50 p/ha "would allow for frequent and attractive bus service" (Orosz 2009). These apply to bus, not rail. Density is measured at census-tract level, and tracts are included only above 1,000 persons/sq mile (3.86 p/ha) (pp. 193, 195) — [Angel, Blei, Parent & Civco 2011](https://www.lincolninst.edu/app/uploads/2024/04/decline-in-transit-sustaining-densities-us-cities_0.pdf)
- The same chapter: "the notion of a density level that is conducive to transit service remains an elusive concept"; "Transit service is possible at any density level" (p. 191). It cites Ewing & Cervero (2010), who found population and job densities only weakly associated with transit use, with proximity to transit and network design more important (p. 192) — [Angel et al. 2011](https://www.lincolninst.edu/app/uploads/2024/04/decline-in-transit-sustaining-densities-us-cities_0.pdf)
- Newman & Kenworthy (1989), as summarised in secondary sources: driving rises markedly below about 20 p/ha and bus service becomes poor below about 30 p/ha. Their later work describes about 35 p/ha of urban intensity (residents + jobs) as where car dependence falls. Mees criticised the density data and found only a weak correlation once it was corrected. Secondary sources give a range of 30–100 p/ha for the threshold (secondary summaries; originals not read) — [Bertaud, Transit US–Europe note](https://courses.washington.edu/gmforum/Readings/Bertaud_Transit_US_Europe.pdf); [Mees critique summary, UTS](https://opus.lib.uts.edu.au/bitstream/10453/11855/1/2009005320.pdf)
- Bertaud: cities with average densities below 30 p/ha have low transit use, under 10 % of trips (secondary summary) — [Bertaud, Transit US–Europe](https://courses.washington.edu/gmforum/Readings/Bertaud_Transit_US_Europe.pdf)
- Guerra & Cervero, "Cost of a Ride", JAPA 77(3): 267–290 (2011). 59 US fixed-guideway investments. Light rail needs about 30 people + jobs per gross acre around stations to be cost-effective, and heavy rail about 50 % more. A US DOT summary gives light rail as more cost-effective than heavy rail up to 28 jobs + people per gross acre. Most sampled stations had fewer than 19 jobs + persons per acre (summaries; article not read) — [Berkeley ITS working paper](https://escholarship.org/content/qt3mb598qr/qt3mb598qr.pdf?t=q9uqt6); [US DOT spotlight](https://www.transportation.gov/sites/dot.gov/files/docs/spotlight_1211_0.pdf); [RePEc record](https://ideas.repec.org/a/taf/rjpaxx/v77y2011i3p267-290.html)
- Pushkarev & Zupan (1977), *Public Transportation and Land Use Policy*. Cited as the start of modern transit–density research (Angel et al. 2011, p. 191), but its thresholds (usually quoted in dwelling units per acre) were not verified here — [Angel et al. 2011](https://www.lincolninst.edu/app/uploads/2024/04/decline-in-transit-sustaining-densities-us-cities_0.pdf)
- DEGURBA urban centre: ≥ 1,500 /km² on 1 km cells (snippet) — [Eurostat manual](https://ec.europa.eu/eurostat/statistics-explained/index.php/Applying_the_degree_of_urbanisation_manual_-_Methodology_for_applying_level_1_of_the_degree_of_urbanisation_classification)

### Inferences (grid-size reasoning, own)
- **Unit conversion:** 1 p/ha = 100 /km². The project's 2,500 /km² = 25 p/ha, below the 30 p/ha "basic bus" figure and half the 50 p/ha "frequent bus" figure.
- **Grid effect:**
  - A census tract or US urbanised-area average includes streets, small parks and non-residential plots.
  - A 250 m cell (6.25 ha) can be almost purely residential, so the same population gives a higher cell density.
  - Hence a 250 m cell threshold should be *higher* than an area-average threshold to mean the same thing, not lower.
  - The project's own data shows the size of the effect. On the same GHSL source, PWD on 250 m cells exceeds PWD on 1 km cells by about 28 % in Warsaw FUA (6,399 vs 4,987) and about 33 % in Kraków FUA (4,524 vs 3,405) (density.md tables 1–2).
  - Roughly, 2,500 /km² on 250 m cells corresponds to about 2,000 /km² on 1 km cells. This is close to the DEGURBA 1,500 "urban" floor, not to a transit-viability level.
- **Who is in the class:** the class "dense cells (≥ 2,500) without service every 20 min" will contain many cells of detached-house suburbs at ~25–40 p/ha. The literature would call these marginal for basic bus, not dense neglected areas. The headline "dense areas without frequent transit" can therefore overstate the problem in GZM and the suburbs.
- **Minimal fix:**
  - Rename the class "built-up residential areas (≥ 25 residents/ha on 250 m cells)" or similar.
  - Add a sensitivity table at 1,500 / 2,500 / 5,000 / 7,500 /km². These cite DEGURBA, the project's own threshold, Angel/Orosz "frequent bus", and Guerra–Cervero "light rail incl. jobs".
  - Or show the share without frequent service as a continuous curve against the density threshold.
  - The 10,000 /km² class (100 p/ha) is defensible as "high density" by all of these sources.
- **Mixed vs residential-only measures:** Guerra–Cervero and Newman–Kenworthy "intensity" count jobs as well as residents. The project's measure is residents only. A jobs layer exists (Goliszek, RAPORT §7) but covers only core cities, so any comparison with those thresholds must say "residents only".

### Gaps
- No European empirical study of residential-density thresholds for frequent service was found within budget. Possible leads not checked: UK "Buses in Urban Developments" guidance, Swiss ÖV-Güteklassen, Dutch work. These are candidates, not verified.
- Original Newman & Kenworthy (1989) and Pushkarev & Zupan (1977) texts were not read. Thresholds are given via secondary summaries, with unit ambiguity noted in the sources (one secondary text confuses per ha and per acre).

---

## Q4. Additional measures and visualisation for these seven agglomerations with the data at hand

### Takeaway
The highest-value additions are:
1. A population-weighted density distribution, i.e. the share of residents by density class. It generalises PWD and is grid-robust when presented with the grid stated.
2. A DEGURBA-style share of FUA population in urban centre / urban cluster / rural cells computed on the census grid, directly comparable with Eurostat and OECD.
3. Angel's Proximity Index on a GHSL urban extent, with the City Hall centre.
4. A centre-sensitivity check, plus the CBD offset from the population's centre of gravity.
5. Explicit citation of the Bertaud & Malpezzi gradients and ρ as an external check.

For lay audiences:
- small multiples of absolute cumulative-population profiles (already recommended by the project);
- population-weighted density histograms;
- 2D maps rather than 3D.

### Cited Findings (bases for the recommendations)
- DEGURBA thresholds and contiguity rules (1 km, 1,500/300 /km², 50,000/5,000), as in Q1 — [Eurostat manual](https://ec.europa.eu/eurostat/statistics-explained/index.php/Applying_the_degree_of_urbanisation_manual_-_Methodology_for_applying_level_1_of_the_degree_of_urbanisation_classification)
- OECD tracks the share of urban land at very low density and the variation of density as sprawl dimensions (snippet) — [OECD 2018](https://www.oecd.org/en/publications/rethinking-urban-sprawl_9789264189881-en/full-report/component-7.html)
- Angel's PRX, Cohesion, Exchange and Fullness definitions with City Hall as CBD; buildable land = dry land with slope < 15 % (SRTM) — [Angel et al.](https://marroninstitute.nyu.edu/uploads/content/Shape_Compactness_of_Urban_Footprints.pdf)
- B&M: ρ is meaningful for monocentric cities and for polycentric ones where CBD and centre of gravity coincide (p. 20). This is a reason to report the offset — [Bertaud & Malpezzi 2003](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf)
- B&M represent a city as a three-dimensional object: built-up area surface, its shape, and the density distribution within it (p. 19, Figure 6 cylinder). This is the conceptual basis for "profile + map" presentation — [Bertaud & Malpezzi 2003](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf)
- Volpati & Barthelemy η and LouBar hotspots as a polycentricity measure — [Volpati & Barthelemy 2018](https://arxiv.org/abs/1804.00855)

### Concrete recommendations (own, each tied to a source above)
1. **Density distribution chart (main graphic candidate).**
   - Content: the share of residents living in 250 m cells of density class < 1,000 / 1,000–2,500 / 2,500–5,000 / 5,000–10,000 / ≥ 10,000 /km², as stacked horizontal bars for 7 FUAs and 7 cores. Use the census-rescaled grid.
   - Why: it shows the whole distribution that PWD summarises, and it is the population-side counterpart of OECD's "share of urban land at very low density".
   - Companion: a land-side version (share of built-up area by density class) next to it.
   - Basis: OECD 2018; PWD definition.
2. **DEGURBA population shares** on the census 1 km grid: urban centre / dense cluster / semi-dense / suburban-or-peri-urban / rural, per FUA.
   - Directly comparable with Eurostat and the OECD figure of 43 % in commuting zones, and cheap to compute.
   - Basis: Eurostat manual.
3. **Proximity Index (Angel).**
   - Urban extent from GHS-BUILT-S, e.g. the 10 % threshold with small-gap filling. Centre = City Hall (Urząd Miasta). Report land-based PRX and, separately, population-weighted 1/ρ on the same extent.
   - This replaces an idiosyncratic net mask with a published, citable definition.
   - Basis: Angel et al.
4. **Centre sensitivity and offset.**
   - Recompute ρ, r50 and the profiles with (a) the config centre, (b) City Hall, (c) the population-weighted centroid.
   - Report the CBD-to-centroid distance. B&M flag Cracow as eccentric, so this is a known issue for Kraków.
   - Basis: B&M p. 20.
5. **External check table:** Clark gradient and ρ (core, 10 %) next to B&M Table 1 for Warsaw and Kraków (see Q2), with era and data caveats.
6. **Polycentricity for GZM / Trójmiasto:**
   - Promote η (Volpati & Barthelemy) and a hotspot count from QA to the table tier.
   - Add a rank-size plot of hotspot clusters (contiguous LouBar cells), which shows GZM's several comparable peaks against a single dominant peak in Warsaw.
   - Basis: Volpati & Barthelemy 2018.
7. **Change over time (suburbanisation).**
   - GHSL multitemporal (1990–2020) PWD, built-up area and r50 per FUA, using GHSL as is, since there is no census grid for earlier years. Say plainly that these are modelled data.
   - Polish 2011 census grid data, if a 1 km grid exists for 2011, would give a census-to-census comparison. Not verified that a 2011 1 km grid is available.
   - Basis: OECD sprawl-since-1990 framing; Angel 1990–2014 framework.
8. **Visualisation notes for lay audiences** (inference; no source on visual efficacy was read):
   - Small multiples with a shared y-axis for the absolute cumulative profile.
   - One annotated "typical resident" density marker, the median of the population-weighted distribution.
   - Avoid 3D density towers (they hide occlusion and exaggerate peaks), or confine them to one illustrative city.
   - Use maps of the same 250 m classes as the histogram, with the same colours.

### Gaps
- No peer-reviewed source on lay-audience comprehension of density visualisations was consulted.
- Availability of a 2011 Polish 1 km census grid was not checked.

---

## Q5. What would an urban-form researcher criticise, and what is the minimal fix?

### Takeaway
The likely criticisms are:
(1) The ρ mask is far stricter than Bertaud's built-up area, which makes ρ uninterpretable against the literature. Fix: use a published urban-extent definition and report PRX.
(2) ρ, the profiles, r50, Clark, Gini and η use raw GHS-POP, which the project itself showed misallocates 16–26 % of people at 1 km. Fix: switch to the census-rescaled grid already built in phase 2.
(3) The 2,500 /km² "dense" class is low relative to transit literature and unanchored. Fix: rename and add a threshold sensitivity table.
(4) There is no centre sensitivity. Fix: the City Hall and centroid variants.
(5) The 1 km PWD (headline) and the 250 m measures (layer) sit side by side. Fix: always state the grid, and never place them on one chart.

### Cited Findings
- B&M net only *large* open areas (p. 24). The project's mask keeps only 100 m cells with ≥ 20 % building coverage and covers just 46–73 % of FUA population at 20 % (density.md table 5) — [Bertaud & Malpezzi 2003](https://www2.lawrence.edu/fast/finklerm/Complete%20Spatial%20Distribution%20of%20Population%20in%2050%20World%20Ci.pdf); project density.md §4.
- Angel's urban extent and Equal Area Circle method provide a published alternative with a fixed CBD rule — [Angel et al.](https://marroninstitute.nyu.edu/uploads/content/Shape_Compactness_of_Urban_Footprints.pdf)
- Grid-based methods are preferred to administrative units to limit the MAUP, and the grid resolution choice is explicit in Eurostat's method (snippet) — [Eurostat, Population grids](https://ec.europa.eu/eurostat/statistics-explained/index.php/Population_grids)
- Transit thresholds are defined on tracts or areas and range from 30 to 50 p/ha for bus up to about 74 p/ha (people + jobs) for light rail — [Angel et al. 2011](https://www.lincolninst.edu/app/uploads/2024/04/decline-in-transit-sustaining-densities-us-cities_0.pdf); [Guerra & Cervero summaries](https://escholarship.org/content/qt3mb598qr/qt3mb598qr.pdf?t=q9uqt6)
- Density's effect on transit use is contested: Ewing & Cervero (2010) found it weak compared with proximity to transit and network design (as cited in Angel et al. 2011, p. 192) — [Angel et al. 2011](https://www.lincolninst.edu/app/uploads/2024/04/decline-in-transit-sustaining-densities-us-cities_0.pdf)

### Inferences: point-by-point cross-check of current measures

| Project measure | Status vs literature | Risk of misleading | Minimal fix |
|---|---|---|---|
| Gross density (FUA, core) | Standard but widely discounted; depends on boundary | Low (already used only as contrast) | None |
| PWD on 1 km census grid | Standard; grid-dependent (MAUP) | Medium if compared with 250 m or GHSL figures (already forbidden in text) | State "1 km census grid" on every chart; add the density-distribution chart |
| ρ, one centre, 20 % net mask, FUA | Standard measure, non-standard area definition | High: ρ > 1 everywhere reads as "sprawling" against literature values around 1 | Report core at 10 % (matches B&M for Warsaw and Kraków) or PRX on a published urban extent; keep 20 % in QA |
| ρ to nearest of N centres | Non-standard, reasonable for GZM; denominator inconsistent (½ of A vs N circles) | Medium | Keep as "other measure" (already done); prefer η or hotspots for polycentricity |
| r50 and cumulative profiles | Standard descriptive; centre-dependent | Low to medium | Add centre sensitivity; use census-rescaled grid |
| Clark gradient (table only) | Standard; agrees with B&M within 0.006/km | Low | Promote to table with B&M comparison |
| Gini, η (QA) | Published method (Volpati & Barthelemy) | Low | Promote η to table for polycentric cities |
| Density × frequency (≥ 2,500 /km², 250 m, 500 m walk, 20 min) | Novel layer; threshold lower than any cited transit threshold | Medium to high: "dense areas without transit" may mostly be low-density suburbs | Rename; add 1,500/5,000/7,500 sensitivity; note residents only, no jobs |
| Spearman rank correlation density vs frequency | Reasonable descriptive | Low | Note the grid (250 m) and ties (3 service classes give many ties) |

Other inferences:
- Data-source consistency: phase 1 profiles and ρ use raw GHS-POP 100 m, while phase 2 moved to a census-rescaled grid. A reviewer will ask why compactness uses the source the project itself found biased (it under-represents large housing estates and over-represents centres and industry). The effect on r50 is small (≤ 3–4.5 pp on the cumulative curve, density.md table 4), but the effect on ρ and Gini is unknown. The minimal fix is to rerun on the rescaled grid and report the difference.
- Seven agglomerations, two of them polycentric: rankings among them will be fragile. The project's own Spearman 0.90 → −0.09 across thresholds shows this. Present ρ ranks only with the threshold stated, or present no ranks.

### Gaps
- No reviewer-style critique of Polish compactness studies was found to compare against.
- The effect of the centre choice on the project's ρ was not computed. This is a recommendation, not a finding.
