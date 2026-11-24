import { useEffect, useRef, useState } from 'react'
import {
  Chips, HelpButton, Hint, LinkButton, Panel, RadioCards, Select, Sidebar as Shell, Toggle,
} from '@bartor-net/ui-kit'
import { dataDates } from './layerInfo'
import { layerColor, rampMid } from './data'
import { chipLabel, overlayGroups, valueLayers, variantOf } from './layerControl'
import { firstSentence } from './helpText'

const NO_VALUE = ''   // the radio value of "Bez warstwy"
const NONE_PICKED = '\u0000'   // matches no data layer: the data-layer group when none is chosen
const CHIPS_MAX = 4   // more layers in a group than this are chosen from a list

/**
 * The short help of a layer, one pattern with the tables' "?": one sentence, the dates and the source in small print,
 * and a link to the fuller text ("O danych").
 */
function LayerHelp({ layer, onMore }) {
  const dates = dataDates(layer)
  return (
    <>
      {layer.note && <p>{firstSentence(layer.note)}</p>}
      {(dates || layer.attribution) && (
        <p className="layer-meta">
          {dates && <span>{dates}</span>}
          {layer.attribution && <span>{layer.attribution}</span>}
        </p>
      )}
      {onMore && <p><button type="button" className="more-link" onClick={onMore}>więcej w „O danych”</button></p>}
    </>
  )
}

/** One overlay group: a switch with a "?", and when on: which layer (if the group has several) and its variants. */
function OverlayGroup({ group, state, onOn, onLayer, onVariant, onMore }) {
  const o = state.overlays[group.kind]
  const chosen = group.layers.find((l) => l.id === o.layer) || group.layers[0]
  const variants = chosen.variants || []
  const chooser = o.on && group.layers.length > 1
  return (
    <Toggle
      label={group.label} checked={o.on} onChange={(v) => onOn(group.kind, v)}
      help={chosen.note || chosen.attribution ? <LayerHelp layer={chosen} onMore={onMore} /> : undefined}
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

/**
 * What the map shows: the list of value layers (one at a time) and, under "Więcej na mapie", the overlays. Global state
 * (city, area, about) is in the header. In the wide dock state the small live map sits at the bottom of this column
 * (`inset`: the box it is drawn in; the list scrolls above it); on a low window the list shrinks to the active layer.
 */
export default function Sidebar({
  catalog, view, onValue, onOverlayOn, onOverlayLayer, onVariant, sheetOpen, setSheetOpen, onAbout, flash, selectedName,
  collapsed = false,
}) {
  const [helpFor, setHelpFor] = useState(null)   // the value layer whose "?" is open
  const cards = useRef(null)
  const values = valueLayers(catalog.layers)
  const planned = catalog.layers.filter((l) => l.status !== 'ready' && l.kind === 'choropleth')
  const groups = overlayGroups(catalog.layers)
  const chosenValue = values.find((l) => l.id === view.value) || null
  const helpLayer = values.find((l) => l.id === helpFor) || null

  // a link elsewhere changed the layer: the card flashes once, so that the change in this column is seen
  useEffect(() => {
    if (!flash || !cards.current) return undefined
    const i = values.findIndex((l) => l.id === flash.id)
    const el = cards.current.querySelectorAll('.kit-card')[i]
    if (!el) return undefined
    el.classList.remove('flash')
    void el.offsetWidth
    el.classList.add('flash')
    el.scrollIntoView?.({ block: 'nearest' })
    const t = setTimeout(() => el.classList.remove('flash'), 1600)
    return () => clearTimeout(t)
  }, [flash])   // eslint-disable-line react-hooks/exhaustive-deps

  const dataCards = values.map((l) => ({
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
  }))

  return (
    <Shell
      title="Warstwy na mapie" peek={selectedName ? `${selectedName}: co pokazać` : 'co pokazać na mapie'}
      open={sheetOpen} setOpen={setSheetOpen}
    >
      {collapsed
        ? (
          <Panel title="Warstwa na mapie">
            <p className="layer-collapsed">{chosenValue ? chosenValue.title : 'Bez warstwy (tylko granice)'}</p>
          </Panel>
        )
        : (
          <>
            <Panel
              title="Warstwa na mapie"
              help={<p>Naraz widać jedną warstwę, bo jej kolory zasłaniałyby się nawzajem. Legenda jest w rogu mapy.</p>}
            >
              {values.length === 0
                ? <Hint>Warstwy pojawią się po przeliczeniu.</Hint>
                : (
                  <>
                    <div className="layer-none">
                      <RadioCards
                        name="value-layer" label="Bez warstwy"
                        value={chosenValue ? NONE_PICKED : NO_VALUE}
                        onChange={() => onValue(null)}
                        options={[{ value: NO_VALUE, label: 'Bez warstwy (tylko granice)', sub: 'sama mapa z obrysami miast' }]}
                      />
                    </div>
                    <div ref={cards} className="layer-data">
                      <RadioCards
                        name="value-layer" label="Warstwa wartości"
                        value={chosenValue ? chosenValue.id : NONE_PICKED}
                        onChange={(v) => onValue(v)}
                        options={dataCards}
                      />
                    </div>
                  </>
                )}
              {helpLayer && <div className="kit-info"><LayerHelp layer={helpLayer} onMore={onAbout} /></div>}
              {planned.length > 0 && (
                <Hint>W przygotowaniu: {planned.map((l) => l.title).join('; ')}.</Hint>
              )}
            </Panel>

            {groups.length > 0 && (
              <details className="more-map">
                <summary>Więcej na mapie</summary>
                <div className="more-map-body">
                  {groups.map((g) => (
                    <OverlayGroup
                      key={g.kind} group={g} state={view} onMore={onAbout}
                      onOn={onOverlayOn} onLayer={onOverlayLayer} onVariant={onVariant}
                    />
                  ))}
                </div>
              </details>
            )}
          </>
        )}
      <p className="sidebar-phone-link"><LinkButton onClick={onAbout}>O danych</LinkButton></p>
    </Shell>
  )
}
