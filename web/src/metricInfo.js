// What each metric means, for the "?" next to it. `read` comes first and says how to understand the number;
// `method` says how it was computed. `better` is the direction used for "where the city stands" ('higher',
// 'lower' or null when the number is not a quality). `layer` is the map layer that shows the same thing cell by
// cell, when there is one. Texts are Polish UI copy; keep them short and concrete.

export const METRIC_GROUPS = [
  { id: 'size', title: 'Wielkość i gęstość', metrics: ['area', 'population_census', 'density_gross', 'pwdens_census_1km'] },
  {
    id: 'form', title: 'Forma miasta',
    metrics: ['rho_t20', 'rho_nearest_t20', 'profile_r50_km', 'share_residents_ge5000',
      'median_resident_density_250m', 'degurba2021_share_urban_centre'],
  },
  { id: 'poly', title: 'Kilka ośrodków czy jeden', metrics: ['poly_eta_mask_t20', 'hotspots_n', 'hotspots_largest_share'] },
  {
    id: 'supply', title: 'Oferta komunikacji',
    metrics: ['vkm_per_cap_day_total', 'tram_speed_median', 'tram_speed_sched_am_peak', 'tram_speed_sched_evening',
      'tram_vkm_share_below15_am_peak', 'tram_time_above_free_running_s_per_km_am_peak',
      'freq_seg_net_le5min', 'freq_seg_net_le10min',
      'freq_seg_net_le15min', 'freq_seg_net_le20min', 'freq_seg_net_le30min', 'rail_ge4dph_net_1km'],
  },
  { id: 'match', title: 'Gęstość a oferta', metrics: ['dxs_dense_underserved_share', 'dxs_rank_correlation'] },
  {
    // each headline (ratio of means, compared between cities) is followed by the value for a typical resident
    id: 'reach', title: 'Co można osiągnąć',
    metrics: ['tp_pt_am_30min_ratio_of_means', 'tp_pt_am_30min', 'tp_pt_am_45min_ratio_of_means', 'tp_pt_am_45min',
      'tp_walk_30min_ratio_of_means', 'tp_walk_30min', 'tp_bike_lts3_30min_ratio_of_means', 'tp_bike_lts3_30min',
      'tp_bike_lts4_30min_ratio_of_means', 'tp_bike_lts4_30min'],
  },
  {
    // comparison only: the rules of the DG REGIO grid study, urban-centre area
    id: 'eu', title: 'Porównanie z miastami UE',
    metrics: ['tp_gridstudy_pt_30min', 'tp_gridstudy_dgregio_30min', 'tp_gridstudy_pt_45min', 'tp_gridstudy_dgregio_45min'],
  },
  {
    id: 'distribution', title: 'Kto ma słaby dostęp',
    metrics: ['dist_below_floor_pt_am_30min', 'dist_fgt1_pt_am_30min', 'dist_below_floor_pt_am_45min',
      'dist_p25_pt_am_30min', 'dist_p75_pt_am_30min', 'dist_below_floor_pt_evening_30min',
      'dist_below_floor_pt_saturday_30min'],
  },
  {
    // the emergency-department measures are in the tables only (register gaps in GZM), see merge_metrics
    id: 'services', title: 'Kto i do czego: wiek i szkoły',
    metrics: ['age_freq_le10min_age0_14', 'age_freq_le10min_age65', 'age_tp_pt_am_30min_age0_14',
      'age_tp_pt_am_30min_age65', 'svc_school_pt_am_le20min', 'svc_school_pt_am_le30min',
      'svc_school_pt_am_le30min_age0_14'],
  },
  {
    id: 'transfer', title: 'Przesiadki',
    metrics: ['transfer_top20_walkwait_w_am_mean_min', 'transfer_top20_walk_w_am_mean_min',
      'transfer_top20_wait_w_am_mean_min', 'transfer_top20_connwait_w_am_mean_min',
      'transfer_top20_connwait_am_p90_min', 'transfer_top20_gtt_low_am_min', 'transfer_top20_gtt_high_am_min',
      'transfer_crossing_w6_hi_mean_pct', 'transfer_movements_freq15_share', 'transfer_dep_share_walkdir_le2min',
      'transfer_dependence_pt_am_30min_ratio_of_sums', 'tp_pt_am_direct_30min',
      'transfer_dependence_pt_am_45min_ratio_of_sums', 'tp_pt_am_direct_45min'],
  },
]

// One sentence of uncertainty under every headline reach figure.
const UNCERTAINTY = 'Niepewność: wybór danych o ludności przesuwa wynik niektórych miast o 3–7 punktów, a w publikowanych '
  + 'badaniach wyniki liczone z rozkładów są zwykle o 5–15 % lepsze niż w rzeczywistości (tu tego nie mierzono).'
const RATIO_OF_MEANS = 'Liczone jak w DG REGIO: suma osób osiągalnych ze wszystkich komórek 250 m, ważona ich ludnością, '
  + 'podzielona przez taką samą sumę osób mieszkających w promieniu (stosunek średnich).'
const MEAN_OF_RATIOS = 'Średnia wartości poszczególnych komórek 250 m, ważona ich ludnością (średnia stosunków). W rdzeniu '
  + 'miasta różni się od wiersza powyżej najwyżej o ok. 3 punkty; w obszarze z przedmieściami bywa niższa o 10 i '
  + 'więcej punktów, bo słabszy wynik mieszkańców przedmieść liczy się tu tak samo jak wynik mieszkańców centrum.'

/** The headline (ratio of means) and the typical-resident row (mean of ratios) of one reach measure. */
const reach = ({ short, what, radius, layer, method }) => ({
  headline: {
    short,
    better: 'higher',
    ...(layer ? { layer } : {}),
    read: [
      `Jaką część wszystkich par „mieszkaniec – osoba mieszkająca w promieniu ${radius}” da się pokonać ${what}. `
      + 'Tę liczbę porównujemy między miastami.',
      UNCERTAINTY,
    ],
    method: [method, RATIO_OF_MEANS],
  },
  typical: {
    // "(typowy mieszkaniec)", folded into an existing bracket when the name already ends with one
    short: short.endsWith(')') ? `${short.slice(0, -1)}, typowy mieszkaniec)` : `${short} (typowy mieszkaniec)`,
    better: 'higher',
    ...(layer ? { layer } : {}),
    read: [
      `Jaką część ludzi mieszkających w promieniu ${radius} typowy mieszkaniec osiągnie ${what}. Ta sama miara co `
      + 'wiersz powyżej, ale każda komórka liczy się swoim wynikiem, więc to wartość dla przeciętnej osoby, a nie dla '
      + 'wszystkich połączeń razem.',
    ],
    method: [method, MEAN_OF_RATIOS],
  },
})

