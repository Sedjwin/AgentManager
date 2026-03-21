import { useState } from 'react'
import { Bot, Loader } from 'lucide-react'
import { useAuth } from './AuthContext'

export default function LoginScreen() {
  const { login } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [busy,     setBusy]     = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true); setError('')
    try { await login(username, password) }
    catch (err) { setError(err.message) }
    finally { setBusy(false) }
  }

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center p-4">
      <form onSubmit={submit} className="bg-gray-900 border border-gray-800 rounded-2xl p-8 w-full max-w-sm flex flex-col gap-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 bg-amber-500/20 rounded-xl flex items-center justify-center">
            <Bot className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h1 className="text-white font-bold text-lg">AgentManager</h1>
            <p className="text-gray-500 text-xs">Sign in to continue</p>
          </div>
        </div>
        <div className="flex flex-col gap-3">
          <input
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500 transition-colors"
            placeholder="Username" autoFocus required
            value={username} onChange={e => setUsername(e.target.value)}
          />
          <input
            type="password"
            className="bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500 transition-colors"
            placeholder="Password" required
            value={password} onChange={e => setPassword(e.target.value)}
          />
        </div>
        {error && <p className="text-red-400 text-sm">{error}</p>}
        <button type="submit" disabled={busy}
          className="flex items-center justify-center gap-2 bg-amber-500 hover:bg-amber-400 disabled:opacity-50 text-black font-semibold rounded-lg py-2.5 text-sm transition-colors">
          {busy ? <><Loader className="w-4 h-4 animate-spin" /> Signing in…</> : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
