/**
 * Makes the kit's DetailsPanel inside it wider (560 px on screens wider than a phone; the panel's own sheet
 * on phones). Wraps without a box of its own, so the panel stays a child of the page layout.
 */
export default function Dock({ children }) {
  return <div className="kitx-dock">{children}</div>
}