const PT_METHOD = 'Silnik R5, środa 7:00–9:00, mediana z odjazdów co minutę, dojście do przystanku do 1 km; czasy z '
  + 'rozkładu, bez opóźnień. Mianownik: ludność w promieniu odpowiadającym 15 km/h w linii prostej.'
const PT30 = reach({
  short: 'Zasięg komunikacją w 30 min', what: 'komunikacją i pieszo w 30 minut w porannym szczycie', radius: '7,5 km',
  layer: 'transport_performance_30', method: PT_METHOD,
})
const PT45 = reach({
  short: 'Zasięg komunikacją w 45 min', what: 'komunikacją i pieszo w 45 minut w porannym szczycie', radius: '11,25 km',
  method: PT_METHOD,
})
const WALK = reach({
  short: 'Zasięg pieszo w 30 min', what: 'pieszo w 30 minut', radius: '2,5 km',
  method: 'Silnik R5, 5 km/h po sieci pieszej OpenStreetMap. Rzeki, tory i brak przejść obniżają wynik.',
})

const freq = (n) => ({
  short: `Kursy co ≤ ${n} min w zasięgu 500 m`,
  better: 'higher',
  layer: 'frequent_transport',
  read: [
    `Odsetek mieszkańców, którzy mają w zasięgu 500 m pieszo przystanek z kursami co ${n} minut lub częściej `
    + '(średnio między 6:00 a 20:00 w dzień roboczy).',
    'Im wyższy, tym więcej osób może korzystać z komunikacji bez sprawdzania rozkładu. Liczy się tylko obszar, '
    + 'dla którego mamy rozkłady jazdy.',
  ],
  method: [
    'Odstęp między kursami liczony dla zespołu przystanków i kierunku z rozkładu na środę 2026-11-25; zasięg 500 m '
    + 'po sieci pieszej OpenStreetMap; ludność ze spisu 2021 w komórkach 250 m.',
  ],
})

const bike = (lts, streets) => {
  const r = reach({
    short: `Zasięg rowerem w 30 min (${streets})`, what: `rowerem w 30 minut, jadąc ${streets}`, radius: '7,5 km',
    method: `Silnik R5, 15 km/h, ulice o poziomie stresu rowerowego (LTS) do ${lts}. Poziom stresu wynika z tagów `
      + 'OpenStreetMap, więc jest przybliżony.',
  })
  r.headline.read.splice(1, 0, 'Porównanie obu wersji rowerowych pokazuje, ile zasięgu zależy od jazdy po ruchliwych ulicach.')
  return r
}
const BIKE3 = bike(3, 'tylko po spokojnych ulicach i drogach rowerowych')
const BIKE4 = bike(4, 'także po ruchliwych ulicach')

const dependence = (t, layer) => ({
  short: `Zasięg ${t} min wymagający przesiadki`,
  better: null,
  ...(layer ? { layer } : {}),
  read: [
    `Jaka część tego, do czego mieszkaniec dojedzie komunikacją i pieszo w ${t} minut, wymaga zmiany linii: bez `
    + 'przesiadki (jednym przejazdem albo pieszo) tych osób nie osiągnie w tym czasie.',
    'Niska wartość znaczy, że linie bezpośrednie albo spacer pokrywają prawie wszystko. Nie jest to ocena: dużo '
    + 'przesiadek może oznaczać dobrze połączoną sieć. Gdzie udział wynosi 0, zwykle zasięg pokrywa sam spacer.',
  ],
  method: [
    'Wynik główny porównany z wariantem z co najwyżej jednym przejazdem (R5, środa 7:00–9:00); 1 − osiągalni bez '
    + 'przesiadki / osiągalni, z sum ważonych ludnością komórek. Czasy z rozkładu.',
  ],
})

const direct = (t) => ({
  short: `Zasięg w ${t} min bez przesiadek`,
  better: 'higher',
  read: [
    `Jaką część ludzi z okolicy typowy mieszkaniec osiągnie w ${t} minut jednym przejazdem albo pieszo, bez zmiany `
    + 'linii. Różnica do zasięgu z przesiadkami pokazuje, ile dają przesiadki.',
  ],
  method: ['Jak zasięg komunikacją (średnia komórek ważona ludnością), z co najwyżej jednym przejazdem.'],
})

const FLOOR_METHOD = 'Próg to połowa mediany siedmiu miast: dla każdego rdzenia liczymy medianę wyniku komórek '
  + '250 m ważoną ludnością (szczyt poranny), z siedmiu median bierzemy środkową i dzielimy przez dwa (30 min: 16 %, '
  + '45 min: 28 %). Ten sam próg obowiązuje w każdym mieście i o każdej porze, więc odsetki można porównywać. To '
  + 'wybór normatywny, wzorowany na względnej granicy ubóstwa (50 % mediany dochodu); w tabelach są też progi 40 % i '
  + '60 % mediany. Komórki poza zasięgiem danych o rozkładach są pomijane, nie liczone jako zero.'

const SVC_PT = 'Silnik R5, środa 7:00–9:00, mediana z odjazdów co minutę, dojście do przystanku do 1 km; nie gorzej '
  + 'niż pieszo. Czas do najbliższej placówki danego rodzaju, od środka komórki 250 m do punktu placówki. Tylko '
  + 'obszar, dla którego mamy rozkłady jazdy.'
const SCHOOL_SRC = 'Szkoły: rejestr RSPO (stan 2026-11-24): licea ogólnokształcące, technika i szkoły branżowe I '
  + 'stopnia dla młodzieży, bez szkół specjalnych, bez szkół bez uczniów i bez szkół w zakładach poprawczych; położenie siedziby według rejestru.'
const SOR_SRC = 'Szpitalne oddziały ratunkowe z rejestru RPRM (stan 2026-11-24), bez SOR dziecięcych; położenie: '
  + 'adres z rejestru dopasowany do adresu w OpenStreetMap, nie wejście na oddział.'
