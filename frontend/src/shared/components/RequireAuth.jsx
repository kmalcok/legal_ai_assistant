import { Navigate, useLocation } from 'react-router-dom'
import { useAuth } from '../../features/auth/useAuth.js'

export function RequireAuth({ children }) {
  const { bootstrapped, isAuthed } = useAuth()
  const location = useLocation()

  if (!bootstrapped) {
    return (
      <div className="centered">
        <div className="muted">Loading…</div>
      </div>
    )
  }

  if (!isAuthed) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />
  }

  return children
}

