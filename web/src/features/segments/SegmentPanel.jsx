import { useEffect, useMemo, useState } from 'react'
import { createPortal } from 'react-dom'
import { DetailsPanel, Fact, Facts, Hint, Notes, Slider } from '@bartor-net/ui-kit'
import { MODE_PL, bandOf, bandText } from '../speed/speedModel'
import {
  CENTRAL, RANGES, addIds, featureSummary, linesAt, patternIds, stretchIds, summary, whatIf,
} from './segModel'
import { NO_DATA, duration, mmss, nf, num, plural, speedText, tphText } from './segText'
import './segments.css'

const ACCENT = '#4A6EA9'
const short = (key) => {
  const b = bandOf(key)
  const m = b.label.match(/\d\d–\d\d/)
  return `${b.day === 'weekday' ? 'śr.' : 'sob.'} ${m ? m[0] : b.label.replace(/ \d.*$/, '')}`
}
const TAF_NOTE = 'Model, nie pomiar: czas z rozkładu minus czas prostego modelu jazdy (rozpędzanie, limit prędkości, '
  + 'hamowanie, postój na przystanku). Zawiera sygnalizację, ograniczenia prędkości, wymianę pasażerów i rezerwy rozkładu. '
  + 'Przedział: postój 10–30 s i limit 40–70 km/h tam, gdzie OSM nie podaje limitu.'

/**
 * The panel of a selection of speed features, on the right of the map (a bottom sheet on a phone): what is selected,
 * its scheduled time and speed with the rounding interval, trips, lines, time above free running and the what-if
 * (trams). Props: sel {mode, ids}; band; tram {status, data: segModel.parseDetail}; feats {status, data: {byId}} for
 * bus and rail; lastId (the segment clicked last); cityName; dates; onIds(ids); onClear(); onBand(key).
 */
export default function SegmentPanel({ sel, band, tram, feats, lastId, cityName, dates, onIds, onClear, onBand }) {
  const isTram = sel.mode === 'tram'
  const phone = usePhoneWidth()
  const src = isTram ? tram : feats
  const ready = src?.status === 'ready' && src.data
  let body
  if (!ready) {
    body = <p className="seg-muted">{src?.status === 'error' ? 'Nie udało się wczytać danych zaznaczenia.' : 'Wczytywanie danych zaznaczenia…'}</p>
  } else if (isTram) {
    body = <TramBody model={src.data} ids={sel.ids} band={band} lastId={lastId} onIds={onIds} onBand={onBand} />
  } else {
    const props = sel.ids.map((id) => src.data.byId.get(id)?.properties).filter(Boolean)
    body = <FeatureBody props={props} band={band} mode={sel.mode} />
  }
  const title = isTram && ready ? tramTitle(src.data, sel.ids) : featureTitle(ready ? src.data : null, sel)
  const panel = (
    <div className="seg-panel">
      <DetailsPanel pill={MODE_PL[sel.mode === 'rail' ? 'rail' : sel.mode] || sel.mode} title={title} color={ACCENT} onClose={onClear}
        actions={<p className="seg-sub">{cityName ? `${cityName} · ` : ''}{bandText(band)} · z rozkładu, nie pomiar</p>}
      >
        <div className="seg-tools">
          <button type="button" className="seg-btn" onClick={onClear}>Wyczyść zaznaczenie</button>
          <span className="seg-tip">Klikaj odcinki na mapie, by dodać lub odjąć.</span>
        </div>
        {body}
        <p className="seg-foot">
          Rozkłady: {dates ? `środa ${dates.weekday}, sobota ${dates.saturday}` : 'środa i sobota'}; OSM 2026-11-22. Czasy i prędkości z rozkładu jazdy, nie pomiar.
        </p>
      </DetailsPanel>
    </div>
  )
  // a phone: the sheet goes to the end of the page, above the city's sheet (the map's box would trap it underneath)
  return phone && typeof document !== 'undefined' ? createPortal(panel, document.body) : panel
}

const PHONE = '(max-width: 760px)'
function usePhoneWidth() {
  const get = () => typeof window !== 'undefined' && window.matchMedia(PHONE).matches
  const [on, setOn] = useState(get)
  useEffect(() => {
    const mq = window.matchMedia(PHONE)
    const f = () => setOn(mq.matches)
    mq.addEventListener('change', f)
    return () => mq.removeEventListener('change', f)
  }, [])
  return on
}

