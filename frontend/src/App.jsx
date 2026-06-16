import './App.css'
import { lazy, Suspense, useEffect } from 'react'
import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { RequireAuth } from './shared/components/RequireAuth.jsx'
// Landing stays eager so the marketing host's first paint has zero Suspense
// flash. Every other page is route-split so a visitor on a phone only
// downloads the landing bundle (which used to ship the entire app — chat,
// ictihat, takvim, admin, websockets, react-day-picker, etc. — in one chunk,
// adding 4–8s of TTI on cellular).
import { LandingPage } from './features/landing/pages/LandingPage.jsx'
import { PwaStatus } from './pwa/PwaStatus.jsx'

// Named exports → wrap with `.then(...)` so React.lazy gets the expected
// `{ default: Component }` shape without us having to touch the page files.
function lazyNamed(loader, name) {
  return lazy(() => loader().then((m) => ({ default: m[name] })))
}

const LoginPage = lazyNamed(() => import('./features/auth/pages/LoginPage.jsx'), 'LoginPage')
const RegisterPage = lazyNamed(() => import('./features/auth/pages/RegisterPage.jsx'), 'RegisterPage')
const ResetPasswordPage = lazyNamed(
  () => import('./features/auth/pages/ResetPasswordPage.jsx'),
  'ResetPasswordPage',
)
const ChatPage = lazyNamed(() => import('./features/chat/pages/ChatPage.jsx'), 'ChatPage')
const IctihatPage = lazyNamed(() => import('./features/ictihat/pages/IctihatPage.jsx'), 'IctihatPage')
const TakvimPage = lazyNamed(() => import('./features/calendar/pages/TakvimPage.jsx'), 'TakvimPage')
const SettingsPage = lazyNamed(
  () => import('./features/settings/pages/SettingsPage.jsx'),
  'SettingsPage',
)
const IntegrationsPage = lazyNamed(
  () => import('./features/landing/pages/IntegrationsPage.jsx'),
  'IntegrationsPage',
)
const AdminDashboardPage = lazyNamed(
  () => import('./features/admin/pages/AdminDashboardPage.jsx'),
  'AdminDashboardPage',
)
const AdminAccountDetailPage = lazyNamed(
  () => import('./features/admin/pages/AdminAccountDetailPage.jsx'),
  'AdminAccountDetailPage',
)
const AdminCouponsPage = lazyNamed(
  () => import('./features/admin/pages/AdminCouponsPage.jsx'),
  'AdminCouponsPage',
)

// Intentionally minimal: avoids a noisy spinner flash while a route chunk
// streams in. The body uses the background color so the transition looks like
// a slight tint shift instead of a layout pop.
function RouteFallback() {
  return (
    <div
      aria-hidden="true"
      style={{
        minHeight: '100dvh',
        backgroundColor: 'var(--background, #ffffff)',
      }}
    />
  )
}

const APP_HOSTNAME = 'app.yargucu.com.tr'
const ADMIN_HOSTNAME = 'admin.yargucu.com.tr'
const APP_LOCAL_HOSTNAME = 'app.localhost'
const ADMIN_LOCAL_HOSTNAME = 'admin.localhost'
const MARKETING_HOSTNAMES = new Set(['yargucu.com.tr', 'www.yargucu.com.tr'])
const APP_HOSTNAMES = new Set([APP_HOSTNAME, APP_LOCAL_HOSTNAME])
const ADMIN_HOSTNAMES = new Set([ADMIN_HOSTNAME, ADMIN_LOCAL_HOSTNAME])

function getCurrentHostname() {
  if (typeof window === 'undefined') return ''
  return String(window.location.hostname || '').trim().toLowerCase()
}

function buildAppUrl(pathname = '/') {
  if (typeof window === 'undefined') return pathname
  const protocol = window.location.protocol || 'https:'
  const currentHostname = getCurrentHostname()
  const targetHostname = currentHostname.endsWith('.localhost') ? APP_LOCAL_HOSTNAME : APP_HOSTNAME
  const port = window.location.port ? `:${window.location.port}` : ''
  return `${protocol}//${targetHostname}${port}${pathname}`
}

