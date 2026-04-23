import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { registerSW } from 'virtual:pwa-register'
import './index.css'
import App from './App'

// When a new service worker takes control (after a deploy), reload immediately
// so users always see the latest frontend without manual intervention.
registerSW({
  immediate: true,
  onRegisteredSW(_swUrl, registration) {
    if (!registration) {
      return
    }

    window.setInterval(() => {
      void registration.update()
    }, 60_000)
  },
  onNeedRefresh() {
    window.location.reload()
  },
  onOfflineReady() {},
})

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