function tramTitle(model, ids) {
  const segs = ids.map((id) => model.byId.get(id)).filter(Boolean)
  if (!segs.length) return 'Zaznaczenie'
  const s = summary(model, ids, model.keys[0])
  if (s?.names) return `${s.names[0]} → ${s.names[s.names.length - 1]}`
  return `${segs.length} ${plural(segs.length, 'odcinek', 'odcinki', 'odcinków')} w ${s.pieces} ${plural(s.pieces, 'kawałku', 'kawałkach', 'kawałkach')}`
}
function featureTitle(data, sel) {
  const ps = data ? sel.ids.map((id) => data.byId.get(id)?.properties).filter(Boolean) : []
  if (ps.length === 1) return ps[0].name || (ps[0].line ? `Linia ${ps[0].line}` : 'Odcinek')
  return `${sel.ids.length} ${plural(sel.ids.length, 'element', 'elementy', 'elementów')}`
}

// ------------------------------------------------------------------ trams
function TramBody({ model, ids, band, lastId, onIds, onBand }) {
  const s = useMemo(() => summary(model, ids, band), [model, ids, band])
  const last = lastId && model.byId.has(lastId) ? lastId : ids[ids.length - 1]
  const lines = useMemo(() => (last ? linesAt(model, last, band) : []), [model, last, band])
  if (!s) return <p className="seg-muted">Tego zaznaczenia nie ma w danych (inna wersja rozkładu?).</p>
  const lastSeg = model.byId.get(last)
  const lastName = lastSeg ? `${model.places[lastSeg.a]} → ${model.places[lastSeg.b]}` : ''
  return (
    <>
      <section className="seg-block" aria-label="Szybkie zaznaczanie">
        <h4>Rozszerz zaznaczenie</h4>
        <p className="seg-small">od odcinka {lastName}:</p>
        <div className="seg-chips">
          {lastSeg?.stretch && (
            <button type="button" className="seg-chip" onClick={() => onIds(addIds(ids, stretchIds(model, last)))}>cały odcinek między węzłami</button>
          )}
          {lines.map((l) => (
            <button key={l.ld} type="button" className="seg-chip" title={`Linia ${l.line}: ${l.name || ''}`}
              onClick={() => onIds(addIds(ids, patternIds(model, last, l.ld)))}
            >
              linia {l.line} w tym kierunku{l.name ? ` (do ${l.name.split(' → ').pop()})` : ''}
            </button>
          ))}
        </div>
      </section>
      <Selected s={s} />
      <BandStrip strip={s.strip} band={band} onBand={onBand} />
      <section className="seg-block">
        <h4>Czas ponad jazdę swobodną (model)</h4>
        <Facts>
          <Fact label="Na kilometr, środek (przedział)" tone="now">
            {s.taf ? (s.taf.faster ? 'rozkład szybszy niż model' : `${nf(s.taf.taf, 0)} s/km (${nf(s.taf.lo, 0)}–${nf(s.taf.hi, 0)})`) : NO_DATA}
          </Fact>
          <Fact label="Na cały przejazd">{s.taf && !s.taf.faster ? duration(s.taf.T - s.taf.free) : NO_DATA}</Fact>
          <Fact label="Jazda swobodna (model)">{s.taf ? duration(s.taf.free) : NO_DATA}</Fact>
        </Facts>
        {s.taf?.faster && <Hint>Rozkład jest tu szybszy niż model jazdy swobodnej (zwykle torowisko wydzielone z limitem wyższym niż przyjęty); czasu ponad jazdę swobodną nie podajemy.</Hint>}
        <Hint>{TAF_NOTE}</Hint>
      </section>
      <WhatIf model={model} ids={ids} band={band} s={s} />
      <section className="seg-block">
        <h4>Tor (OSM)</h4>
        <Facts>
          <Fact label="W jezdni (dolne oszacowanie)">{s.osm.st == null ? NO_DATA : `${nf(s.osm.st * 100, 0)} %`}</Fact>
          <Fact label="Skrzyżowania z drogą (z sygnalizacją)">{s.osm.x == null ? NO_DATA : `${nf(s.osm.x, 0)} (${s.osm.xs == null ? NO_DATA : nf(s.osm.xs, 0)})`}</Fact>
          <Fact label="Przejścia poza skrzyżowaniami">{num(s.osm.xp, '', 0)}</Fact>
          <Fact label="Rozjazdy">{num(s.osm.sw, '', 0)}</Fact>
        </Facts>
        <Hint>Suma po odcinkach między przystankami. Skrzyżowanie leżące dokładnie na przystanku nie jest liczone.</Hint>
      </section>
    </>
  )
}

