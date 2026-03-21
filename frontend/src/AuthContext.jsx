import { createContext, useContext, useState, useEffect } from 'react'

const TOKEN_KEY = 'agentmanager_jwt'
const umUrl = () => `https://${window.location.hostname}:13376`

function parseJwt(token) {
  try {
    return JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
  } catch { return null }
}

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser]       = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) { setLoading(false); return }
    fetch(`${umUrl()}/auth/validate`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(data => {
        if (data.valid) setUser({ id: data.user_id, username: data.username, display_name: data.display_name, role: data.role })
        else localStorage.removeItem(TOKEN_KEY)
      })
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false))
  }, [])

  async function login(username, password) {
    const r = await fetch(`${umUrl()}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || 'Login failed')
    const data = await r.json()
    localStorage.setItem(TOKEN_KEY, data.access_token)
    const payload = parseJwt(data.access_token)
    setUser({ id: data.user_id, username: data.username, display_name: payload?.display_name ?? null, role: data.role })
  }

  function logout() {
    localStorage.removeItem(TOKEN_KEY)
    setUser(null)
  }

  return <AuthContext.Provider value={{ user, loading, login, logout }}>{children}</AuthContext.Provider>
}

export function useAuth() { return useContext(AuthContext) }
