import { DetailsPanel } from '@bartor-net/ui-kit'
import { ACCENT } from './config'
import CityView from './CityView'

/**
 * A phone's sheet for a selected agglomeration: the kit's DetailsPanel around CityView (stacked). On a desktop the
 * same view lives in the bottom dock (App.jsx).
 */
export default function CityPanel({ agglomeration, onClose, ...rest }) {
  return (
    <DetailsPanel
      pill={agglomeration.phase != null ? `Etap ${agglomeration.phase}` : undefined}
      title={agglomeration.name} color={ACCENT} onClose={onClose}
    >
      <CityView agglomeration={agglomeration} layout="stack" {...rest} />
    </DetailsPanel>
  )
}