function Selected({ s, feature = false, rail = false }) {
  const pieces = s.errMin
  const words = rail ? ['linia', 'linie', 'linii'] : ['odcinek', 'odcinki', 'odcinków']
  return (
    <section className="seg-block">
      <h4>Zaznaczenie</h4>
      <p className="seg-lead">
        {s.count} {plural(s.count, ...words)}
        {s.lengthM != null ? `, ${nf(s.lengthM / 1000, 2)} km` : ''}
        {s.stops ? `, ${s.stops} ${plural(s.stops, 'przystanek', 'przystanki', 'przystanków')}` : ''}
      </p>
      {s.names
        ? <p className="seg-stops">{s.names.join(' › ')}</p>
        : !feature && s.pieces > 1 && <p className="seg-small">To kilka osobnych kawałków ({s.pieces}); niżej sumy długości i czasu.</p>}
      <Facts>
        <Fact label="Czas przejazdu" tone={rail ? undefined : s.timeS == null ? 'gap' : 'now'}>
          {rail ? 'cała linia, bez długości odcinka w danych' : s.timeS == null ? 'brak kursów w tym paśmie' : `${duration(s.timeS)} (±${pieces} min)`}
        </Fact>
        <Fact label="Prędkość z rozkładu" tone="now">
          {rail
            ? (s.speeds?.length ? s.speeds.map((v) => nf(v, 1)).join('; ') + ' km/h' : 'brak kursów w tym paśmie')
            : s.zeroTime ? '0 min w rozkładzie' : speedText(s.speed, s.interval, pieces)}
        </Fact>
        <Fact label="Kursy na godzinę">{tphText(s.tph)}</Fact>
        <Fact label="Linie">{s.lines.length ? s.lines.join(', ') : NO_DATA}</Fact>
      </Facts>
      {s.served != null && s.served < s.count && (
        <Hint>{s.count - s.served} z {s.count} odcinków nie ma kursów w tym paśmie: czas i prędkość dotyczą pozostałych.</Hint>
      )}
      {!rail && <Hint>
        {feature
          ? `Rozkład podaje pełne minuty, więc czas każdego zaznaczonego elementu może się różnić o ±1 min; razem ±${pieces} min.`
          : pieces <= 1
            ? 'Rozkład podaje pełne minuty. Na ciągłym fragmencie zaokrąglenia zostają tylko na jego dwóch końcach (czasy na przystankach pośrodku się znoszą), więc czas całości może się różnić o ±1 min. Im dłuższe zaznaczenie, tym węższy przedział.'
            : `Rozkład podaje pełne minuty. Każdy z ${pieces} osobnych kawałków może się różnić o ±1 min, więc suma o ±${pieces} min.`}
      </Hint>}
    </section>
  )
}

function BandStrip({ strip, band, onBand }) {
  const max = Math.max(30, ...strip.map((b) => b.value || 0))   // a fixed scale from 0 to at least 30 km/h
  return (
    <section className="seg-block">
      <h4>Prędkość w innych pasmach</h4>
      <div className="seg-strip" role="list">
        {strip.map((b) => (
          <button
            key={b.key} type="button" role="listitem" className={`seg-bar${b.key === band ? ' on' : ''}${b.value == null ? ' missing' : ''}${b.partial ? ' partial' : ''}`}
            title={`${bandText(b.key)}: ${b.value == null ? 'brak kursów' : `${nf(b.value, 1)} km/h${b.partial ? ' (nie wszystkie odcinki mają kursy)' : ''}`}`}
            aria-label={`${bandText(b.key)}: ${b.value == null ? NO_DATA : `${nf(b.value, 1)} km/h`}`}
            onClick={() => onBand?.(b.key)}
          >
            <i style={{ height: `${max > 0 && b.value ? Math.round((b.value / max) * 100) : 0}%`, background: b.color || undefined }} />
            <span>{short(b.key).replace('śr. ', '').replace('sob. ', '')}</span>
          </button>
        ))}
      </div>
      <p className="seg-strip-days"><span>środa</span><span>sobota</span></p>
      <Hint>Całe zaznaczenie. Blady słupek: w tym paśmie nie wszystkie odcinki mają kursy (liczone z pozostałych); kreskowane pole: brak kursów. Kliknięcie zmienia pasmo mapy.</Hint>
    </section>
  )
}

