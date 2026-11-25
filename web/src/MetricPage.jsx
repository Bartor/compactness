import { useEffect } from 'react'
import { DataTable, Hint } from '@bartor-net/ui-kit'
import {
  AtLeastCurve, Dumbbell, RankBars, ReachCurve, TimeOfDay, atLeastSeries, dumbbellRows, floorOf,
  headwaySeries, reachSeries, timeOfDayRows,
} from './features/charts'
import { DOMAIN_INFO, METRIC_INFO } from './metricInfo'
import { formatValue } from './metrics'
import { metricName, metricUnit, plainText } from './metricTable'
import {
  cityValues, densityBars, directionBadge, medianOf, neighbours, pageAreas, pageText, partnerOf, ranks, relatedBlocks,
  rowsOf, sourceFacts, universe, walkOrder,
} from './metricPageData'
import { cityColors } from './chartLink'
import StackBars from './kitx/StackBars'
import ExportButtons from './export/ExportButtons'
import { metricTable } from './export/shape'
import './metricPage.css'

const areaName = (a) => DOMAIN_INFO[a]?.short || a

/** The large page of one metric: all cities, one area at a time, how to read it, related charts and sources. */
export default function MetricPage({
  id, area, asked = area, from = null, index, cities, everyCity, names, charts, form, densityColors, layers, link,
  onClose, onNavigate, onPickCity, onShowLayer, info = METRIC_INFO,
}) {
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape' && !document.querySelector('dialog[open]')) onClose() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const name = metricName(index, id, info)
  const unit = metricUnit(index, id)
  const better = info[id]?.better ?? null
  const nav = neighbours(walkOrder(index), id)
  const areas = pageAreas(index, id)
  const text = pageText(id, info)
  const badge = directionBadge(better)
  const cityIds = universe(index, id, everyCity, cities)
  const { have, missing } = area ? cityValues(index, id, area, cityIds) : { have: [], missing: cityIds }
  const median = medianOf(have.map((h) => h.value))
  const rank = ranks(have, better)
  const fmt = (v) => (v == null ? 'brak danych' : formatValue({ value: v, unit }).text)
  const tick = (v) => formatValue({ value: v, unit: '' }).text
  const colors = cityColors(from, link.pinned)
  const mapLayer = info[id]?.layer && layers.find((l) => l.id === info[id].layer && l.status === 'ready')
  const facts = sourceFacts(rowsOf(index, id))
  const nameOf = (c) => names[c] || c
  const lines = { hot: link.hot, onHot: link.setHot, pinned: link.pinned, onPin: link.onPin }
  const nm = (mid) => metricName(index, mid, info)

  // ---- areas side by side
  const areaCols = [
    ...areas.map((a) => ({ key: a, head: areaName(a), title: DOMAIN_INFO[a]?.title || a, help: DOMAIN_INFO[a] ? <p>{DOMAIN_INFO[a].read}</p> : undefined })),
    { key: 'pos', head: 'Poz.', title: `Miejsce wśród miast w obszarze „${area ? areaName(area) : ''}”`, narrow: true },
  ]
  const tableCities = cityIds.filter((c) => areas.some((a) => index[id]?.[c]?.[a] && cityValues(index, id, a, [c]).have.length))
  const tableRows = tableCities.map((c) => ({
    id: c,
    label: <button type="button" className="metric-city" onClick={() => onPickCity(c)}>{nameOf(c)}</button>,
    name: nameOf(c),
    labelValue: nameOf(c),
    cells: [
      ...areas.map((a) => {
        const row = index[id]?.[c]?.[a]
        const v = row && Number.isFinite(row.value) ? row.value : null
        return v == null ? null : { content: plainText(row), value: v, title: formatValue(row).text }
      }),
      rank[c] ? { content: `${rank[c]}/${have.length}`, value: rank[c], tone: better && rank[c] === 1 ? 'best' : better ? undefined : 'dim' } : null,
    ],
  }))

  // ---- related blocks (each only when its data exists)
  const blocks = relatedBlocks(id).map((b, k) => ({ b, k, el: relatedBlock(b) })).filter((x) => x.el)
  function relatedBlock(b) {
    if (b.type === 'twin' || b.type === 'pair30v45') {
      const p = partnerOf(id, b.type)
      if (!p || !index[p.a] || !index[p.b] || !area) return null
      const rows = cityIds.map((c) => ({
        key: c, label: nameOf(c),
        a: cityValues(index, p.a, area, [c]).have[0]?.value ?? null, b: cityValues(index, p.b, area, [c]).have[0]?.value ?? null,
      }))
      if (!rows.some((r) => r.a != null && r.b != null)) return null
      return (
        <Dumbbell
          rows={rows} aLabel={p.aLabel} bLabel={p.bLabel} unit={unit === '%' ? '%' : unit} selected={from} sort={null} {...lines}
          title={b.type === 'twin' ? `Wskaźnik porównawczy i typowy mieszkaniec: ${areaName(area)}` : `Zasięg w 30 i w 45 min: ${areaName(area)}`}
          note={b.type === 'twin' ? 'Pierwszy wiersz: porównujemy nim miasta. Drugi: wartość dla przeciętnej osoby.' : undefined}
        />
      )
    }
    if (!charts) return null
    if (b.type === 'atleast') {
      const series = atLeastSeries(charts, { series: b.series })
      if (!series.some((s) => s.ys)) return null
      return (
        <AtLeastCurve
          series={series} colors={colors} floor={b.floor ? floorOf(charts, b.floor) ?? undefined : undefined} height={260}
          hotSeries={link.hot} onHotSeries={link.setHot} pinnedSeries={link.pinned} onPinSeries={link.onPin}
          title={`Odsetek mieszkańców z zasięgiem co najmniej X (${b.series.endsWith('45') ? '45' : '30'} min)`}
          xLabel="zasięg, % ludności z okolicy"
        />
      )
    }
    if (b.type === 'reach') {
      const series = reachSeries(charts, { mode: b.mode })
      if (!series.some((s) => s.rom)) return null
      return <ReachCurve series={series} focus={from || undefined} colors={colors} {...lines} height={260} />
    }
    if (b.type === 'timeofday') {
      const c = from || link.pinned[0] || cities[0]
      const rows = timeOfDayRows(charts, { agg: c })
      if (!rows.some((r) => r.v30 != null || r.v45 != null)) return null
      return <TimeOfDay rows={rows} title={`Pory dnia: ${nameOf(c)}`} height={240} />
    }
    if (b.type === 'headway') {
      const series = headwaySeries(charts)
      if (!series.some((s) => s.ys)) return null
      return (
        <AtLeastCurve
          series={series} unit="min" what="kursy" colors={colors} height={260}
          hotSeries={link.hot} onHotSeries={link.setHot} pinnedSeries={link.pinned} onPinSeries={link.onPin}
          title="Odsetek mieszkańców z kursami co najwyżej co N min" xLabel="odstęp między kursami, min"
        />
      )
    }
    if (b.type === 'dumbbell') {
      const d = dumbbellRows(charts, b.pair)
      if (!d.rows.some((r) => r.a != null && r.b != null)) return null
      return <Dumbbell {...d} title={d.label} selected={from} {...lines} />
    }
    if (b.type === 'density') {
      const rows = densityBars(form, cityIds, area, densityColors)
      if (!rows.length) return null
      return (
        <div>
          <h3 className="metric-h3">Mieszkańcy według gęstości komórki 250 m</h3>
          <StackBars
            rows={rows.map((r) => ({ ...r, onPick: () => onPickCity(r.key) }))} label="Mieszkańcy według gęstości zaludnienia"
            hot={link.hot} onHot={link.setHot} pinned={link.pinned}
          />
          <p className="metric-note">Klasy jak warstwa gęstości na mapie. {area === 'core' ? 'Rdzeń miasta.' : 'Cały obszar funkcjonalny.'}</p>
        </div>
      )
    }
    return null
  }

  return (
    <article className="metric-page" aria-label={`Miara: ${name}`}>
      <nav className="metric-nav" aria-label="Nawigacja po miarach">
        <button type="button" className="metric-back" onClick={onClose}>← wróć</button>
        <span className="metric-walk">
          <button type="button" disabled={!nav?.prev} onClick={() => nav?.prev && onNavigate(nav.prev)} title={nav?.prev ? nm(nav.prev) : undefined}>
            ‹ Poprzednia miara
          </button>
          <button type="button" disabled={!nav?.next} onClick={() => nav?.next && onNavigate(nav.next)} title={nav?.next ? nm(nav.next) : undefined}>
            Następna miara ›
          </button>
        </span>
      </nav>

      <header className="metric-head">
        <h1>{name}</h1>
        <p className="metric-meta">
          {unit && <span>jednostka: {unit}</span>}
          {nav && <span>{nav.groupTitle}</span>}
          {badge && <span className="metric-badge">{badge}</span>}
        </p>
      </header>

      {text.lead && <p className="metric-lead">{text.lead}</p>}

      <section className="metric-section" aria-label="Wszystkie miasta">
        {area && (
          <p className="metric-note">
            Obszar: <b>{areaName(area)}</b> (przełącznik u góry strony). {DOMAIN_INFO[area]?.read}
            {asked && asked !== area ? ` Ta miara nie ma wartości w obszarze „${areaName(asked)}”, więc pokazujemy najbliższy.` : ''}
          </p>
        )}
        {have.length > 0
          ? (
            <RankBars
              rows={have.map((h) => ({ key: h.id, label: nameOf(h.id), value: h.value }))} median={median} better={better}
              label={`${name}${unit ? `, ${unit}` : ''}`} title={`${name}: ${area ? areaName(area) : ''}`}
              format={fmt} tickFormat={tick} selected={from} colors={colors} {...lines} unit={unit}
              exportInfo={{ view: 'miara', subject: id, area: { id: area, label: areaName(area) } }}
              medianLabel={`mediana ${have.length} miast`}
            />
          )
          : <Hint>Ta miara nie ma wartości w wybranym obszarze.</Hint>}
        {missing.length > 0 && <p className="metric-missing">brak danych: {missing.map(nameOf).join(', ')}</p>}
      </section>

      {/* with one area the table would repeat the chart above (its "Tabela" switch gives the same numbers) */}
      {areas.length > 1 && tableRows.length > 0 && (
        <section className="metric-section">
          <h2>Obszary obok siebie</h2>
          <DataTable
            caption={`${name}: miasta i obszary`} labelHead="Miasto" className="metric-areas" columns={areaCols} rows={tableRows}
            sortBy="column" density="compact" resizable="all" widthsKey="compactness-metric" maxHeight="none"
            toolbar={(
              <ExportButtons
                table={() => metricTable({ index, id, cityIds, names, areas, area, info })}
                name={{ view: 'miara', subject: id, area }}
              />
            )}
          />
          <p className="metric-note">Kliknij nazwę miasta, aby przejść do jego miar. „–” oznacza brak danych, a nie zero.</p>
        </section>
      )}

      {blocks.length > 0 && (
        <section className="metric-section" aria-label="Powiązane wykresy">
          <h2>Powiązane</h2>
          <div className="metric-related">
            {blocks.map(({ b, k, el }) => <div key={`${b.type}-${k}`} className="metric-block">{el}</div>)}
          </div>
        </section>
      )}

      <section className="metric-prose">
        {text.read.length > 0 && <><h2>Jak czytać</h2>{text.read.map((p) => <p key={p}>{p}</p>)}</>}
        {text.method.length > 0 && <><h2>Jak policzono</h2>{text.method.map((p) => <p key={p}>{p}</p>)}</>}
        {text.uncertainty.length > 0 && <p className="metric-uncertainty">{text.uncertainty.join(' ')}</p>}
        {facts.length > 0 && (
          <>
            <h2>Źródła i daty</h2>
            <dl className="metric-facts">
              {facts.map((f) => (
                <div key={f.label}><dt>{f.label}</dt><dd>{f.values.map((v) => <span key={v}>{v}</span>)}</dd></div>
              ))}
            </dl>
          </>
        )}
        {text.gaps.length > 0 && <p className="metric-note">Brak tekstu dla tej miary: {text.gaps.join(', ')}.</p>}
      </section>

      {mapLayer && (
        <p className="metric-map">
          <button type="button" className="metric-show" onClick={() => onShowLayer(mapLayer.id)}>Pokaż na mapie</button>
        </p>
      )}
    </article>
  )
}