const school = (t) => ({
  short: `Szkoła ponadpodstawowa w ${t} min`,
  better: 'higher',
  layer: 'time_to_school',
  read: [
    `Odsetek mieszkańców, którzy dojadą komunikacją z dojściem pieszym do najbliższego liceum, technikum albo `
    + `szkoły branżowej w ${t} minut lub szybciej w porannym szczycie.`,
    'Najbliższa szkoła nie musi być tą, do której dziecko chodzi: rejonów ani profili szkół nie uwzględniono.',
  ],
  method: [SVC_PT, SCHOOL_SRC],
})
const sor = (t, win) => ({
  short: `SOR w ${t} min${win ? ` (${win})` : ''}`,
  better: 'higher',
  layer: 'time_to_sor',
  read: [
    `Odsetek mieszkańców, którzy dojadą komunikacją z dojściem pieszym do najbliższego szpitalnego oddziału `
    + `ratunkowego w ${t} minut lub szybciej${win ? `, ${win}` : ' w porannym szczycie'}.`,
    'To miara dostępności oddziału dla odwiedzających i pacjentów w stanie niewymagającym karetki; w nagłych '
    + 'wypadkach liczy się dojazd ratownictwa, którego tu nie mierzymy.',
  ],
  method: [SVC_PT, SOR_SRC],
})
const ageNote = 'Wiek ze spisu 2021 w kwadratach 1 km rozdzielony na komórki 250 m według liczby mieszkańców; '
  + 'wewnątrz kwadratu 1 km udział grupy jest wszędzie taki sam, więc różnice między grupami pochodzą tylko z różnic '
  + 'między kwadratami. Różnice poniżej 1 punktu nie są interpretowane.'

