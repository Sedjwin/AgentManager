import React, { useEffect, useState } from 'react'
import { Plus, Bot, Mic, Volume2, Zap, ZapOff, Trash2, MessageCircle } from 'lucide-react'
import AvatarCanvas from './AvatarCanvas'

export default function AgentList({ onSelect, onCreate, onChat }) {
  const [agents, setAgents] = useState([])
  const [loading, setLoading] = useState(true)
  const [deleting, setDeleting] = useState(null)

  useEffect(() => { fetchAgents() }, [])

  async function fetchAgents() {
    try {
      const r = await fetch('/agents')
      setAgents(await r.json())
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  async function handleDelete(e, id) {
    e.stopPropagation()
    if (!confirm('Delete this agent?')) return
    setDeleting(id)
    try {
      await fetch(`/agents/${id}`, { method: 'DELETE' })
      setAgents(a => a.filter(x => x.id !== id))
    } finally {
      setDeleting(null)
    }
  }

  return (
    <div className="min-h-screen p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-xl font-bold text-white tracking-wide">Agent Manager</h1>
          <p className="text-xs text-gray-500 mt-0.5">{agents.length} agent{agents.length !== 1 ? 's' : ''} registered</p>
        </div>
        <button
          onClick={onCreate}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
            bg-amber-500 hover:bg-amber-400 text-black transition-colors"
        >
          <Plus size={16} /> New Agent
        </button>
      </div>

      {/* Agent grid */}
      {loading ? (
        <div className="text-gray-600 text-sm">Loading…</div>
      ) : agents.length === 0 ? (
        <div className="text-center py-24 text-gray-600">
          <Bot size={48} className="mx-auto mb-4 opacity-30" />
          <p className="text-sm">No agents yet.</p>
          <button onClick={onCreate} className="mt-4 text-amber-500 hover:text-amber-400 text-sm">
            Create your first agent →
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map(a => (
            <AgentCard
              key={a.id}
              agent={a}
              onSelect={() => onSelect(a.id)}
              onDelete={(e) => handleDelete(e, a.id)}
              onChat={(e) => { e.stopPropagation(); onChat(a) }}
              deleting={deleting === a.id}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function AgentCard({ agent, onSelect, onDelete, onChat, deleting }) {
  const spec = safeJson(agent.avatar_spec)

  return (
    <div
      onClick={onSelect}
      className="relative bg-gray-900 border border-gray-800 rounded-xl p-4 cursor-pointer
        hover:border-gray-600 hover:bg-gray-800/60 transition-all group"
    >
      {/* Enabled dot */}
      <span className={`absolute top-3 right-3 w-2 h-2 rounded-full ${agent.enabled ? 'bg-green-500' : 'bg-gray-600'}`} />

      {/* Delete */}
      <button
        onClick={onDelete}
        disabled={deleting}
        className="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100
          text-gray-600 hover:text-red-400 transition-all"
      >
        <Trash2 size={14} />
      </button>

      <div className="flex gap-4 items-start">
        {/* Avatar */}
        <div className="shrink-0">
          <AvatarCanvas spec={spec} size={64} animated={false} />
        </div>

        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-white truncate">{agent.name}</h3>
          <p className="text-xs text-gray-500 mt-1 line-clamp-2 leading-relaxed">
            {agent.bio || <span className="italic">No description</span>}
          </p>

          {/* Badges */}
          <div className="flex flex-wrap gap-1.5 mt-3">
            <Badge icon={<Mic size={10} />} label={agent.voice || 'glados'} color="purple" />
            {agent.smart_routing
              ? <Badge icon={<Zap size={10} />} label="smart" color="amber" />
              : agent.default_model
                ? <Badge label={agent.default_model.split('/').pop().substring(0, 18)} color="blue" />
                : null
            }
            {agent.accepts_attachments && <Badge label="files" color="gray" />}
            {agent.accepts_images     && <Badge label="images" color="gray" />}
          </div>

          {/* Chat Now button */}
          {agent.enabled && agent.gateway_token && (
            <button
              onClick={onChat}
              className="mt-3 flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium
                bg-amber-500/10 border border-amber-500/30 text-amber-400
                hover:bg-amber-500/20 hover:border-amber-500/50 transition-all"
            >
              <MessageCircle size={12} /> Chat Now
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

function Badge({ icon, label, color }) {
  const colors = {
    amber:  'bg-amber-500/10 text-amber-400 border-amber-500/20',
    purple: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    blue:   'bg-blue-500/10  text-blue-400  border-blue-500/20',
    green:  'bg-green-500/10 text-green-400 border-green-500/20',
    gray:   'bg-gray-700/50  text-gray-400  border-gray-600',
  }
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] ${colors[color] || colors.gray}`}>
      {icon}{label}
    </span>
  )
}

function safeJson(v) {
  if (!v) return {}
  if (typeof v === 'object') return v
  try { return JSON.parse(v) } catch { return {} }
}
