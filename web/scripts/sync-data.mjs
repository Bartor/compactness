// Copies the pipeline's outputs into web/public/ so Vite serves and ships them.
//   ../results/web/*                  -> public/data/   (metrics.json there is the panel subset;
//                                         the full table results/metrics/metrics.json is not shipped)
//   ../tiles/*.pmtiles                -> public/tiles/
// Without ../results/web/catalog.json the small fixtures in web/fixtures/ are
// used instead, with a loud warning: a site built from them is only a demo.
import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const web = resolve(here, '..')
const repo = resolve(web, '..')
const out = join(web, 'public')
const dataOut = join(out, 'data')
const tilesOut = join(out, 'tiles')

const files = (dir) => (existsSync(dir)
  ? readdirSync(dir).filter((f) => statSync(join(dir, f)).isFile())
  : [])

const copy = (from, to) => {
  mkdirSync(dirname(to), { recursive: true })
  copyFileSync(from, to)
}

// Start clean so a layer removed from the pipeline does not linger.
rmSync(dataOut, { recursive: true, force: true })
rmSync(tilesOut, { recursive: true, force: true })
mkdirSync(dataOut, { recursive: true })
mkdirSync(tilesOut, { recursive: true })

const webDir = join(repo, 'results', 'web')
const real = existsSync(join(webDir, 'catalog.json'))

if (real) {
  for (const f of files(webDir)) copy(join(webDir, f), join(dataOut, f))
  if (!existsSync(join(dataOut, 'metrics.json'))) {
    console.warn('sync-data: results/web/metrics.json is missing (run pipeline.merge_metrics), the site will show no metrics')
  }
  console.log(`sync-data: data from results/web (${files(dataOut).length} files)`)
} else {
  const fixtures = join(web, 'fixtures')
  for (const f of files(fixtures)) copy(join(fixtures, f), join(dataOut, f))
  const bar = '!'.repeat(72)
  console.warn(`\n${bar}\nsync-data: results/web/catalog.json NOT FOUND\n`
    + 'sync-data: using web/fixtures/ - DEMO DATA, NOT REAL RESULTS. Do not publish this.\n'
    + `${bar}\n`)
}

const tiles = files(join(repo, 'tiles')).filter((f) => f.endsWith('.pmtiles'))
for (const f of tiles) copy(join(repo, 'tiles', f), join(tilesOut, f))
console.log(`sync-data: ${tiles.length} pmtiles file(s)`)
