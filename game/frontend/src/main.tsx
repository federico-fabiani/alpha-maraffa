import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'

// Lock orientation to landscape (works on mobile browsers that support the API)
const orientation = screen.orientation as ScreenOrientation & { lock?: (o: string) => Promise<void> }
if (orientation?.lock) {
  orientation.lock('landscape').catch(() => {
    // Silently ignore – desktop browsers and some mobile browsers deny this
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
