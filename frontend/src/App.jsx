import { useState, useEffect, useCallback } from 'react'
import { Plus, RefreshCw, Bot, Mic, User, Trash2, Edit2, AlertCircle } from 'lucide-react'
import { listAgents, deleteAgent } from './api.js'
import { useAuth } from './AuthContext'
import AgentModal from './AgentModal.jsx'
import AgentDetail from './AgentDetail.jsx'
import LoginScreen from './LoginScreen.jsx'
import UserPill from './UserPill.jsx'

export default function App() {
  const { user, loading, logout } = useAuth()

  if (loading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <div className="w-6 h-6 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
  if (!user) return <LoginScreen />

  return <AgentApp user={user} logout={logout} />
}

function AgentApp({ user, logout }) {
  const [agents, setAgents]           = useState([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)
  const [selected, setSelected]       = useState(null)
  const [modal, setModal]             = useState(null)  // null | 'create' | agent object
  const [deleting, setDeleting]       = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listAgents()
      setAgents(data)
      if (selected) setSelected(data.find(a => a.agent_id === selected.agent_id) || null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [selected])

  useEffect(() => { load() }, [])

  async function handleDelete(agent) {
    if (!confirm(`Delete "${agent.name}"? This cannot be undone.`)) return
    setDeleting(agent.agent_id)
    try {
      await deleteAgent(agent.agent_id)
      if (selected?.agent_id === agent.agent_id) setSelected(null)
      await load()
    } catch (e) {
      alert('Delete failed: ' + e.message)
    } finally {
      setDeleting(null)
    }
  }

  function handleSaved() {
    setModal(null)
    load()
  }

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      {/* Header */}
      <header className="shrink-0 h-12 flex items-center justify-between px-5 border-b border-gray-800 bg-gray-900">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-amber-400" />
          <span className="text-sm font-bold tracking-tight">AgentManager</span>
          <span className="text-xs text-gray-600 ml-2">v2</span>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={load} disabled={loading}
            className="p-1.5 rounded text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors">
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button onClick={() => setModal('create')}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-black text-xs font-semibold transition-colors">
            <Plus className="w-3.5 h-3.5" /> New Agent
          </button>
          <UserPill user={user} onLogout={logout} />
        </div>
      </header>

      {/* Body */}
      <div className="flex flex-1 min-h-0">
        {/* Sidebar — agent list */}
        <aside className="w-72 shrink-0 border-r border-gray-800 bg-gray-900 flex flex-col overflow-y-auto">
          {error && (
            <div className="m-3 p-2 bg-red-950 border border-red-800 rounded text-xs text-red-300 flex gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              {error}
            </div>
          )}
          {!loading && agents.length === 0 && (
            <div className="p-4 text-xs text-gray-600 text-center mt-4">
              No agents yet. Create one to get started.
            </div>
          )}
          {agents.map(agent => (
            <div key={agent.agent_id}
              onClick={() => setSelected(agent)}
              className={`flex items-start gap-3 px-4 py-3 cursor-pointer border-b border-gray-800 transition-colors group ${
                selected?.agent_id === agent.agent_id
                  ? 'bg-amber-500/10 border-l-2 border-l-amber-500'
                  : 'hover:bg-gray-800/50'
              }`}>
              <div className={`w-8 h-8 rounded-lg shrink-0 flex items-center justify-center mt-0.5 ${
                agent.has_profile ? 'bg-amber-500/20' : 'bg-gray-800'
              }`}>
                {agent.has_profile ? <User className="w-4 h-4 text-amber-400" /> : <Bot className="w-4 h-4 text-gray-500" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-gray-100 truncate">{agent.name}</div>
                <div className="flex items-center gap-2 mt-0.5">
                  <span className={`text-xs px-1.5 py-0.5 rounded ${
                    agent.has_profile ? 'bg-amber-500/15 text-amber-400' : 'bg-gray-800 text-gray-500'
                  }`}>
                    {agent.has_profile ? 'Interaction' : 'Functional'}
                  </span>
                  {agent.voice_enabled && <Mic className="w-3 h-3 text-blue-400" title="Voice enabled" />}
                </div>
              </div>
              <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                <button onClick={e => { e.stopPropagation(); setModal(agent) }}
                  className="p-1 rounded text-gray-500 hover:text-amber-400 hover:bg-gray-700 transition-colors">
                  <Edit2 className="w-3.5 h-3.5" />
                </button>
                <button onClick={e => { e.stopPropagation(); handleDelete(agent) }}
                  disabled={deleting === agent.agent_id}
                  className="p-1 rounded text-gray-500 hover:text-red-400 hover:bg-gray-700 transition-colors">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </aside>

        {/* Main — agent detail */}
        <main className="flex-1 overflow-y-auto p-6">
          {selected ? (
            <AgentDetail
              agent={selected}
              onEdit={() => setModal(selected)}
              onDelete={() => handleDelete(selected)}
              onRefresh={load}
            />
          ) : (
            <div className="h-full flex items-center justify-center text-gray-700 text-sm">
              Select an agent to view details
            </div>
          )}
        </main>
      </div>

      {/* Modal */}
      {modal !== null && (
        <AgentModal
          agent={modal === 'create' ? null : modal}
          onClose={() => setModal(null)}
          onSaved={handleSaved}
        />
      )}
    </div>
  )
}
