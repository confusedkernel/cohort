import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { applyTheme, loadTheme } from './Settings'
import './styles.css'

// Before the first paint, not in an effect: applying a stored theme after
// React mounts would show one frame of the system scheme first, which is a
// visible flash for anyone whose choice differs from their OS.
applyTheme(loadTheme())

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
