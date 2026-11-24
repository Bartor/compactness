# features/nodes: node detail

What happens when a stop area (a transfer node) is clicked: a card in the bottom dock with one plain sentence,
a connection matrix, the generalised-time band, obstacles and the heaviest movements, and on the map the node's
stops, walking paths and crossings. Nothing here is wired into the page yet; the steps are below.

## Files

| file | what |
|---|---|
| `detailData.js` | loader with a per-city cache (`createDetailLoader`), decoding (`decodeNode`), pure models for the card (`summarySentence`, `matrixModel`, `bandText`, `obstacleRows`, `topMovementTable`), W6 colours (`W6`) |
| `useNodeDetail.js` | `useNodeDetail(loader, id)` -> `{ status, node }` |
| `NodeDetail.jsx` | the card (uses the kit's `DataTable`, `Hint`, `Notes`) |
| `detailLayers.js` | MapLibre: `showNodeDetail(map, node, before)`, `setHotPath(map, pathIndex)`, `clearNodeDetail(map)`, `detailBounds(node)`; specs and features are pure (`detailLayerSpecs`, `detailFeatures`, `hotFilter`) |
| `nodeDetail.css` | styles of the card, on the kit's custom properties |
| `detail.test.js` | tests (vitest) |

## Data

`results/web/transfer_detail/<agg>.json` (one file per agglomeration, 0.1–1.5 MB, lazy) and `index.json`
(node id -> [agg, name, departures an hour]); format in the docstring of `pipeline/transfer_detail.py`. Nodes with
at least 20 departures an hour (06–20), inside the FUA and the GTFS mask, with at least one movement between
lines. In `results/web/transfer_nodes.geojson` (after `python -m pipeline.transfer_web --geojson-only`) these nodes
carry `detail: true`.

**Needed in `web/scripts/sync-data.mjs`:** it copies only the files directly in `results/web/`, so the folder must be
added, for example after the loop over `files(webDir)`:

```js
const detailDir = join(webDir, 'transfer_detail')
for (const f of files(detailDir)) copy(join(detailDir, f), join(dataOut, 'transfer_detail', f))
```

The loader then reads `./data/transfer_detail/<agg>.json` (`DATA_BASE_URL` from `src/config.js`).

## NodeDetail props

| prop | type | meaning |
|---|---|---|
| `node` | decoded node or `null` | from `useNodeDetail` |
| `status` | `'idle' \| 'loading' \| 'ready' \| 'none' \| 'error'` | `none` = no record for this node (quiet node, outside the mask, no movement) |
| `name` | string | the node's name from the map feature, for the loading and "no detail" texts |
| `hot` | number or `null` | index of the lit movement (`node.moves[i]`) |
| `onHot` | `(moveIndex, pathIndex) => void` | pointer or focus entered (numbers) or left (`null, null`) a matrix cell or a table row; `pathIndex` is an index into `node.paths`, `-1` = same stop (no path), `null` = no stored path |
| `timetableDate` | string | for the footnote |

The card has no title of its own: the dock's title bar carries the node's name.

## Wiring (for the agent who owns `App.jsx` and `MapView.jsx`)

Proposed behaviour: on desktop a click on a node **with** `detail: true` opens the card in the dock (unfolding it
to half if folded) and draws the node on the map; the popup is not opened for it (the card says more, and both at
once cover the paths). A node without `detail` keeps today's popup. On a phone keep the popup and offer a link
"Szczegóły węzła" in it that opens the card in a `Modal` (the dock is desktop only).

1. `App.jsx`: one loader for the session, the selected node, the lit movement.

```jsx
import { createDetailLoader } from './features/nodes/detailData'
import { useNodeDetail } from './features/nodes/useNodeDetail'
import NodeDetail from './features/nodes/NodeDetail'

const detailLoader = useMemo(() => createDetailLoader(), [])
const [nodePick, setNodePick] = useState(null)      // {id, name} or null
const [nodeHot, setNodeHot] = useState({ move: null, path: null })
const detail = useNodeDetail(detailLoader, nodePick?.id)
// prefetch the city's file when a city is selected (optional)
useEffect(() => { if (selectedId) detailLoader.prefetch(selectedId) }, [selectedId, detailLoader])
const openNode = (props) => { setNodePick({ id: props.id, name: props.name }); setDock((d) => (d === 'folded' ? 'half' : d)) }
const closeNode = () => { setNodePick(null); setNodeHot({ move: null, path: null }) }
```

Pass `onNode={openNode}`, `detailNode={detail.status === 'ready' ? detail.node : null}` and
`hotPath={nodeHot.path}` to `MapView`. In `DockStage`, when `nodePick` is set, the title is
`<button className="dock-back" onClick={closeNode}>← {selected ? selected.name : 'Porównanie miast'}</button><h2>{nodePick.name}</h2>`
and the content is

```jsx
<NodeDetail node={detail.node} status={detail.status} name={nodePick.name} hot={nodeHot.move}
  onHot={(move, path) => setNodeHot({ move, path })} timetableDate={transferLayer?.timetable_date} />
```

Add `nodePick` to the `ErrorBoundary`'s `resetKey`.

2. `MapView.jsx`: in the `click` handler, before `openPopup(node)`:

```js
const props = node.feature.properties || {}
if (props.detail && !isPhone() && latest.current.onNode) {
  closePopup()
  latest.current.onNode(props)
  return
}
```

(and add `onNode` to `latest.current`). Draw, light and clear the node with two effects:

```js
import { clearNodeDetail, detailBounds, setHotPath, showNodeDetail } from './features/nodes/detailLayers'
import { ANCHOR_LABELS } from './mapStyle'

useEffect(() => {
  if (!ready) return
  if (!detailNode) { clearNodeDetail(ready); return }
  showNodeDetail(ready, detailNode, ANCHOR_LABELS)   // above the overlays, under the basemap labels
  const b = detailBounds(detailNode)
  if (b) ready.fitBounds([[b[0], b[1]], [b[2], b[3]]], { padding: fitPad, maxZoom: 17, duration: 700 })
}, [ready, detailNode])
useEffect(() => { if (ready) setHotPath(ready, hotPath) }, [ready, hotPath, detailNode])
```

`syncOverlays` must leave the `node-detail:*` layers and the `node-detail` source alone (it only touches catalog
layers by id, so it does today). If the transfer layer is switched off, call `closeNode()`.

3. URL state (optional): `#...&node=poznan-T00012` restored through `setNodePick`.

## Not verified

The card has been rendered only in tests (static markup); it has not been looked at in a browser, at phone
width, or with a keyboard beyond the cells being focusable. The matrix is a plain table with sticky heads inside
its own scrolling box; check it inside the dock at half height.
