import { createContext, useContext } from 'react'

/**
 * What every export needs to say about the data: {source, populationGrid, populationDate, timetableDate} (export/shape.js
 * metaFromRows). The page provides it once; without a provider the exports carry empty provenance cells.
 */
export const ExportContext = createContext({ source: '', populationGrid: '', populationDate: '', timetableDate: '' })
export const useExportMeta = () => useContext(ExportContext)
