import './kit'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource-variable/schibsted-grotesk'
import '@fontsource-variable/newsreader'
import 'maplibre-gl/dist/maplibre-gl.css'
import '@bartor-net/ui-kit/base.css'
import '@bartor-net/ui-kit/styles.css'
import './kitx/kitx.css'
import './app.css'
import App from './App'

createRoot(document.getElementById('root')).render(<StrictMode><App /></StrictMode>)