// ------------------------------------------------------------------ what if
function WhatIf({ model, ids, band, s }) {
  const [open, setOpen] = useState(false)
  const [mode, setMode] = useState('share')
  const [share, setShare] = useState(50)
  const base = s.speed ? Math.ceil(s.speed) : 15
  const [target, setTarget] = useState(null)
  const [p, setP] = useState({ ...CENTRAL })
  const tgt = target ?? Math.min(60, base + 3)
  const plan = mode === 'share' ? { mode, share: share / 100 } : { mode, target: tgt }
  const w = useMemo(() => (open ? whatIf(model, ids, p, plan) : null), [open, model, ids, p, mode, share, tgt])   // eslint-disable-line react-hooks/exhaustive-deps
  const cur = w?.bands.find((b) => b.key === band)
  const changed = p.dwell_s !== CENTRAL.dwell_s || p.v_cap_kmh !== CENTRAL.v_cap_kmh || p.a_acc !== CENTRAL.a_acc || p.b_brk !== CENTRAL.b_brk
  return (
    <section className="seg-block seg-whatif">
      <button type="button" className="seg-fold" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span aria-hidden="true">{open ? '▾' : '▸'}</span> Co by było, gdyby tramwaj jechał tu szybciej?
      </button>
      {open && w && (
        <div className="seg-whatif-body">
          <p className="seg-warn">
            To arytmetyka rozkładu, nie prognoza. Nie mówi, jak to osiągnąć ani ile to kosztuje. To, dokąd mieszkańcy
            dojadą szybciej, wymaga wyznaczania tras; policzyliśmy to raz, dla Wrocławia (raport, rozdział 23).
          </p>
          <div className="seg-mode" role="radiogroup" aria-label="Rodzaj zmiany">
            <label><input type="radio" name="seg-mode" checked={mode === 'share'} onChange={() => setMode('share')} /> usuń część czasu ponad jazdę swobodną</label>
            <label><input type="radio" name="seg-mode" checked={mode === 'target'} onChange={() => setMode('target')} /> prędkość docelowa na zaznaczeniu</label>
          </div>
          {mode === 'share'
            ? <Slider caption={<>Usunięta część: <b>{share}&nbsp;%</b></>} label="Usunięta część czasu ponad jazdę swobodną" value={share} min={0} max={100} step={5} onChange={setShare} />
            : <Slider caption={<>Prędkość docelowa: <b>{nf(tgt, 1)}&nbsp;km/h</b></>} label="Prędkość docelowa, km/h" value={tgt} min={Math.max(5, base - 5)} max={60} step={0.5} onChange={setTarget} />}
          <Hint>Żaden odcinek nie jedzie szybciej niż w modelu jazdy swobodnej, a zaznaczenie nigdy nie zwalnia. Zmiana w każdym paśmie osobno.</Hint>
          <details className="seg-params">
            <summary>Parametry modelu jazdy swobodnej{changed ? ' (zmienione)' : ''}</summary>
            <Slider caption={<>Postój na przystanku: <b>{p.dwell_s}&nbsp;s</b></>} label="Postój, s" value={p.dwell_s} min={RANGES.dwell_s[0]} max={RANGES.dwell_s[1]} step={RANGES.dwell_s[2]} onChange={(v) => setP({ ...p, dwell_s: v })} />
            <Slider caption={<>Limit prędkości tam, gdzie OSM go nie podaje: <b>{p.v_cap_kmh}&nbsp;km/h</b></>} label="Limit prędkości, km/h" value={p.v_cap_kmh} min={RANGES.v_cap_kmh[0]} max={RANGES.v_cap_kmh[1]} step={RANGES.v_cap_kmh[2]} onChange={(v) => setP({ ...p, v_cap_kmh: v })} />
            <Slider caption={<>Przyspieszanie: <b>{nf(p.a_acc, 2)}&nbsp;m/s²</b></>} label="Przyspieszanie, m/s²" value={p.a_acc} min={RANGES.a_acc[0]} max={RANGES.a_acc[1]} step={RANGES.a_acc[2]} onChange={(v) => setP({ ...p, a_acc: v })} />
            <Slider caption={<>Hamowanie: <b>{nf(p.b_brk, 2)}&nbsp;m/s²</b></>} label="Hamowanie, m/s²" value={p.b_brk} min={RANGES.b_brk[0]} max={RANGES.b_brk[1]} step={RANGES.b_brk[2]} onChange={(v) => setP({ ...p, b_brk: v })} />
            <button type="button" className="seg-btn" disabled={!changed} onClick={() => setP({ ...CENTRAL })}>Przywróć 20 s, 50 km/h, 1,0 m/s²</button>
          </details>
          <h5>Wybrane pasmo: {bandText(band)}</h5>
          {cur && cur.timeS != null
            ? (
              <Facts>
                <Fact label="Czas przejazdu" tone="now">{duration(cur.timeS)} → {duration(cur.newTimeS)}</Fact>
                <Fact label="Prędkość z rozkładu" tone="now">{num(cur.speed, 'km/h')} → {num(cur.newSpeed, 'km/h')}</Fact>
                <Fact label="Oszczędność na przejazd">{duration(cur.savedS)}</Fact>
              </Facts>
            )
            : <p className="seg-muted">W tym paśmie zaznaczenie nie ma kursów.</p>}
          <h5>Cała środa</h5>
          <Facts>
            <Fact label="Wozogodziny mniej" tone="now">{num(w.vehHoursWeekday, 'h', 1)}</Fact>
            <Fact label="Wagony wolne w szczycie 07–09">{w.vehiclesPeak == null ? NO_DATA : `ok. ${nf(w.vehiclesPeak, 1)}`}</Fact>
          </Facts>
          <Hint>
            Wozogodziny: kursy × oszczędność, suma po pasmach środy. Wagony: oszczędność × kursy na godzinę / 3600 przy
            tych samych odstępach; obraz wyidealizowany (zakłada, że krótszy obieg da się tak zaplanować).
          </Hint>
          <BandTable w={w} band={band} />
          <LineTable w={w} band={band} />
        </div>
      )}
    </section>
  )
}