function CrossHostRedirect({ to }) {
  const location = useLocation()
  useEffect(() => {
    if (typeof window === 'undefined') return
    const targetPath = String(to || `${location.pathname}${location.search}${location.hash}` || '/')
    window.location.replace(buildAppUrl(targetPath))
  }, [location.hash, location.pathname, location.search, to])
  return null
}

function AppFrame({ children }) {
  return (
    <>
      <Suspense fallback={<RouteFallback />}>{children}</Suspense>
      <PwaStatus />
    </>
  )
}

function App() {
  const hostname = getCurrentHostname()
  const isMarketingHost = MARKETING_HOSTNAMES.has(hostname)
  const isAppHost = APP_HOSTNAMES.has(hostname)
  const isAdminHost = ADMIN_HOSTNAMES.has(hostname)

  if (isAdminHost) {
    return (
      <AppFrame>
        <Routes>
          <Route path="/" element={<AdminDashboardPage />} />
          <Route path="/accounts" element={<AdminDashboardPage />} />
          <Route path="/accounts/:userId" element={<AdminAccountDetailPage />} />
          <Route path="/coupons" element={<AdminCouponsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppFrame>
    )
  }

  if (isAppHost) {
    return (
      <AppFrame>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/reset-password" element={<ResetPasswordPage />} />
          <Route path="/" element={<Navigate to="/chat" replace />} />
          <Route path="/integrations" element={<Navigate to="/chat" replace />} />
          <Route
            path="/chat"
            element={
              <RequireAuth>
                <ChatPage />
              </RequireAuth>
            }
          />
          <Route
            path="/chat/:chatId"
            element={
              <RequireAuth>
                <ChatPage />
              </RequireAuth>
            }
          />
          <Route
            path="/ictihat"
            element={
              <RequireAuth>
                <IctihatPage />
              </RequireAuth>
            }
          />
          <Route
            path="/takvim"
            element={
              <RequireAuth>
                <TakvimPage />
              </RequireAuth>
            }
          />
          <Route
            path="/settings"
            element={
              <RequireAuth>
                <SettingsPage />
              </RequireAuth>
            }
          />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Routes>
      </AppFrame>
    )
  }

  if (isMarketingHost) {
    return (
      <AppFrame>
        <Routes>
          <Route path="/" element={<LandingPage />} />
          <Route path="/integrations" element={<IntegrationsPage />} />
          <Route path="/login" element={<CrossHostRedirect to="/login" />} />
          <Route path="/register" element={<CrossHostRedirect to="/register" />} />
          <Route path="/reset-password" element={<CrossHostRedirect to="/reset-password" />} />
          <Route path="/chat" element={<CrossHostRedirect />} />
          <Route path="/chat/:chatId" element={<CrossHostRedirect />} />
          <Route path="/ictihat" element={<CrossHostRedirect />} />
          <Route path="/takvim" element={<CrossHostRedirect />} />
          <Route path="/settings" element={<CrossHostRedirect />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppFrame>
    )
  }

  return (
    <AppFrame>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route path="/" element={<LandingPage />} />
        <Route path="/integrations" element={<IntegrationsPage />} />
        <Route
          path="/chat"
          element={
            <RequireAuth>
              <ChatPage />
            </RequireAuth>
          }
        />
        <Route
          path="/chat/:chatId"
          element={
            <RequireAuth>
              <ChatPage />
            </RequireAuth>
          }
        />
        <Route
          path="/ictihat"
          element={
            <RequireAuth>
              <IctihatPage />
            </RequireAuth>
          }
        />
        <Route
          path="/takvim"
          element={
            <RequireAuth>
              <TakvimPage />
            </RequireAuth>
          }
        />
        <Route
          path="/settings"
          element={
            <RequireAuth>
              <SettingsPage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppFrame>
  )
}

export default App
