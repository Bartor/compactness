import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { createElement as h } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import SurveyContext from './SurveyContext'
import { barSegments, loadSurveyContext, pl, surveyView } from './surveyModel'

// the real file written by pipeline/survey_context.py
const DATA = JSON.parse(readFileSync(resolve(__dirname, '../../../../results/web/survey_context.json'), 'utf-8'))
const html = (agg, data = DATA) => renderToStaticMarkup(h(SurveyContext, { data, agg }))
const AGGS = ['warszawa', 'krakow', 'wroclaw', 'poznan', 'lodz', 'trojmiasto', 'gzm']

describe('the survey file', () => {
  it('has a record for every agglomeration and a source for every number', () => {
    for (const a of AGGS) {
      const r = DATA.agglomerations[a]
      expect(r, a).toBeTruthy()
      const nums = []
      const walk = (x) => {
        if (x && typeof x === 'object') {
          if ('v' in x) nums.push(x)
          else Object.values(x).forEach(walk)
        }
      }
      walk(r)
      for (const n of nums) {
        expect(DATA.sources[n.src], `${a}: ${JSON.stringify(n)}`).toBeTruthy()
        expect(n.loc, `${a}: ${JSON.stringify(n)}`).toBeTruthy()
      }
    }
  })
  it('never puts 0 where a share is not published', () => {
    expect(DATA.agglomerations.krakow.modal_split.walk).toBeNull()
    expect(DATA.agglomerations.gzm.modal_split).toBeNull()
    expect(DATA.agglomerations.lodz.modal_split).toBeNull()
  })
})

describe('bar segments', () => {
  it('keeps the published modes in order and shows the unpublished rest separately', () => {
    const p = barSegments(DATA.agglomerations.poznan.modal_split)
    expect(p.segments.map((s) => s.mode)).toEqual(['walk', 'bike', 'pt'])
    expect(p.rest).toBe(37.3)
    const w = barSegments(DATA.agglomerations.wroclaw.modal_split)
    expect(w.segments.map((s) => s.value)).toEqual([33.1, 4.7, 21.6, 39.8, 0.8])
    expect(w.rest).toBeNull()
    expect(barSegments(null)).toEqual({ segments: [], rest: null })
  })
  it('writes Polish decimals', () => expect(pl(21.6)).toBe('21,6'))
})

describe('the view per city', () => {
  it('Warszawa has two partial bars and no single share', () => {
    const v = surveyView(DATA, 'warszawa')
    expect(v.status).toBe('partial')
    expect(v.bars).toHaveLength(2)
    expect(v.bars.every((b) => b.label)).toBe(true)
  })
  it('Łódź and GZM have none; Łódź says the survey is under way', () => {
    expect(surveyView(DATA, 'gzm').bars).toHaveLength(0)
    expect(surveyView(DATA, 'lodz').upcoming.text).toContain('Łódzkie Badania Ruchu')
    expect(surveyView(DATA, 'nowhere')).toBeNull()
  })
})

describe('the block', () => {
  it('shows the bar, the year, the source link and the comparability sentence', () => {
    const s = html('wroclaw')
    expect(s).toContain('Kompleksowe Badanie Ruchu 2024')
    expect(s).toContain('role="img"')
    expect(s).toContain('komunikacja zbiorowa 21,6 %')
    expect(s).toContain('href="https://www.wroclaw.pl/')
    expect(s).toContain('od 100 m')
  })
  it('says "brak badania" where there is none', () => {
    expect(html('gzm')).toContain('brak badania')
    expect(html('lodz')).toContain('badanie w toku')
    expect(html('gzm')).not.toContain('role="img"')
  })
  it('renders nothing without data', () => expect(html('wroclaw', null)).toBe(''))
  it('loads null when the file is missing', async () => {
    expect(await loadSurveyContext({ fetchImpl: async () => ({ ok: false }) })).toBeNull()
  })
})
