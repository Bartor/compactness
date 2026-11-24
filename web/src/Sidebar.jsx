import {
  Chips, Field, Footnote, Hint, InfoButton, LinkButton, Panel, RadioCards, Select, Sidebar as Shell, Toggle, Warn,
} from '@bartor-net/ui-kit'
import { dataDates } from './layerInfo'
import { layerColor, rampMid } from './data'
import { LegendBody } from './Legend'
import { focusOf } from './classFocus'
import { chipLabel, overlayGroups, valueLayers, variantOf } from './layerControl'
import { usePhone } from './usePhone'

const TITLE = 'Zwartość miast'
const SUBTITLE = 'Gęstość, forma i transport zbiorowy w polskich aglomeracjach'
const NO_VALUE = ''   // the radio value of "Tylko granice"
const CHIPS_MAX = 4   // more layers in a group than this are chosen from a list

function LayerMeta({ layer }) {
  const dates = dataDates(layer)
  if (!dates && !layer.attribution) return null
  return (
    <p className="layer-meta">
      {dates && <span>{dates}</span>}
      {layer.attribution && <span>{layer.attribution}</span>}
    </p>
  )
}

function Legend({ layer, focus, shares }) {
  return (
    <div className="layer-legend">
      <LegendBody
        layer={layer} focus={focusOf(focus.focuses, layer.id)} shares={shares}
        onHover={focus.onHover} onToggle={focus.onToggle} onClear={focus.onClear}
      />
    </div>
  )
}

/** One overlay group: a switch, and when on: which layer (if the group has several), its variants and its key. */
function OverlayGroup({ group, state, onOn, onLayer, onVariant, focus, showLegend, sharesOf }) {
  const o = state.overlays[group.kind]
  const chosen = group.layers.find((l) => l.id === o.layer) || group.layers[0]
  const variants = chosen.variants || []
  return (
    <Toggle
      label={group.label} checked={o.on} onChange={(v) => onOn(group.kind, v)}
      help={chosen.note ? <p>{chosen.note}</p> : undefined}
    >
      {o.on && (
        <div className="overlay-body">
          {group.layers.length > 1 && (group.layers.length <= CHIPS_MAX
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
          {showLegend && <Legend layer={chosen} focus={focus} shares={sharesOf(chosen.id)} />}
          <LayerMeta layer={chosen} />
        </div>
      )}
    </Toggle>
  )
}

export default function Sidebar({
  catalog, metrics, selectedId, onPick, view, active, onValue, onOverlayOn, onOverlayLayer, onVariant, focus,
  sheetOpen, setSheetOpen, onAbout, onCompare, sharesOf,
}) {
  const phone = usePhone()   // on a phone the key is the overlay on the map, not here
  const sel = catalog.agglomerations.find((a) => a.id === selectedId)
  const options = [
    { value: '', label: 'Cała Polska' },
    ...catalog.agglomerations.map((a) => ({ value: a.id, label: a.name })),
  ]
  const values = valueLayers(catalog.layers)
  const planned = catalog.layers.filter((l) => l.status !== 'ready' && l.kind === 'choropleth')
  const groups = overlayGroups(catalog.layers)
  const chosenValue = values.find((l) => l.id === view.value) || null
  const layerCredits = [...new Set(catalog.layers
    .filter((l) => l.status === 'ready' && active.has(l.id) && l.attribution)
    .map((l) => l.attribution))]
  const cards = [
    { value: NO_VALUE, label: 'Tylko granice', sub: 'bez kolorowania obszaru' },
    ...values.map((l) => ({ value: l.id, label: l.title, sub: l.sub || l.unit, color: rampMid(l.ramp) || layerColor(l) })),
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
        {sel?.note && <Warn>{sel.note}</Warn>}
        {!sel && <Hint>Wybierz aglomerację z listy albo kliknij jej obrys na mapie.</Hint>}
        <LinkButton block onClick={onCompare}>Porównanie miast</LinkButton>
      </Panel>

      <Panel
        title="Co pokazać"
        help={<p>Naraz widać jedną warstwę wartości, bo jej kolory zasłaniałyby się nawzajem. Nakładki poniżej można dodać do każdej z nich.</p>}
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
        {chosenValue && (
          <>
            {!phone && (
              <Field label="Legenda" help={chosenValue.note ? <p>{chosenValue.note}</p> : undefined}>
                <Legend layer={chosenValue} focus={focus} shares={sharesOf(chosenValue.id)} />
              </Field>
            )}
            {phone && chosenValue.note && (
              <Field label="O tej warstwie" help={<p>{chosenValue.note}</p>} />
            )}
            <LayerMeta layer={chosenValue} />
          </>
        )}
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
            key={g.kind} group={g} state={view} focus={focus} showLegend={!phone} sharesOf={sharesOf}
            onOn={onOverlayOn} onLayer={onOverlayLayer} onVariant={onVariant}
          />
        ))}
        {view.overlays.points?.on && <Hint>Kliknij punkt na mapie, aby zobaczyć składowe przesiadki.</Hint>}
      </Panel>
      <Footnote>
        <LinkButton onClick={() => onAbout()}>Źródła, różnice dat i ograniczenia</LinkButton>
      </Footnote>
    </Shell>
  )
}
