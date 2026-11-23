import { useState } from 'react'
import {
  Footnote, Hint, InfoButton, LinkButton, Panel, Select, Sidebar as Shell, Toggle, Warn,
} from '@bartor-net/ui-kit'
import { dataDates } from './layerInfo'
import { layerColor } from './data'
import About from './About'

const TITLE = 'Zwartość miast'
const SUBTITLE = 'Gęstość, forma i transport zbiorowy w polskich aglomeracjach'

function LayerRow({ layer, on, onChange }) {
  if (layer.status !== 'ready') {
    return (
      <div className="layer-planned" title="Warstwa będzie dostępna po przeliczeniu">
        <span>{layer.title}</span>
        <em>w przygotowaniu</em>
      </div>
    )
  }
  const dates = dataDates(layer)
  return (
    <Toggle label={layer.title} swatch={layerColor(layer)} checked={on} onChange={onChange}>
      {on && (dates || layer.attribution || layer.note) && (
        <p className="layer-meta">
          {dates && <span>{dates}</span>}
          {layer.attribution && <span>{layer.attribution}</span>}
          {layer.note && <span>{layer.note}</span>}
        </p>
      )}
    </Toggle>
  )
}

export default function Sidebar({
  catalog, metrics, selectedId, onPick, active, setLayer, sheetOpen, setSheetOpen,
}) {
  const [about, setAbout] = useState(false)
  const sel = catalog.agglomerations.find((a) => a.id === selectedId)
  const options = [
    { value: '', label: 'Cała Polska' },
    ...catalog.agglomerations.map((a) => ({ value: a.id, label: a.name })),
  ]
  const attributions = [...new Set(catalog.layers
    .filter((l) => l.status === 'ready' && active.has(l.id) && l.attribution)
    .map((l) => l.attribution))]

  return (
    <>
      <Shell
        title={TITLE} subtitle={SUBTITLE} peek={sel ? sel.name : 'aglomeracja i warstwy'}
        open={sheetOpen} setOpen={setSheetOpen}
        action={<InfoButton label="O danych" title="Źródła i daty danych" onClick={() => setAbout(true)} />}
        footer={(
          <>
            Podkład: <a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a>,
            {' '}© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">współtwórcy OpenStreetMap</a>.
            {attributions.map((a) => <span key={a}><br />{a}</span>)}
          </>
        )}
      >
        <Panel title="Aglomeracja">
          <Select label="Aglomeracja" value={selectedId || ''} options={options}
            onChange={(v) => onPick(v || null)} />
          {sel?.note && <Warn>{sel.note}</Warn>}
          {!sel && <Hint>Wybierz aglomerację z listy albo kliknij jej obszar na mapie.</Hint>}
        </Panel>

        <Panel title="Warstwy">
          {catalog.layers.length === 0 && <Hint>Warstwy pojawią się po przeliczeniu.</Hint>}
          {catalog.layers.map((l) => (
            <LayerRow key={l.id} layer={l} on={active.has(l.id)} onChange={(v) => setLayer(l.id, v)} />
          ))}
          {catalog.layers.some((l) => l.status !== 'ready') && (
            <Hint>Warstwy oznaczone jako „w przygotowaniu” zostaną włączone, gdy dane będą gotowe.</Hint>
          )}
        </Panel>

        <Panel title="O danych">
          <Hint>
            Liczba ludności pochodzi ze spisu i siatek z lat 2020-2021, a rozkłady jazdy z 2026 roku.
            Miary łączą więc dane z różnych lat; przy każdej warstwie i liczbie podajemy daty.
          </Hint>
          <LinkButton block onClick={() => setAbout(true)}>Źródła i różnice dat</LinkButton>
          <Footnote>
            {metrics.metrics.length
              ? `Miary przeliczono: ${metrics.generated || 'brak daty'}.`
              : 'Miary pojawią się po przeliczeniu.'}
            {catalog.generated ? ` Katalog warstw: ${catalog.generated}.` : ''}
          </Footnote>
        </Panel>
      </Shell>
      {about && <About catalog={catalog} metrics={metrics} onClose={() => setAbout(false)} />}
    </>
  )
}
