import { useState } from 'react'
import {
  Chips, HelpButton, Hint, InfoButton, LinkButton, Panel, RadioCards, Select, Sidebar as Shell, Toggle,
} from '@bartor-net/ui-kit'
import { dataDates } from './layerInfo'
import { layerColor, rampMid } from './data'
import { chipLabel, overlayGroups, valueLayers, variantOf } from './layerControl'

const TITLE = 'Zwartość miast'
const SUBTITLE = 'Gęstość, forma i transport zbiorowy w polskich aglomeracjach'
const NO_VALUE = ''   // the radio value of "Tylko granice"
const CHIPS_MAX = 4   // more layers in a group than this are chosen from a list

/** What stands behind a layer's "?": its note, then the dates and the source in small print. */
function LayerHelp({ layer }) {
  const dates = dataDates(layer)
  return (
    <>
      {layer.note && <p>{layer.note}</p>}
      {(dates || layer.attribution) && (
        <p className="layer-meta">
          {dates && <span>{dates}</span>}
          {layer.attribution && <span>{layer.attribution}</span>}
        </p>
      )}
    </>
  )
}

/** One overlay group: a switch with a "?", and when on: which layer (if the group has several) and its variants. */
function OverlayGroup({ group, state, onOn, onLayer, onVariant }) {
  const o = state.overlays[group.kind]
  const chosen = group.layers.find((l) => l.id === o.layer) || group.layers[0]
  const variants = chosen.variants || []
  const chooser = o.on && group.layers.length > 1
  return (
    <Toggle
      label={group.label} checked={o.on} onChange={(v) => onOn(group.kind, v)}
      help={chosen.note || chosen.attribution ? <LayerHelp layer={chosen} /> : undefined}
    >
      {o.on && (chooser || variants.length > 1) && (
        <div className="overlay-body">
          {chooser && (group.layers.length <= CHIPS_MAX
            ? (
              <Chips
                tight items={group.layers.map((l) => ({ key: l.id, label: chipLabel(l), on: l.id === chosen.id }))}
                onPick={(id) => onLayer(group.kind, id)}
              />
            )
            : (
              <Select
                label={`${group.label}: warstwa`} value={chosen.id}
                options={group.layers.map((l) => ({ value: l.id, label: chipLabel(l) }))}
                onChange={(id) => onLayer(group.kind, id)}
              />
            ))}
          {variants.length > 1 && (
            <Chips
              tight items={variants.map((v) => ({ key: v.key, label: v.label, on: v.key === variantOf(state, chosen) }))}
              onPick={(k) => onVariant(chosen, k)}
            />
          )}
        </div>
      )}
    </Toggle>
  )
}

/** The controls only: city, what to colour the map with, overlays. Legends live on the map, tables in the dock. */
export default function Sidebar({
  catalog, metrics, selectedId, onPick, view, active, onValue, onOverlayOn, onOverlayLayer, onVariant,
  sheetOpen, setSheetOpen, onAbout, onCompare,
}) {
  const [helpFor, setHelpFor] = useState(null)   // the value layer whose "?" is open
  const sel = catalog.agglomerations.find((a) => a.id === selectedId)
  const options = [
    { value: '', label: 'Cała Polska' },
    ...catalog.agglomerations.map((a) => ({ value: a.id, label: a.name })),
  ]
  const values = valueLayers(catalog.layers)
  const planned = catalog.layers.filter((l) => l.status !== 'ready' && l.kind === 'choropleth')
  const groups = overlayGroups(catalog.layers)
  const chosenValue = values.find((l) => l.id === view.value) || null
  const helpLayer = values.find((l) => l.id === helpFor) || null
  const layerCredits = [...new Set(catalog.layers
    .filter((l) => l.status === 'ready' && active.has(l.id) && l.attribution)
    .map((l) => l.attribution))]
  const cards = [
    { value: NO_VALUE, label: 'Tylko granice', sub: 'bez kolorowania obszaru' },
    ...values.map((l) => ({
      value: l.id,
      label: (
        <>
          {l.title}
          {(l.note || l.attribution) && (
            <HelpButton open={helpFor === l.id} onClick={() => setHelpFor(helpFor === l.id ? null : l.id)} />
          )}
        </>
      ),
      sub: l.sub || l.unit,
      color: rampMid(l.ramp) || layerColor(l),
    })),
  ]

  return (
    <Shell
      title={TITLE} subtitle={SUBTITLE} peek={sel ? sel.name : 'aglomeracja i warstwy'}
      open={sheetOpen} setOpen={setSheetOpen}
      action={<InfoButton label="O danych" title="Źródła i daty danych" onClick={() => onAbout()} />}
      footer={(
        <>
          {metrics.metrics.length
            ? `Miary przeliczono: ${metrics.generated || 'brak daty'}.`
            : 'Miary pojawią się po przeliczeniu.'}
          {catalog.generated ? ` Katalog warstw: ${catalog.generated}.` : ''}
          <br />
          Podkład: <a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a>,
          {' '}© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">współtwórcy OpenStreetMap</a>.
          {layerCredits.map((a) => <span key={a}><br />{a}</span>)}
        </>
      )}
    >
      <Panel title="Aglomeracja">
        <Select label="Aglomeracja" value={selectedId || ''} options={options}
          onChange={(v) => onPick(v || null)} />
        <LinkButton block onClick={onCompare}>Porównanie miast</LinkButton>
      </Panel>

      <Panel
        title="Co pokazać"
        help={<p>Naraz widać jedną warstwę wartości, bo jej kolory zasłaniałyby się nawzajem. Nakładki poniżej można dodać do każdej z nich. Legenda jest w rogu mapy.</p>}
      >
        {values.length === 0
          ? <Hint>Warstwy pojawią się po przeliczeniu.</Hint>
          : (
            <RadioCards
              name="value-layer" label="Warstwa wartości"
              value={chosenValue ? chosenValue.id : NO_VALUE}
              onChange={(v) => onValue(v === NO_VALUE ? null : v)}
              options={cards}
            />
          )}
        {helpLayer && <div className="kit-info"><LayerHelp layer={helpLayer} /></div>}
        {planned.length > 0 && (
          <Hint>W przygotowaniu: {planned.map((l) => l.title).join('; ')}.</Hint>
        )}
      </Panel>

      <Panel
        title="Nakładki"
        help={<p>Nakładki można łączyć z każdą warstwą wartości i ze sobą.</p>}
      >
        {groups.length === 0 && <Hint>Nakładki pojawią się po przeliczeniu.</Hint>}
        {groups.map((g) => (
          <OverlayGroup
            key={g.kind} group={g} state={view}
            onOn={onOverlayOn} onLayer={onOverlayLayer} onVariant={onVariant}
          />
        ))}
      </Panel>
      <p className="kit-footnote sidebar-link">
        <LinkButton onClick={() => onAbout()}>Źródła, różnice dat i ograniczenia</LinkButton>
      </p>
    </Shell>
  )
}
