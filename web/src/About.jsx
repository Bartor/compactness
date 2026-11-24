import { Hint, Modal, TextTable } from '@bartor-net/ui-kit'
import { dataDates } from './layerInfo'

/** Placeholder for the full methodology: sources and the date mismatch. */
export default function About({ catalog, metrics, attributions, onClose }) {
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
        Gęstość zaludnienia, zwartość zabudowy i dostępność transportu zbiorowego w polskich
        aglomeracjach (funkcjonalnych obszarach miejskich, FUA). Wszystkie liczby da się
        odtworzyć z publicznych danych; metoda i kontrole są opisane w raporcie w repozytorium.
      </p>

      <h3>Czego te liczby nie mówią</h3>
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

      <h3>Wydawcy rozkładów jazdy (GTFS)</h3>
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
