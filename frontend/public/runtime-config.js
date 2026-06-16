// Runtime configuration (overridden in Docker/Nginx container at startup).
// Keep this file in /public so Vite dev server can serve it too.
window.__APP_CONFIG__ = window.__APP_CONFIG__ || {
  API_BASE_URL: '',
  DEMO_VIDEO_URL: '',
}

