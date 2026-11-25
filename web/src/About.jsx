import { useEffect } from 'react'
import { Hint, Modal, TextTable } from '@bartor-net/ui-kit'
import { dataDates } from './layerInfo'

/**
 * Placeholder for the full methodology: sources and the date mismatch. `toLimits` opens it scrolled to the list of
 * what the numbers do not say.
 */
export default function About({ catalog, metrics, attributions, onClose, toLimits = false }) {
  useEffect(() => {
    if (toLimits) document.getElementById('about-limits')?.scrollIntoView({ block: 'start' })
  }, [toLimits])
  const feeds = attributions?.gtfs_feeds || []
  const rows = catalog.layers.map((l) => [
    <>{l.title}{l.status !== 'ready' && <small>w przygotowaniu</small>}</>,
    <>{l.attribution || '-'}{l.note && <small>{l.note}</small>}</>,
    dataDates(l) || '-',
  ])
  return (
    <Modal title="O danych" onClose={onClose}>
      <h3>Co pokazuje ta strona</h3>
      <p>
        Jak gęsto i jak zwarcie mieszkają ludzie w polskich aglomeracjach i co da się w nich osiągnąć komunikacją
        zbiorową: tramwajem, autobusem, koleją i metrem. Aglomeracja to miasto razem z gminami, z których wielu
        mieszkańców dojeżdża do niego do pracy. Wszystkie liczby da się odtworzyć z publicznych danych; metoda
        i kontrole są opisane w raporcie w repozytorium.
      </p>

      <h3>Słowa użyte na stronie</h3>
      <dl className="about-terms">
        <dt>Cały obszar</dt>
        <dd>Miasto ze strefą dojazdów do pracy. Granice wyznacza Eurostat (obszar funkcjonalny, w skrócie FUA).</dd>
        <dt>Miasto</dt>
        <dd>Miasto centralne w granicach administracyjnych; w GZM i Trójmieście kilka miast razem.</dd>
        <dt>Centrum miejskie</dt>
        <dd>Zwarty obszar gęstej zabudowy, wyznaczony jedną regułą dla wszystkich miast Europy. Najlepszy do porównań.</dd>
        <dt>Obszar z danymi</dt>
        <dd>Ta część całego obszaru, dla której mamy rozkłady jazdy. Reszta jest na mapie kreskowana.</dd>
        <dt>Zasięg w 30 minut</dt>
        <dd>
          Ilu mieszkańców da się osiągnąć w 30 minut komunikacją i pieszo, jako procent wszystkich mieszkających
          w promieniu 7,5 km. 100 % oznaczałoby, że do każdego z nich da się dotrzeć w pół godziny.
        </dd>
        <dt>Częsta komunikacja</dt>
        <dd>Przystanek, z którego w dzień roboczy coś odjeżdża co kilka lub kilkanaście minut; próg jest podany przy każdej liczbie.</dd>
        <dt>Mediana</dt>
        <dd>Wartość środkowa: połowa przypadków ma mniej, połowa więcej. Mniej wrażliwa na skrajności niż średnia.</dd>
        <dt>Rozkład jazdy</dt>
        <dd>Plik w formacie GTFS, w którym organizator komunikacji publikuje kursy w postaci czytelnej dla programów.</dd>
      </dl>

      <h3 id="about-limits">Czego te liczby nie mówią</h3>
      <ul className="about-limits">
        <li>Liczymy z rozkładów jazdy, nie z rzeczywistych przejazdów: bez opóźnień, korków i zatłoczenia.</li>
        <li>
          Wynik zależy od tego, gdzie przebiega granica miasta, więc różnica kilku punktów między
          miastami nie jest rankingiem.
        </li>
        <li>
          Część rozkładów pochodzi z nieoficjalnych źródeł, prywatnych przewoźników w większości brakuje,
          a obszary bez danych są kreskowane, nie liczone jako brak komunikacji.
        </li>
        <li>„Osiągalna ludność” jest przybliżeniem miejsc pracy i usług; liczymy tylko czas, bez cen biletów.</li>
        <li>Rozkłady pochodzą z jednej środy i jednej soboty w listopadzie 2026.</li>
        <li>Metody nie recenzował badacz transportu; obliczenia wykonał asystent AI.</li>
      </ul>

      <h3>Różnica dat</h3>
      <p>
        Dane o ludności pochodzą z lat 2020-2021 (spis powszechny i siatki statystyczne),
        a rozkłady jazdy z 2026 roku. Miary łączące jedno z drugim opisują więc rozkłady
        dzisiejsze na tle ludności sprzed kilku lat. Nowo zbudowane osiedla mogą być widoczne
        jako obszary bez ludności, a przy każdej liczbie podajemy daty obu źródeł.
      </p>

      <h3>Warstwy i źródła</h3>
      {rows.length
        ? <TextTable head={['Warstwa', 'Źródło', 'Daty danych']} rows={rows} />
        : <Hint>Lista warstw pojawi się po przeliczeniu.</Hint>}

      <h3>Kto publikuje rozkłady jazdy</h3>
      {feeds.length
        ? (
          <TextTable
            head={['Wydawca', 'Licencja lub warunki', 'Obszar']}
            rows={feeds.map((f) => [
              f.publisher,
              <>{f.license || '-'}{f.url && <small><a href={f.url} target="_blank" rel="noopener">warunki</a></small>}</>,
              (f.agglomerations || []).join(', ') || '-',
            ])}
          />
        )
        : <Hint>Lista wydawców pojawi się po przeliczeniu.</Hint>}

      <h3>Mapa</h3>
      <p>
        Podkład: <a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a>,
        dane © <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">współtwórcy OpenStreetMap</a>,
        schemat © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a>.
      </p>
      <Hint>
        Katalog: {catalog.generated || 'brak daty'}; miary: {metrics.generated || 'jeszcze nie przeliczone'}.
      </Hint>
    </Modal>
  )
}
