// What each metric means, for the "?" next to it. `read` comes first and says how to understand the number;
// `method` says how it was computed. `better` is the direction used for "where the city stands" ('higher',
// 'lower' or null when the number is not a quality). `layer` is the map layer that shows the same thing cell by
// cell, when there is one. Texts are Polish UI copy; keep them short and concrete.

export const METRIC_GROUPS = [
  { id: 'size', title: 'Wielkość i gęstość', metrics: ['area', 'population_census', 'density_gross', 'pwdens_census_1km'] },
  { id: 'form', title: 'Forma miasta', metrics: ['rho_t20', 'rho_nearest_t20', 'profile_r50_km'] },
  {
    id: 'supply', title: 'Oferta komunikacji',
    metrics: ['vkm_per_cap_day_total', 'tram_speed_median', 'freq_seg_net_le5min', 'freq_seg_net_le10min',
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
    id: 'transfer', title: 'Przesiadki',
    metrics: ['transfer_top20_walkwait_w_am_mean_min', 'transfer_top20_walk_w_am_mean_min',
      'transfer_top20_wait_w_am_mean_min', 'transfer_dep_share_walkdir_le2min',
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
    short: 'Indeks Bertauda ρ',
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
    short: 'Indeks Bertauda ρ do najbliższego centrum',
    better: 'lower',
    read: [
      'Ten sam indeks, ale odległość liczona do najbliższego z kilku centrów. Ma sens dla obszarów z kilkoma '
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
    short: 'Wozokilometry na mieszkańca na dobę',
    better: 'higher',
    read: [
      'Ile kilometrów przejeżdżają w ciągu doby wszystkie pojazdy komunikacji w przeliczeniu na mieszkańca.',
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
    short: 'Zgodność gęstości i częstotliwości',
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
    read: 'Ta część obszaru funkcjonalnego, dla której mamy rozkłady jazdy. Poza nią nie wiemy, jaka jest komunikacja.',
  },
  fua: {
    short: 'Cały obszar',
    title: 'Cały obszar funkcjonalny (FUA)',
    read: 'Miasto razem ze strefą dojazdów według Eurostatu.',
  },
  city_tram_network: {
    short: 'Sieć tramwajowa',
    title: 'Sieć tramwajowa miasta',
    read: 'Wszystkie kursy tramwajowe miasta, niezależnie od granic.',
  },
}