function BandTable({ w, band }) {
  const rows = w.bands.filter((b) => b.timeS != null)
  if (!rows.length) return null
  return (
    <div className="seg-table-wrap">
      <table className="seg-table">
        <caption>Zaznaczenie w pasmach</caption>
        <thead><tr><th scope="col">Pasmo</th><th scope="col">Czas teraz (min:s)</th><th scope="col">Oszczędność</th><th scope="col">km/h teraz → potem</th></tr></thead>
        <tbody>
          {rows.map((b) => (
            <tr key={b.key} className={b.key === band ? 'on' : undefined}>
              <th scope="row">{short(b.key)}</th>
              <td>{mmss(b.timeS)}</td>
              <td>{mmss(b.savedS)}</td>
              <td>{num(b.speed, '', 1)} → {num(b.newSpeed, '', 1)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function LineTable({ w, band }) {
  if (!w.lines.length) return null
  return (
    <div className="seg-table-wrap">
      <table className="seg-table">
        <caption>Linie, które tu jeżdżą ({short(band)}; wozogodziny i wagony: środa)</caption>
        <thead>
          <tr><th scope="col">Linia, kierunek</th><th scope="col">Na kurs (min:s)</th><th scope="col">Prędkość linii</th><th scope="col">Wozo&shy;godziny</th><th scope="col">Wagony 07–09</th></tr>
        </thead>
        <tbody>
          {w.lines.map((l) => {
            const x = l.per.find((q) => q?.key === band)
            return (
              <tr key={l.ld}>
                <th scope="row"><b>{l.line}</b> <small>{l.name ? `do ${l.name.split(' → ').pop()}` : ''}</small></th>
                <td>{x ? mmss(x.savedS) : '–'}</td>
                <td>{x && x.speed != null ? `${nf(x.speed, 1)} → ${x.newSpeed != null ? nf(x.newSpeed, 1) : NO_DATA}` : '–'}</td>
                <td>{l.vehHours == null ? '–' : nf(l.vehHours, 1)}</td>
                <td>{l.vehPeak == null ? '–' : nf(l.vehPeak, 2)}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
      <Hint>Na kurs: średnia oszczędność na kurs linii w tym kierunku (część kursów nie przejeżdża całego zaznaczenia). Prędkość linii: cała trasa, z rozkładu.</Hint>
    </div>
  )
}

// ------------------------------------------------------------------ buses, metro and rail
function FeatureBody({ props, band, mode }) {
  const s = useMemo(() => featureSummary(props, band), [props, band])
  if (!s) return <p className="seg-muted">Tego zaznaczenia nie ma w danych.</p>
  return (
    <>
      <Selected s={{ ...s, stops: null }} feature rail={mode === 'rail'} />
      <Notes>
        <li>
          {mode === 'bus'
            ? 'Autobusy i trolejbusy są na mapie dłuższymi odcinkami (pliki z odcinkami między przystankami byłyby za duże); model jazdy swobodnej jest tylko dla tramwajów.'
            : 'Metro i kolej są na mapie całymi liniami; model jazdy swobodnej jest tylko dla tramwajów.'}
        </li>
      </Notes>
    </>
  )
}

