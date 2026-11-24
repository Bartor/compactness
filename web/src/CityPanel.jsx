import { DetailsPanel } from '@bartor-net/ui-kit'
import { ACCENT } from './config'
import CityView, { CITY_TABS } from './CityView'
import Tabs, { panelId } from './kitx/Tabs'

/**
 * A phone's sheet for a selected agglomeration: the kit's DetailsPanel with the same tabs as the desktop panel and the
 * same CityView (stacked). On a desktop the view lives in the bottom dock (App.jsx). `onClose` only collapses the sheet.
 */
export default function CityPanel({ agglomeration, subtitle, tab, setTab, tabs = CITY_TABS, onClose, onBack, ...rest }) {
  return (
    <DetailsPanel title={agglomeration.name} color={ACCENT} onClose={onClose}>
      {subtitle && <p className="city-sub">{subtitle}</p>}
      <p className="city-back"><button type="button" className="dock-back" onClick={onBack}>← Porównanie</button></p>
      <div className="city-tabs"><Tabs tabs={tabs} value={tab} onChange={setTab} label="Widoki aglomeracji" prefix="cityp" /></div>
      <div role="tabpanel" id={panelId('cityp')}>
        <CityView agglomeration={agglomeration} tab={tab} layout="stack" {...rest} />
      </div>
    </DetailsPanel>
  )
}

