import { fileURLToPath, URL } from 'node:url'
import process from 'node:process'
import { defineConfig } from 'vite'
import { loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const apiTarget = String(
    env.VITE_PROXY_TARGET ||
    env.VITE_API_PROXY_TARGET ||
    env.VITE_API_BASE_URL ||
    'http://127.0.0.1:8000'
  )
    .trim()
    .replace(/\/+$/, '') || 'http://127.0.0.1:8000'

  return {
    plugins: [
      react(),
      tailwindcss(),
      VitePWA({
        injectRegister: false,
        registerType: 'prompt',
        includeManifestIcons: false,
        manifest: {
          id: '/chat',
          name: 'Yargucu - AI Hukuk Asistanı',
          short_name: 'Yargucu',
          description: 'Hukuk soruları, dilekçe taslakları ve içtihat araştırmaları için güvenli çalışma alanı.',
          lang: 'tr-TR',
          dir: 'ltr',
          start_url: '/chat',
          scope: '/',
          display: 'standalone',
          display_override: ['window-controls-overlay', 'standalone', 'minimal-ui'],
          orientation: 'portrait-primary',
          background_color: '#ffffff',
          theme_color: '#0c4e30',
          categories: ['business', 'productivity', 'utilities'],
          prefer_related_applications: false,
          icons: [
            {
              src: '/pwa-192x192.png',
              sizes: '192x192',
              type: 'image/png',
              purpose: 'any',
            },
            {
              src: '/pwa-512x512.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'any',
            },
            {
              src: '/maskable-icon.png',
              sizes: '512x512',
              type: 'image/png',
              purpose: 'maskable',
            },
          ],
          shortcuts: [
            {
              name: 'Sohbet',
              short_name: 'Sohbet',
              description: 'Hukuk asistanı ile çalış',
              url: '/chat',
              icons: [{ src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png' }],
            },
            {
              name: 'İçtihat Arama',
              short_name: 'İçtihat',
              description: 'Karar ve içtihat araştır',
              url: '/ictihat',
              icons: [{ src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png' }],
            },
            {
              name: 'Ayarlar',
              short_name: 'Ayarlar',
              description: 'Hesap ayarlarını aç',
              url: '/settings',
              icons: [{ src: '/pwa-192x192.png', sizes: '192x192', type: 'image/png' }],
            },
          ],
        },
        workbox: {
          cacheId: 'yargucu',
          cleanupOutdatedCaches: true,
          clientsClaim: true,
          globPatterns: ['**/*.{js,css,html,svg,png,lottie,woff2}'],
          globIgnores: ['**/runtime-config.js'],
          maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
          navigateFallback: '/index.html',
          navigateFallbackDenylist: [/^\/v1\//, /^\/runtime-config\.js$/],
          runtimeCaching: [
            {
              urlPattern: ({ url }) => url.pathname.startsWith('/v1/') || url.pathname === '/runtime-config.js',
              handler: 'NetworkOnly',
              method: 'GET',
            },
            {
              urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
              handler: 'StaleWhileRevalidate',
              options: {
                cacheName: 'google-fonts-stylesheets',
                expiration: {
                  maxEntries: 10,
                  maxAgeSeconds: 60 * 60 * 24 * 365,
                },
                cacheableResponse: {
                  statuses: [0, 200],
                },
              },
            },
            {
              urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
              handler: 'CacheFirst',
              options: {
                cacheName: 'google-fonts-webfonts',
                expiration: {
                  maxEntries: 30,
                  maxAgeSeconds: 60 * 60 * 24 * 365,
                },
                cacheableResponse: {
                  statuses: [0, 200],
                },
              },
            },
            {
              urlPattern: /^https:\/\/cdnjs\.cloudflare\.com\/ajax\/libs\/font-awesome\/.*/i,
              handler: 'StaleWhileRevalidate',
              options: {
                cacheName: 'font-awesome-assets',
                expiration: {
                  maxEntries: 20,
                  maxAgeSeconds: 60 * 60 * 24 * 30,
                },
                cacheableResponse: {
                  statuses: [0, 200],
                },
              },
            },
            {
              urlPattern: ({ request, url }) =>
                url.origin === self.location.origin && ['script', 'style', 'worker', 'font'].includes(request.destination),
              handler: 'StaleWhileRevalidate',
              options: {
                cacheName: 'same-origin-static-assets',
                expiration: {
                  maxEntries: 80,
                  maxAgeSeconds: 60 * 60 * 24 * 30,
                },
                cacheableResponse: {
                  statuses: [200],
                },
              },
            },
            {
              urlPattern: ({ request, url }) => url.origin === self.location.origin && request.destination === 'image',
              handler: 'StaleWhileRevalidate',
              options: {
                cacheName: 'same-origin-images',
                expiration: {
                  maxEntries: 80,
                  maxAgeSeconds: 60 * 60 * 24 * 30,
                },
                cacheableResponse: {
                  statuses: [200],
                },
              },
            },
          ],
        },
        devOptions: {
          enabled: false,
        },
      }),
    ],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    server: {
      // When exposing Vite dev server via ngrok, the public hostname must be allowlisted
      // to avoid "Blocked request. This host is not allowed."
      allowedHosts: ['.ngrok-free.app', '.ngrok.app'],
      proxy: {
        // Avoid CORS during local dev: frontend -> Vite -> backend.
        // Keep the proxy target aligned with `.env` so backend URL is configured in one place.
        '/v1': {
          target: apiTarget,
          changeOrigin: true,
          ws: true,
        },
      },
    },
  }
})
