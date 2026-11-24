import { useEffect, useRef, useState } from 'react'
import { downloadBlob } from '@bartor-net/ui-kit'
import { buildCsv } from './csv'
import { exportFilename } from './filename'
import { pngSupported, svgToPngBlob } from './png'
import { useExportMeta } from './ExportContext'
import './export.css'

/**
 * The one export control of the page: "Pobierz" with the buttons "CSV" and (for an SVG chart) "PNG", and a polite status
 * line once a download has started. Same markup and place everywhere: beside the chart / table switch in a chart's
 * header, in the toolbar of a table.
 *
 * Props
 *   table      CSV rows (header first), or a function returning them (built when the button is pressed)
 *   name       {view, subject, area}: the parts of the file name (export/filename.js)
 *   getSvg     () => SVGElement | null: makes a PNG of it; without it there is no PNG button
 *   title      chart title for the picture; area: the area's name for the picture's footer
 */
export default function ExportButtons({ table, name, getSvg, title = '', area = '', className = '' }) {
  const meta = useExportMeta()
  const [status, setStatus] = useState('')
  const timer = useRef(null)
  useEffect(() => () => clearTimeout(timer.current), [])
  const say = (text) => {
    setStatus(text)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => setStatus(''), 5000)
  }
  const rows = () => (typeof table === 'function' ? table() : table)
  const csv = () => {
    const file = exportFilename({ ...name, ext: 'csv' })
    downloadBlob(new Blob([buildCsv(rows())], { type: 'text/csv;charset=utf-8' }), file)
    say(`Pobieranie: ${file}`)
  }
  const png = async () => {
    const svg = getSvg?.()
    if (!svg) return say('Nie ma wykresu do zapisania (przełącz na widok „Wykres”).')
    try {
      const file = exportFilename({ ...name, ext: 'png' })
      const blob = await svgToPngBlob(svg, { title, area, date: meta.timetableDate || meta.populationDate, source: meta.source })
      downloadBlob(blob, file)
      say(`Pobieranie: ${file}`)
    } catch (e) {
      say(e?.message || 'Nie udało się zapisać obrazu.')
    }
  }
  const withPng = !!getSvg && pngSupported()
  return (
    <span className={`exp ${className}`.trim()}>
      <span className="exp-label">Pobierz</span>
      <button type="button" className="exp-btn" aria-label="Pobierz CSV" title="Pobierz dane jako plik CSV" onClick={csv}>CSV</button>
      {withPng && (
        <button type="button" className="exp-btn" aria-label="Pobierz obraz PNG" title="Pobierz wykres jako obraz PNG" onClick={png}>PNG</button>
      )}
      <span className="exp-status" role="status" aria-live="polite">{status}</span>
    </span>
  )
}
