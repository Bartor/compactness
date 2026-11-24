import { useEffect, useState } from 'react'
import { decodeNode } from './detailData'

/**
 * {status, node} of a node id through a loader (detailData.createDetailLoader):
 * status 'idle' (no id), 'loading', 'ready' (node decoded), 'none' (the node has no detail record: fewer than 20
 * departures an hour, outside the GTFS mask, or no movement between lines), 'error' (the file could not be read).
 */
export function useNodeDetail(loader, id) {
  const [state, setState] = useState({ status: id ? 'loading' : 'idle', node: null, id })
  useEffect(() => {
    if (!id) { setState({ status: 'idle', node: null, id }); return undefined }
    let live = true
    setState({ status: 'loading', node: null, id })
    loader.get(id).then(
      (rec) => { if (live) setState({ status: rec ? 'ready' : 'none', node: decodeNode(rec), id }) },
      () => { if (live) setState({ status: 'error', node: null, id }) },
    )
    return () => { live = false }
  }, [loader, id])
  return state
}
