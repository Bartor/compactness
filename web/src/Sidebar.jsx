import { useEffect, useRef, useState } from 'react'
import {
  Chips, HelpButton, Hint, LinkButton, Panel, RadioCards, Select, Sidebar as Shell, Toggle,
} from '@bartor-net/ui-kit'
import { dataDates } from './layerInfo'
import { layerColor, rampMid } from './data'
import { OVERLAY_KINDS, chipLabel, overlayGroups, sharedVariant, valueLayers, variantOf } from './layerControl'
import { DAY_FILTERS, bandsOfDay } from './features/speed/lineTable'
import { bandOf } from './features/speed/speedModel'
import { layerUrl } from './features/speed/loader'
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

/** A switch that can be disabled, with a line saying why (the kit's Toggle has no disabled state). */
function SwitchRow({ label, checked, disabled = false, why = null, onChange, children }) {
  return (
    <div className="kit-toggle">
      <div className="kit-toggle-row">
        <label>
          <input type="checkbox" className="kit-switch" checked={checked && !disabled} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
          <span>{label}</span>
        </label>
      </div>
      {why && <p className="iso-why">{why}</p>}
      {children}
    </div>
  )
}

/**
 * The scheduled-speed overlay: one switch per mode (the layers of the group are independent) and ONE chooser of day type
 * and time band for all of them. Buses exist only for the selected city, so without one that switch is off and says why.
 */
function SpeedGroup({ group, state, agg, onLayerOn, onBand, onMore }) {
  const [help, setHelp] = useState(false)
  const on = new Set(state.overlays[group.kind]?.ids || [])
  const band = bandOf(sharedVariant(state, group.kind, group.layers))
  const first = group.layers[0]
  return (
    <div className="speed-group">
      <div className="kit-toggle-row speed-group-head">
        <b>{group.label}</b>
        <HelpButton open={help} onClick={() => setHelp(!help)} />
      </div>
      {help && (
        <div className="kit-info">
          <p>Prędkość komunikacyjna z rozkładu jazdy (z postojami na przystankach), nie pomiar ruchu. Kolor to klasa prędkości, grubość to liczba kursów na godzinę.</p>
          {first && <LayerHelp layer={{ ...first, note: null }} onMore={onMore} />}
        </div>
      )}
      {group.layers.map((l) => {
        const needsCity = !!l.needs_city
        const noCity = needsCity && !agg
        const unsupported = needsCity && agg && !layerUrl(l, agg)
        return (
          <SwitchRow
            key={l.id} label={chipLabel(l)} checked={on.has(l.id)} disabled={noCity || unsupported}
            why={noCity ? 'wybierz miasto, aby zobaczyć autobusy' : unsupported ? 'dla tej aglomeracji nie ma autobusów z rozkładu' : null}
            onChange={(v) => onLayerOn(group.kind, l.id, v)}
          />
        )
      })}
      {on.size > 0 && (
        <div className="overlay-body">
          <Chips tight items={DAY_FILTERS.map((d) => ({ key: d.key, label: d.label, on: d.key === band.day }))} onPick={(d) => onBand(d, null)} />
          <Chips tight items={bandsOfDay(band.day).map((b) => ({ key: b.key, label: b.label, on: b.key === band.key }))} onPick={(k) => onBand(band.day, k)} />
          {group.layers.some((l) => l.mode_group === 'bus' && on.has(l.id)) && <p className="iso-why">Autobusy widać od przybliżenia mapy do ulic.</p>}
        </div>
      )}
    </div>
  )
}

/**
 * The switch "Dokąd dojadę stąd": a click on the map inside the selected city shows where one can get to from the nearest
 * precomputed origin. It needs a city, so without one the switch is disabled and says why.
 */
function IsoSwitch({ iso }) {
  const [help, setHelp] = useState(false)
  return (
    <div className="kit-toggle">
      <div className="kit-toggle-row">
        <label>
          <input type="checkbox" className="kit-switch" checked={iso.on && iso.enabled} disabled={!iso.enabled} onChange={(e) => iso.onChange(e.target.checked)} />
          <span>Dokąd dojadę stąd</span>
        </label>
        <HelpButton open={help} onClick={() => setHelp(!help)} />
      </div>
      {help && (
        <div className="kit-info">
          <p>Po włączeniu kliknij na mapie w obrębie miasta: pokażemy, dokąd dojedziesz komunikacją w 15, 30, 45 i 60 minut z najbliższego wyliczonego punktu. To czasy z rozkładu jazdy, nie rzeczywiste.</p>
        </div>
      )}
      {!iso.enabled && <p className="iso-why">Wybierz najpierw aglomerację (u góry strony albo klikając jej obrys na mapie).</p>}
    </div>
  )
}

/**
 * What the map shows: the list of value layers (one at a time) and, under "Więcej na mapie", the overlays. Global state
 * (city, area, about) is in the header. In the wide dock state the small live map sits at the bottom of this column
 * (`inset`: the box it is drawn in; the list scrolls above it); on a low window the list shrinks to the active layer.
 */
export default function Sidebar({
  catalog, view, onValue, onOverlayOn, onOverlayLayer, onVariant, sheetOpen, setSheetOpen, onAbout, flash, selectedName,
  collapsed = false, iso = null, agg = null, onLayerOn, onBand,
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

            {(groups.length > 0 || iso) && (
              <details className="more-map">
                <summary>Więcej na mapie</summary>
                <div className="more-map-body">
                  {groups.map((g) => (OVERLAY_KINDS[g.kind].multi
                    ? <SpeedGroup key={g.kind} group={g} state={view} agg={agg} onLayerOn={onLayerOn} onBand={onBand} onMore={onAbout} />
                    : (
                      <OverlayGroup
                      key={g.kind} group={g} state={view} onMore={onAbout}
                        onOn={onOverlayOn} onLayer={onOverlayLayer} onVariant={onVariant}
                      />
                    )))}
                  {iso && <IsoSwitch iso={iso} />}
                </div>
              </details>
            )}
          </>
        )}
      <p className="sidebar-phone-link"><LinkButton onClick={onAbout}>O danych</LinkButton></p>
    </Shell>
  )
}
