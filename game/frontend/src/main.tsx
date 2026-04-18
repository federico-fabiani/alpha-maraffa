import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

// Lock orientation to landscape (works on mobile browsers that support the API)
if (screen.orientation && typeof screen.orientation.lock === 'function') {
  screen.orientation.lock('landscape').catch(() => {
    // Silently ignore – desktop browsers and some mobile browsers deny this
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