export const METRIC_INFO = {
  area: {
    short: 'Powierzchnia',
    better: null,
    read: [
      'Powierzchnia obszaru w podanych granicach. Sama nic nie mówi o mieście; pomaga pamiętać, że granice miast '
      + 'obejmują bardzo różną ilość przedmieść, pól i lasów.',
    ],
    method: ['Pole granicy: obszar funkcjonalny Eurostatu albo granica administracyjna miasta.'],
  },
  population_census: {
    short: 'Ludność (spis 2021)',
    better: null,
    read: ['Liczba mieszkańców w podanych granicach. Punkt odniesienia dla wszystkich udziałów procentowych.'],
    method: ['Suma komórek siatki spisowej 1 km (GUS, NSP 2021, ludność rezydująca) wewnątrz granicy.'],
  },
  density_gross: {
    short: 'Gęstość brutto',
    better: null,
    read: [
      'Mieszkańcy podzieleni przez całą powierzchnię, razem z lasami, polami i wodą.',
      'Zależy głównie od tego, jak narysowano granicę, więc nie nadaje się do porównywania miast. Pokazujemy ją '
      + 'dla kontrastu z gęstością ważoną populacją.',
    ],
    method: ['Ludność ze spisu podzielona przez powierzchnię obszaru.'],
  },
  pwdens_census_1km: {
    short: 'Gęstość ważona populacją',
    better: 'higher',
    layer: 'density_250m',
    read: [
      'Gęstość, w jakiej mieszka przeciętny mieszkaniec, a nie przeciętny hektar. Puste tereny w granicach jej nie '
      + 'zaniżają.',
      'Wyższa wartość oznacza, że więcej ludzi mieszka w zwartej zabudowie. To najlepsza pojedyncza liczba do '
      + 'porównania zwartości miast.',
    ],
    method: [
      'Średnia gęstości komórek siatki spisowej 1 km, ważona liczbą mieszkańców komórki. Wynik zależy od wielkości '
      + 'komórki, więc nie porównywać z liczbami liczonymi na innej siatce.',
    ],
  },
  rho_t20: {
    short: 'Rozproszenie wokół centrum (indeks Bertauda)',
    better: 'lower',
    read: [
      'Jak daleko od centrum mieszkają ludzie w porównaniu z miastem, w którym ludność jest rozłożona równomiernie '
      + 'na kole o tej samej powierzchni zabudowy.',
      '1 oznacza rozkład równomierny, poniżej 1 ludność skupioną bliżej centrum, powyżej 1 rozproszoną albo '
      + 'skupioną w kilku ośrodkach. Dla GZM i Trójmiasta miara względem jednego centrum jest mało miarodajna.',
    ],
    method: [
      'Średnia odległość mieszkańca od centrum podzielona przez średnią odległość w kole o powierzchni terenów '
      + 'zabudowanych. Zabudowane są komórki z co najmniej 20 % powierzchni zabudowy według GHSL.',
    ],
  },
  rho_nearest_t20: {
    short: 'Rozproszenie wokół najbliższego z centrów',
    better: 'lower',
    read: [
      'Ten sam indeks Bertauda, ale odległość liczona do najbliższego z kilku centrów. Ma sens dla obszarów z kilkoma '
      + 'ośrodkami: GZM, Trójmiasta, Bydgoszczy i Torunia.',
    ],
    method: ['Jak indeks Bertauda, z listą centrów z konfiguracji projektu zamiast jednego punktu.'],
  },
  profile_r50_km: {
    short: 'Promień obejmujący połowę ludności',
    better: 'lower',
    read: [
      'Promień koła wokół centrum, w którym mieszka połowa ludności obszaru. Mniejszy oznacza miasto bardziej '
      + 'skupione.',
      'Zależy od wielkości miasta, więc porównywać miasta podobnej wielkości.',
    ],
    method: ['Z profilu skumulowanej ludności według odległości od centrum; ludność ze spisu 2021 rozłożona na komórki 100 m.'],
  },
  vkm_per_cap_day_total: {
    short: 'Kilometry kursów na mieszkańca na dobę',
    better: 'higher',
    read: [
      'Ile kilometrów przejeżdżają w ciągu doby wszystkie pojazdy komunikacji w przeliczeniu na mieszkańca '
      + '(w branży: wozokilometry).',
      'Więcej oznacza większą ofertę, ale nie mówi, czy kursy są tam, gdzie mieszkają ludzie, ani ile miejsc mają '
      + 'pojazdy.',
    ],
    method: [
      'Suma długości kursów z rozkładów na środę 2026-11-25 wewnątrz obszaru, podzielona przez ludność. Tramwaj, '
      + 'autobus, kolej i metro razem.',
    ],
  },
  tram_speed_median: {
    short: 'Prędkość komunikacyjna tramwajów',
    better: 'higher',
    read: [
      'Jak szybko tramwaj pokonuje trasę według rozkładu, razem z postojami na przystankach. To prędkość planowana, '
      + 'nie rzeczywista.',
      'Różnica 1–2 km/h między miastami jest duża. Na wynik wpływa też rozstaw przystanków.',
    ],
    method: [
      'Dla każdego kursu długość trasy podzielona przez czas od pierwszego odjazdu do ostatniego przyjazdu; mediana '
      + 'po kursach w środę 2026-11-25.',
    ],
  },
  tram_speed_sched_am_peak: {
    short: 'Prędkość tramwajów w szczycie (7–9)',
    better: 'higher',
    read: [
      'Jak szybko tramwaje jeżdżą według rozkładu w porannym szczycie, z postojami na przystankach. To prędkość '
      + 'planowana, nie zmierzona.',
      'Porównaj z wierszem „wieczorem”: różnica pokazuje, ile rozkład dolicza na ruch i tłok w szczycie.',
    ],
    method: ['Długość trasy podzielona przez czas przejazdu z rozkładu, razem z postojami na przystankach, dla wszystkich kursów tramwajów w danym paśmie godzin (środa 2026-11-25); kurs należy do pasma według godziny pierwszego odjazdu. To suma kilometrów podzielona przez sumę godzin, więc linie z wieloma kursami ważą więcej.'],
  },
  tram_speed_sched_evening: {
    short: 'Prędkość tramwajów wieczorem (20–23)',
    better: 'higher',
    read: [
      'Ta sama prędkość z rozkładu, ale dla kursów zaczynających się między 20:00 a 23:00, gdy ulice są puste, '
      + 'a wymiana pasażerów krótka.',
      'Jeśli wieczorem jest wyraźnie szybciej niż w szczycie (we Wrocławiu o ok. 1,7 km/h), to w szczycie tramwaje '
      + 'tracą czas na skrzyżowaniach i przystankach, a nie na samej trasie.',
    ],
    method: ['Długość trasy podzielona przez czas przejazdu z rozkładu, razem z postojami na przystankach, dla wszystkich kursów tramwajów w danym paśmie godzin (środa 2026-11-25); kurs należy do pasma według godziny pierwszego odjazdu. To suma kilometrów podzielona przez sumę godzin, więc linie z wieloma kursami ważą więcej.'],
  },
  tram_vkm_share_below15_am_peak: {
    short: 'Jazda tramwajów poniżej 15 km/h',
    better: 'lower',
    read: [
      'Jaka część kilometrów przejeżdżanych przez tramwaje w porannym szczycie przypada na odcinki, na których '
      + 'rozkład zakłada mniej niż 15 km/h. To odcinki, gdzie tramwaj jedzie wolniej niż rowerzysta.',
      'Niżej znaczy lepiej. Liczą się odcinki o czasie przejazdu co najmniej 5 minut; krótsze są zbyt wrażliwe na '
      + 'zaokrąglenie rozkładu do pełnych minut.',
    ],
    method: [
      'Sieć tramwajowa podzielona na odcinki między węzłami; dla każdego prędkość z rozkładu w paśmie 7–9 '
      + '(środa 2026-11-25) i liczba wozokilometrów. Rozkład, nie pomiar.',
    ],
  },
  tram_time_above_free_running_s_per_km_am_peak: {
    short: 'Czas ponad jazdę swobodną (model)',
    better: 'lower',
    read: [
      'Ile sekund na każdy kilometr rozkład dolicza ponad czas, w jakim tramwaj przejechałby trasę bez przeszkód: '
      + 'ruszając, jadąc z dozwoloną prędkością i hamując przed każdym przystankiem. W tym czasie mieszczą się '
      + 'światła, ograniczenia prędkości, dłuższa wymiana pasażerów i rezerwy rozkładu.',
      'To wynik modelu, nie pomiar. Przedział przy liczbie (w objaśnieniu wiersza) pokazuje, jak bardzo zależy od '
      + 'założeń; porównuj miasta, nie czytaj pojedynczej wartości dosłownie.',
    ],
    method: [
      'Czas z rozkładu minus czas jazdy swobodnej: przyspieszenie i hamowanie 1,0 m/s², prędkość do 50 km/h albo '
      + 'do ograniczenia zapisanego w OpenStreetMap, postój 20 s na przystanku. Przedział: postój 10–30 s i limit '
      + '40–70 km/h. Odcinki, na których rozkład jest szybszy od modelu, nie dostają wartości.',
    ],
  },
   tp_gridstudy_pt_30min: {
     short: 'Zasięg 30 min wg reguł badania UE',
     better: 'higher',
     read: [
       'Ta sama miara co zasięg 30 minut, ale policzona tak jak w badaniu Komisji Europejskiej (DG REGIO) dla 197 '
       + 'miast UE, żeby dało się porównać polskie miasta z innymi. Średnia w badaniu: 36 dla wszystkich miast, '
       + 'ok. 36–42 dla miast wielkości polskich.',
       'Wartości są wyższe niż w zwykłej mierze, bo liczy się najszybszy odjazd w szczycie, a nie typowy. '
       + 'Służy tylko do porównań z UE; różnica kilku punktów nie jest rankingiem.',
     ],
     method: [
       'Starty w centrum miejskim Eurostatu 2021; osiągalni i mieszkający w promieniu 8 km (także poza centrum); '
       + 'najkrótszy z 6 odjazdów co 5 min w 30-minutowym szczycie; łączne dojście pieszo do 15 min, sam spacer '
       + 'do 1,2 km; średnia wyników komórek ważona ludnością. Rozkłady z 2026 r., badanie UE z lat 2019–2021.',
     ],
   },
   tp_gridstudy_pt_45min: {
     short: 'Zasięg 45 min wg reguł badania UE',
     better: 'higher',
     read: [
       'Jak wyżej, dla 45 minut i promienia 12 km. Średnia w badaniu UE: 54 dla wszystkich miast, ok. 60–63 dla '
       + 'miast wielkości polskich.',
       'Służy tylko do porównań z UE; różnica kilku punktów nie jest rankingiem.',
     ],
     method: ['Jak dla 30 minut, z promieniem 12 km.'],
   },
   tp_gridstudy_dgregio_30min: {
     short: 'Wartość z badania UE',
     better: 'higher',
     read: [
       'Wynik tego miasta w badaniu Komisji Europejskiej (DG REGIO), odczytany z ich mapy komórek. Inne lata '
       + 'rozkładów (2019–2021), inne dane o ludności i inna granica centrum (2011), więc różnica do wiersza wyżej '
       + 'pokazuje także różnice danych, nie tylko zmianę komunikacji.',
     ],
     method: ['Średnia wyników komórek 200 m z przeglądarki DG REGIO, ważona ludnością 2018.'],
   },
 
  tp_gridstudy_dgregio_45min: {
    short: 'Wartość z badania UE (45 min)',
    better: 'higher',
    read: [
      'Wynik tego miasta w badaniu Komisji Europejskiej (DG REGIO) dla 45 minut, odczytany z ich mapy komórek. Inne '
      + 'lata rozkładów (2019–2021), inne dane o ludności i inna granica centrum (2011), więc różnica do wiersza wyżej '
      + 'pokazuje także różnice danych, nie tylko zmianę komunikacji.',
    ],
    method: ['Średnia wyników komórek 200 m z przeglądarki DG REGIO, ważona ludnością 2018.'],
  },
  transfer_top20_connwait_w_am_mean_min: {
    short: 'czekanie po przyjeździe linii dowożącej',
    better: 'lower',
    layer: 'transfer_wait',
    read: [
      'Ile czeka pasażer, który przyjechał jedną linią i przeszedł do drugiej, licząc od rzeczywistego przyjazdu z '
      + 'rozkładu. Jeśli rozkłady są skomunikowane, ta liczba jest mniejsza niż czekanie przy przyjściu w losowej chwili.',
      'We wszystkich siedmiu miastach obie liczby są prawie równe (różnica poniżej 0,1 min): przyjazdy nie są '
      + 'dopasowane do odjazdów, więc czekanie zależy od częstotliwości drugiej linii.',
    ],
    method: [
      'Dla każdego przyjazdu linii A w godzinach 7–9: czas do najbliższego odjazdu linii B w potrzebnym kierunku po '
      + 'przejściu między przystankami. Średnia ważona liczbą kursów obu linii, potem średnia po 20 największych węzłach.',
    ],
  },
  transfer_top20_connwait_am_p90_min: {
    short: 'co dziesiąta przesiadka czeka dłużej niż',
    better: 'lower',
    read: [
      'Dziewięć na dziesięć przesiadek w największych węzłach kończy się w tym czasie; reszta czeka dłużej. To mówi o '
      + 'pechowych przesiadkach na rzadkie linie, których średnia nie pokazuje.',
    ],
    method: ['90. percentyl czekania po rzeczywistym przyjeździe w węźle (ważony kursami), mediana po 20 węzłach.'],
  },
  transfer_top20_gtt_low_am_min: {
    short: 'Odczuwalny czas przesiadki, od',
    better: null,
    read: [
      'Ile „kosztuje” typowa przesiadka w minutach jazdy pojazdem (w literaturze: czas uogólniony), według wag z '
      + 'badań pasażerów: minuta dojścia i '
      + 'czekania liczy się bardziej niż minuta jazdy, a sama przesiadka dodaje stałą karę. Wiersz poniżej to górna '
      + 'granica pasma.',
      'Pasmo jest szerokie, bo badania różnią się co do kary (5–18 min). Różnice między miastami wynikają prawie tylko z '
      + 'czekania. Nie jest to ocena węzłów i nie służy do rankingu.',
    ],
    method: [
      'Dojście × 1,2 + czekanie × 1,47 + 5 min (wariant niski); dojście × 1,66 + czekanie × 1,47 + 18 min (wysoki). '
      + 'Wagi: Wardman 1998, Ortelli i in. 2026, Jara-Díaz i in. 2022. Dojście i czekanie z typowej przesiadki 7–9.',
    ],
  },
  transfer_top20_gtt_high_am_min: {
    short: 'do',
    better: null,
    read: ['Górna granica pasma odczuwalnego czasu przesiadki (wyjaśnienie wiersz wyżej).'],
    method: ['Dojście × 1,66 + czekanie × 1,47 + 18 min.'],
  },
  transfer_crossing_w6_hi_mean_pct: {
    short: 'Bezpieczeństwo przejść na dojściach',
    better: 'higher',
    read: [
      'Jak bezpieczne są przejścia przez jezdnię na drogach przesiadkowych, w skali używanej w polskich ocenach węzłów '
      + '(kryterium W6 metody AMPTI): '
      + 'przejście podziemne lub kładka 100, sygnalizacja 70, zebra 30, przejście niewyznakowane 0. Wyżej znaczy '
      + 'bezpieczniej.',
      'Rodzaj przejścia pochodzi z OpenStreetMap; około 3–8 % przejść nie ma tam opisu i nie jest liczonych.',
    ],
    method: [
      'Średnia ocena przejść na najkrótszej drodze pieszej każdej przesiadki, ważona liczbą kursów. Sygnalizacja liczona '
      + 'jako 70; przy 50 (gdy piesi kolidują ze skręcającymi, czego OSM nie mówi) wynik jest o 6–14 punktów niższy.',
    ],
  },
  transfer_movements_freq10_share: {
    short: 'Przesiadki między liniami co ≤ 10 min',
    better: 'higher',
    read: [
      'Jaka część możliwych przesiadek łączy dwie linie, które obie kursują w szczycie co 10 minut lub częściej. Na '
      + 'takiej przesiadce nie trzeba patrzeć w rozkład.',
      'Poza Warszawą (10 %) i Poznaniem (7 %) takich przesiadek prawie nie ma; wiersz niżej podaje próg 15 minut.',
    ],
    method: ['Kursy obu linii w ich kierunkach w godzinach 7–9 (co najmniej 12 w 2 godziny); udział wszystkich ruchów przesiadkowych, bez wag.'],
  },
  transfer_movements_freq15_share: {
    short: 'to samo, co ≤ 15 min',
    better: 'higher',
    read: ['Jak wyżej, dla linii kursujących co 15 minut lub częściej.'],
    method: ['Co najmniej 8 kursów obu linii w 2 godziny szczytu.'],
  },
  svc_school_pt_am_le20min: school(20),
  svc_school_pt_am_le30min: school(30),
  svc_school_pt_am_le30min_age0_14: { ...school(30), short: 'Szkoła w 30 min: dzieci 0–14 lat',
    read: ['Ten sam odsetek policzony dla mieszkańców w wieku 0–14 lat. Porównaj z wierszem dla wszystkich '
      + 'mieszkańców: wyższa wartość znaczy, że dzieci mieszkają częściej tam, gdzie szkoła jest blisko.'],
    method: [SVC_PT, SCHOOL_SRC, ageNote] },
  svc_sor_pt_am_le30min: sor(30),
  svc_sor_pt_am_le45min: sor(45),
  svc_sor_pt_am_le30min_age65: { ...sor(30), short: 'SOR w 30 min: osoby 65+',
    read: ['Ten sam odsetek policzony dla mieszkańców w wieku 65 lat i więcej.'], method: [SVC_PT, SOR_SRC, ageNote] },
  svc_sor_pt_evening_le30min: sor(30, 'wieczorem 20:00–22:00'),
  svc_sor_pt_am_none60: { short: 'Bez SOR w 60 min', better: 'lower', layer: 'time_to_sor',
    read: ['Odsetek mieszkańców, którzy w porannym szczycie nie dojadą komunikacją z dojściem pieszym do żadnego '
      + 'SOR w ciągu godziny.'], method: [SVC_PT, SOR_SRC] },
  age_freq_le10min_age0_14: { short: 'Kursy co ≤ 10 min w zasięgu 500 m: dzieci 0–14', better: 'higher',
    layer: 'frequent_transport',
    read: ['Odsetek dzieci w wieku 0–14 lat, które mają w zasięgu 500 m pieszo przystanek z kursami co 10 minut lub '
      + 'częściej. Porównaj z wartością dla wszystkich mieszkańców.'],
    method: ['Ta sama miara co „Kursy co ≤ 10 min w zasięgu 500 m”, ważona liczbą dzieci w komórce.', ageNote] },
  age_freq_le10min_age65: { short: 'Kursy co ≤ 10 min w zasięgu 500 m: osoby 65+', better: 'higher',
    layer: 'frequent_transport',
    read: ['Odsetek osób w wieku 65+, które mają w zasięgu 500 m pieszo przystanek z kursami co 10 minut lub częściej.'],
    method: ['Ta sama miara co „Kursy co ≤ 10 min w zasięgu 500 m”, ważona liczbą osób 65+ w komórce.', ageNote] },
  age_tp_pt_am_30min_age0_14: { short: 'Zasięg komunikacją w 30 min: dzieci 0–14', better: 'higher',
    read: ['Jaką część par „mieszkaniec – osoba z okolicy (7,5 km)” da się pokonać w 30 minut, licząc tylko '
      + 'mieszkańców w wieku 0–14 lat jako punkty startu.'],
    method: [PT_METHOD, RATIO_OF_MEANS, ageNote] },
  age_tp_pt_am_30min_age65: { short: 'Zasięg komunikacją w 30 min: osoby 65+', better: 'higher',
    read: ['Jak wyżej, dla mieszkańców w wieku 65+ jako punktów startu.'], method: [PT_METHOD, RATIO_OF_MEANS, ageNote] },
  freq_seg_net_le5min: freq(5),
  freq_seg_net_le10min: freq(10),
  freq_seg_net_le15min: freq(15),
  freq_seg_net_le20min: freq(20),
  freq_seg_net_le30min: freq(30),
  rail_ge4dph_net_1km: {
    short: 'Kolej lub metro co 15 min w zasięgu 1 km',
    better: 'higher',
    read: [
      'Odsetek mieszkańców w zasięgu 1 km pieszo od stacji kolei lub metra z co najmniej czterema odjazdami na '
      + 'godzinę.',
      'Pokazuje, ilu ludzi ma pod ręką szybki transport szynowy o użytecznej częstotliwości.',
    ],
    method: ['Odjazdy ze stacji z rozkładu na środę 2026-11-25; zasięg po sieci pieszej; ludność ze spisu 2021.'],
  },
  dxs_dense_underserved_share: {
    short: 'Gęsta zabudowa bez kursów co 20 min',
    better: 'lower',
    layer: 'density_service',
    read: [
      'Jaka część mieszkańców komórek o gęstości co najmniej 5 000 os./km² nie ma w zasięgu 500 m kursów nawet co '
      + '20 minut.',
      'To najprostsza miara niedopasowania: ludzie są, oferty nie ma. Niżej znaczy lepiej.',
    ],
    method: [
      'Komórki 250 m, liczeni tylko mieszkańcy. 5 000 os./km² (50 na hektar) to w literaturze poziom, przy którym '
      + 'oczekuje się częstej obsługi autobusowej; wynik przy progu 2 500 jest w tabelach jako wariant, a kolejność '
      + 'miast od progu prawie nie zależy. Próg 20 minut jest wyborem autorów.',
    ],
  },
  dxs_rank_correlation: {
    short: 'Częstsze kursy tam, gdzie gęściej',
    better: 'higher',
    layer: 'density_service',
    read: [
      'Czy częstsze kursy są tam, gdzie mieszka więcej ludzi. 1 oznacza pełną zgodność, 0 brak związku.',
      'Niska wartość w samym mieście nie musi być zła: może znaczyć, że prawie całe miasto ma dobrą obsługę, więc '
      + 'gęstość niczego już nie różnicuje.',
    ],
    method: ['Korelacja rang Spearmana między gęstością komórki a klasą odstępu między kursami, ważona ludnością.'],
  },
  tp_pt_am_30min_ratio_of_means: {
    ...PT30.headline,
    read: [
      PT30.headline.read[0],
      '100 oznaczałoby komunikację tak szybką jak jazda 15 km/h w linii prostej do każdego w okolicy. Różnica kilku '
      + 'punktów między miastami nie jest rankingiem: wynik zależy od przebiegu granicy i od danych o ludności.',
      UNCERTAINTY,
    ],
  },
  tp_pt_am_30min: PT30.typical,
  tp_pt_am_45min_ratio_of_means: {
    ...PT45.headline,
    read: [
      PT45.headline.read[0],
      'W małym, zwartym obszarze ta liczba zbliża się do udziału całego obszaru osiągalnego w 45 minut, więc duże i '
      + 'małe miasta nie są w pełni porównywalne.',
      UNCERTAINTY,
    ],
  },
  tp_pt_am_45min: PT45.typical,
  tp_walk_30min_ratio_of_means: {
    ...WALK.headline,
    read: [
      WALK.headline.read[0],
      'Pokazuje ciągłość sieci pieszej. Niepewność: wybór danych o ludności przesuwa wynik miast o 1–6 punktów; '
      + 'rozkładów jazdy ta miara nie używa.',
    ],
  },
  tp_walk_30min: WALK.typical,
  tp_bike_lts3_30min_ratio_of_means: {
    ...BIKE3.headline,
    read: [BIKE3.headline.read[0], BIKE3.headline.read[1],
      'Niepewność: wybór danych o ludności przesuwa wynik miast o najwyżej 4 punkty; rozkładów jazdy ta miara nie używa.'],
  },
  tp_bike_lts3_30min: BIKE3.typical,
  tp_bike_lts4_30min_ratio_of_means: {
    ...BIKE4.headline,
    read: [BIKE4.headline.read[0], BIKE4.headline.read[1],
      'Niepewność: wybór danych o ludności przesuwa wynik miast o najwyżej 4 punkty; rozkładów jazdy ta miara nie używa.'],
  },
  tp_bike_lts4_30min: BIKE4.typical,
  transfer_top20_walkwait_w_am_mean_min: {
    short: 'Typowa przesiadka: dojście + czekanie',
    better: 'lower',
    layer: 'transfer_total',
    read: [
      'Ile trwa typowa przesiadka w 20 największych węzłach w porannym szczycie: przejście do drugiej linii plus '
      + 'czekanie na nią. Niżej znaczy lepiej.',
      'Dwa wiersze poniżej to części tej liczby i sumują się do niej. Czekanie zwykle stanowi 70–90 % całości, więc '
      + 'o wyniku decyduje głównie częstotliwość kursów, nie układ przystanków.',
    ],
    method: [
      'Dla każdej przesiadki, po której druga linia jedzie gdzie indziej niż pierwsza: dojście po sieci pieszej '
      + '(5 km/h) i oczekiwane czekanie z rozkładu przy przyjściu w losowej chwili. Średnia ważona liczbą kursów obu '
      + 'linii, potem średnia po 20 węzłach z największą liczbą odjazdów. Czas z rozkładu, w pełnych minutach.',
    ],
  },
  transfer_top20_walk_w_am_mean_min: {
    short: 'w tym dojście między liniami',
    better: 'lower',
    layer: 'transfer_walk',
    read: [
      'Część typowej przesiadki, którą się idzie. W największych węzłach to zwykle 1,5–3 minuty; więcej oznacza '
      + 'rozległy węzeł albo przystanki po dwóch stronach dużego skrzyżowania.',
    ],
    method: ['Jak wyżej; sama część piesza. Bez czasu na światłach, schodach i w tłumie.'],
  },
  transfer_top20_wait_w_am_mean_min: {
    short: 'w tym czekanie na drugą linię',
    better: 'lower',
    layer: 'transfer_wait',
    read: [
      'Część typowej przesiadki, którą się czeka. Przy kursach co 10 minut to około 5 minut; długie czekanie oznacza '
      + 'rzadkie linie w węźle.',
    ],
    method: ['Jak wyżej; samo czekanie. Liczone tak, jakby pasażer przychodził w losowej chwili, bez skomunikowań.'],
  },
  transfer_dep_share_walkdir_le2min: {
    short: 'Odjazdy w zwartych węzłach',
    better: 'higher',
    layer: 'transfer_walk',
    read: [
      'Jaka część odjazdów odbywa się w węzłach, w których między liniami idzie się nie dłużej niż 2 minuty.',
      'Wyżej znaczy bardziej zwarte węzły. Poziom zależy od tego, jak łączymy przystanki w zespoły, więc porównywać '
      + 'miasta między sobą, nie czytać jako wartości bezwzględnej.',
    ],
    method: [
      'Dojście po sieci pieszej OpenStreetMap, 5 km/h, tylko dla przesiadek, po których druga linia jedzie gdzie '
      + 'indziej niż pierwsza. Miara własna, składowe pokazywane osobno.',
    ],
  },
  transfer_dependence_pt_am_30min_ratio_of_sums: dependence(30, 'transfer_dependence_30'),
  tp_pt_am_direct_30min: direct(30),
  transfer_dependence_pt_am_45min_ratio_of_sums: dependence(45),
  tp_pt_am_direct_45min: direct(45),
  share_residents_ge5000: {
    short: 'Mieszkańcy gęstej zabudowy',
    better: 'higher',
    layer: 'density_250m',
    read: [
      'Jaka część mieszkańców mieszka w kwadratach 250 × 250 m, w których jest co najmniej 5 000 osób na km² '
      + '(ok. 310 osób na kwadrat). To zwykle bloki i kamienice; poniżej tej granicy przeważają domy jednorodzinne.',
      'Ta sama granica co w warstwie „gęstość a częstotliwość kursów”. W obszarze funkcjonalnym zależy też od tego, '
      + 'jak daleko sięga jego granica, więc porównywać miasta raczej w rdzeniu.',
    ],
    method: [
      'Ludność ze spisu 2021 (siatka 1 km) rozłożona na kwadraty 250 m według modelu GHSL 2020; gęstość kwadratu = '
      + 'mieszkańcy / 0,0625 km². Liczeni tylko mieszkańcy, bez miejsc pracy.',
    ],
  },
  median_resident_density_250m: {
    short: 'Gęstość wokół typowego mieszkańca',
    better: 'higher',
    layer: 'density_250m',
    read: [
      'Połowa mieszkańców mieszka w kwadratach 250 m gęstszych niż ta wartość, połowa w rzadszych.',
      'Wyższa niż gęstość ważona populacją z siatki 1 km, bo mniejszy kwadrat obejmuje mniej pustych terenów; tych '
      + 'dwóch liczb nie porównywać.',
    ],
    method: ['Mediana gęstości kwadratów 250 m ważona liczbą mieszkańców; ludność jak w wierszu powyżej.'],
  },
  degurba2021_share_urban_centre: {
    short: 'Mieszkańcy centrów miejskich',
    better: null,
    read: [
      'Jaka część mieszkańców żyje w centrum miejskim według Eurostatu: zwartym obszarze kwadratów 1 km z co '
      + 'najmniej 1 500 osobami na km², który razem ma co najmniej 50 000 mieszkańców.',
      'To ta sama definicja, której Eurostat i OECD używają we wszystkich krajach, więc liczbę można zestawiać z '
      + 'miastami za granicą. W obszarze funkcjonalnym zależy od tego, jak szeroko narysowano jego granicę.',
    ],
    method: [
      'Oficjalna warstwa centrów miejskich Eurostatu 2021 nałożona na siatkę spisową 1 km (spis 2021).',
    ],
  },
  poly_eta_mask_t20: {
    short: 'Rozrzut najgęstszych miejsc',
    better: null,
    read: [
      'Czy najgęściej zaludnione miejsca leżą w jednym rejonie (blisko 0), czy są rozrzucone po całym obszarze jak '
      + 'cała zabudowa (blisko 1).',
      'Wysokie w GZM, Trójmieście i Bydgoszczy–Toruniu, ale też w Lublinie, gdzie gęste osiedla leżą daleko od '
      + 'siebie. Samo nie odróżnia kilku miast od jednego miasta z rozrzuconymi osiedlami.',
    ],
    method: [
      'Miara η Volpatiego i Barthelemy’ego (2018): średnia odległość między najgęstszymi kwadratami 100 m (powyżej '
      + 'progu LouBar) podzielona przez średnią odległość między wszystkimi kwadratami zabudowy (≥ 20 % powierzchni '
      + 'pod budynkami).',
    ],
  },
  hotspots_n: {
    short: 'Skupiska gęstości',
    better: null,
    layer: 'density_250m',
    read: [
      'Ile jest zwartych skupisk kwadratów 250 m z co najmniej 10 000 osobami na km², w których mieszka co najmniej '
      + '5 000 osób. W GZM ponad 30, w miastach jednocentrowych zwykle kilka do kilkunastu.',
      'Skupiska to najczęściej wielkie osiedla, a nie śródmieścia.',
    ],
    method: ['Kwadraty powyżej progu połączone bokami lub narożnikami; ludność jak w wierszach o gęstości.'],
  },
  hotspots_largest_share: {
    short: 'Udział największego skupiska',
    better: null,
    read: [
      'Jaka część mieszkańców wszystkich skupisk gęstości mieszka w największym z nich. Niski udział (GZM ok. 10 %) '
      + 'oznacza wiele podobnych ośrodków, wysoki (Szczecin ok. 60 %) jeden dominujący.',
    ],
    method: ['Jak wiersz „Skupiska gęstości”; w mianowniku wszystkie skupiska, także mniejsze niż 5 000 osób.'],
  },
  dist_below_floor_pt_am_30min: {
    short: 'Poniżej minimalnego zasięgu (30 min)',
    better: 'lower',
    layer: 'transport_performance_30',
    read: [
      'Jaka część mieszkańców osiąga komunikacją i pieszo w 30 minut mniej niż 16 % ludzi mieszkających w promieniu '
      + '7,5 km, czyli mniej niż połowę tego, co typowy mieszkaniec rdzenia w typowym z siedmiu miast.',
      'Średnia miasta tego nie pokazuje: dwa miasta o tej samej średniej mogą mieć bardzo różną liczbę ludzi '
      + 'z wyraźnie słabym dostępem. Niżej znaczy lepiej; kilka punktów różnicy to nie ranking.',
    ],
    method: [FLOOR_METHOD, 'Środa 2026-11-25, 7:00–9:00, mediana z odjazdów co minutę; ludność ze spisu 2021.'],
  },
  dist_below_floor_pt_am_45min: {
    short: 'Poniżej minimalnego zasięgu (45 min)',
    better: 'lower',
    read: [
      'Jak wyżej, ale dla 45 minut: odsetek mieszkańców, którzy w 45 minut osiągają mniej niż 28 % ludzi z promienia '
      + '11,25 km.',
    ],
    method: [FLOOR_METHOD],
  },
  dist_fgt1_pt_am_30min: {
    short: 'Średni niedobór do progu',
    better: 'lower',
    read: [
      'Jak daleko pod progiem są ci, którzy są pod nim. Wartość 5 znaczy: gdyby brakujący zasięg rozłożyć na '
      + 'wszystkich mieszkańców, każdemu brakowałoby 5 % progu.',
      'Dwa miasta z tym samym odsetkiem poniżej progu mogą się tu różnić: wyższa wartość to głębsze braki.',
    ],
    method: ['Wskaźnik Fostera–Greera–Thorbeckego FGT1 × 100: średnia z (próg − wynik) / próg po mieszkańcach '
      + 'pod progiem, z zerem dla pozostałych, ważona ludnością. ' + FLOOR_METHOD],
  },
  dist_p25_pt_am_30min: {
    short: 'Słabsza ćwiartka mieszkańców (30 min)',
    better: 'higher',
    read: [
      'Co czwarty mieszkaniec ma zasięg w 30 minut nie większy niż ta wartość (25. percentyl komórek ważony ludnością).',
      'Razem z wierszem poniżej pokazuje, jak szeroko rozkłada się dostęp w mieście.',
    ],
    method: ['Komórki 250 m w masce danych o rozkładach, posortowane według wyniku; wartość, przy której skumulowana '
      + 'ludność osiąga 25 %.'],
  },
  dist_p75_pt_am_30min: {
    short: 'Lepsza ćwiartka mieszkańców (30 min)',
    better: 'higher',
    read: ['Co czwarty mieszkaniec ma zasięg w 30 minut co najmniej taki (75. percentyl komórek ważony ludnością).'],
    method: ['Jak wiersz wyżej, dla 75 % ludności.'],
  },
  dist_below_floor_pt_evening_30min: {
    short: 'Poniżej progu wieczorem (30 min)',
    better: 'lower',
    read: [
      'Odsetek mieszkańców poniżej tego samego progu co rano (16 %), ale dla wyjazdów w środę 20:00–22:00. Wzrost '
      + 'względem szczytu pokazuje, ilu ludzi traci minimalny dostęp, gdy kursów jest mniej.',
    ],
    method: [FLOOR_METHOD],
  },
  dist_below_floor_pt_saturday_30min: {
    short: 'Poniżej progu w sobotę (30 min)',
    better: 'lower',
    read: ['Jak wyżej, dla soboty 2026-11-28, 10:00–14:00.'],
    method: [FLOOR_METHOD],
  },
}

/** Short explanations of the areas a metric can refer to (the columns of the city table). */
export const DOMAIN_INFO = {
  core: {
    short: 'Miasto',
    title: 'Miasto (rdzeń)',
    read: 'Miasto centralne w granicach administracyjnych; dla GZM i Trójmiasta suma miast rdzeniowych.',
  },
  urban_centre: {
    short: 'Centrum miejskie',
    title: 'Centrum miejskie',
    read: 'Zwarty obszar gęstej zabudowy według Eurostatu (2021). Ta sama reguła dla każdego miasta, więc lepiej '
      + 'nadaje się do porównań niż granice administracyjne.',
  },
  covered: {
    short: 'Obszar z danymi',
    title: 'Obszar pokryty danymi o rozkładach',
    read: 'Ta część całego obszaru, dla której mamy rozkłady jazdy. Poza nią nie wiemy, jaka jest komunikacja.',
  },
  fua: {
    short: 'Cały obszar',
    title: 'Cały obszar: miasto ze strefą dojazdów',
    read: 'Miasto razem z gminami, z których wielu mieszkańców dojeżdża do niego do pracy. Granice wyznacza '
      + 'Eurostat (obszar funkcjonalny, FUA).',
  },
  city_tram_network: {
    short: 'Sieć tramwajowa',
    title: 'Sieć tramwajowa miasta',
    read: 'Wszystkie kursy tramwajowe miasta, niezależnie od granic.',
  },
}
