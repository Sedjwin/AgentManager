import { Edit2, Trash2, Mic, MicOff, User, Bot, Wrench } from 'lucide-react'
import { useState, useEffect, useCallback } from 'react'

function Field({ label, children }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-sm text-gray-200">{children}</div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{title}</h3>
      {children}
    </div>
  )
}

function ToolsSection({ agent, onToolConfigSaved }) {
  const [tools, setTools] = useState([])
  const [loading, setLoading] = useState(true)
  const [toolUseEnabled, setToolUseEnabled] = useState(agent.tool_use_enabled || false)
  const [enabledTools, setEnabledTools] = useState(new Set(agent.enabled_tools || []))
  const [saving, setSaving] = useState(false)

  const fetchTools = useCallback(async () => {
    setLoading(true)
    try {
      const r = await fetch(`/agents/${agent.agent_id}/tools`)
      if (r.ok) setTools(await r.json())
    } catch {}
    setLoading(false)
  }, [agent.agent_id])

  useEffect(() => { fetchTools() }, [fetchTools])

  async function save(newEnabled, newToolUse) {
    setSaving(true)
    try {
      const r = await fetch(`/agents/${agent.agent_id}/tools`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_use_enabled: newToolUse, enabled_tools: [...newEnabled] }),
      })
      if (r.ok && onToolConfigSaved) onToolConfigSaved()
    } catch {}
    setSaving(false)
  }

  function toggleToolUse(val) {
    setToolUseEnabled(val)
    save(enabledTools, val)
  }

  function toggleTool(name, checked) {
    const next = new Set(enabledTools)
    checked ? next.add(name) : next.delete(name)
    setEnabledTools(next)
    save(next, toolUseEnabled)
  }

  const grantedCount = tools.length
  const hasUm = agent.um_user_id != null

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider flex items-center gap-2">
          <Wrench className="w-3.5 h-3.5" /> Tool Use
        </h3>
        {saving && <span className="text-xs text-gray-600">Saving…</span>}
      </div>

      {!hasUm && (
        <p className="text-xs text-amber-500">Agent has no UserManager principal — tool grants require registration.</p>
      )}

      {/* Enable Tool Use toggle */}
      <label className="flex items-center gap-3 cursor-pointer">
        <div
          onClick={() => hasUm && toggleToolUse(!toolUseEnabled)}
          className={`relative w-9 h-5 rounded-full transition-colors ${toolUseEnabled ? 'bg-violet-600' : 'bg-gray-700'} ${!hasUm ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}`}
        >
          <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform ${toolUseEnabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
        </div>
        <div>
          <div className="text-sm text-gray-200">Enable Tool Use</div>
          <div className="text-xs text-gray-600">Adds tool-calling preamble + selected tool instructions to system prompt</div>
        </div>
      </label>

      {/* Tool list */}
      {toolUseEnabled && (
        <div className="space-y-2 pt-1">
          {loading && <div className="text-xs text-gray-600">Loading granted tools…</div>}
          {!loading && grantedCount === 0 && (
            <div className="text-xs text-gray-600 italic">No tools granted to this agent yet. Grant tools in ToolGateway.</div>
          )}
          {tools.map(t => (
            <div key={t.tool_id} className={`flex items-start gap-3 p-3 rounded-lg border ${
              t.grant_enabled && t.enabled ? 'border-gray-700 bg-gray-800/50' : 'border-gray-800 bg-gray-900 opacity-60'
            }`}>
              <input
                type="checkbox"
                checked={enabledTools.has(t.name)}
                onChange={e => toggleTool(t.name, e.target.checked)}
                disabled={!t.grant_enabled || !t.enabled}
                className="mt-0.5 accent-violet-500"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-mono text-violet-300">{t.name}</span>
                  {!t.grant_enabled && <span className="text-xs text-gray-600">(grant disabled)</span>}
                  {!t.enabled && <span className="text-xs text-gray-600">(tool disabled)</span>}
                </div>
                {t.description && <div className="text-xs text-gray-500 mt-0.5">{t.description}</div>}
                {!t.skill_md && (
                  <div className="text-xs text-amber-600 mt-0.5">No SkillMD — agent won't know how to use this tool</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AgentDetail({ agent, onEdit, onDelete, onRefresh }) {
  const profile = agent.profile
  const vc = agent.voice_config

  return (
    <div className="max-w-2xl space-y-4">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
            profile ? 'bg-amber-500/20' : 'bg-gray-800'
          }`}>
            {profile ? <User className="w-5 h-5 text-amber-400" /> : <Bot className="w-5 h-5 text-gray-500" />}
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">{agent.name}</h2>
            <div className="flex items-center gap-2 mt-0.5">
              <span className={`text-xs px-1.5 py-0.5 rounded ${
                profile ? 'bg-amber-500/15 text-amber-400' : 'bg-gray-800 text-gray-500'
              }`}>
                {profile ? 'Interaction Agent' : 'Functional Agent'}
              </span>
              {agent.voice_enabled
                ? <span className="flex items-center gap-1 text-xs text-blue-400"><Mic className="w-3 h-3" /> Voice</span>
                : <span className="flex items-center gap-1 text-xs text-gray-600"><MicOff className="w-3 h-3" /> No voice</span>
              }
            </div>
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={onEdit}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs text-gray-300 transition-colors">
            <Edit2 className="w-3.5 h-3.5" /> Edit
          </button>
          <button onClick={onDelete}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-950 hover:bg-red-900 text-xs text-red-400 transition-colors">
            <Trash2 className="w-3.5 h-3.5" /> Delete
          </button>
        </div>
      </div>

      {/* System prompt */}
      <Section title="System Prompt">
        <pre className="text-xs text-gray-300 whitespace-pre-wrap leading-relaxed font-sans">
          {agent.system_prompt || <span className="text-gray-600 italic">No system prompt</span>}
        </pre>
      </Section>

      {/* Voice config */}
      {agent.voice_enabled && vc && (
        <Section title="Voice Configuration">
          <Field label="Voice">{vc.voice_id || '—'}</Field>
        </Section>
      )}

      {/* Profile summary */}
      {profile && (
        <>
          <Section title="Identity">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Display Name">{profile.display_name}</Field>
              <Field label="Tagline">{profile.tagline}</Field>
            </div>
          </Section>

          <Section title="Appearance">
            <div className="grid grid-cols-3 gap-3">
              {Object.entries(profile.appearance || {}).map(([k, v]) => (
                typeof v === 'number' ? (
                  <div key={k}>
                    <div className="text-xs text-gray-600 mb-1">{k.replace(/_/g, ' ')}</div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-1.5 bg-gray-800 rounded-full">
                        <div className="h-1.5 bg-amber-500/60 rounded-full" style={{ width: `${Math.min(v * 100, 100)}%` }} />
                      </div>
                      <span className="text-xs text-gray-500 font-mono w-8 text-right">{v.toFixed(2)}</span>
                    </div>
                  </div>
                ) : (
                  <div key={k}>
                    <div className="text-xs text-gray-600 mb-1">{k.replace(/_/g, ' ')}</div>
                    {typeof v === 'string' && v.startsWith('#')
                      ? <div className="flex items-center gap-2">
                          <div className="w-4 h-4 rounded border border-gray-700" style={{ background: v }} />
                          <span className="text-xs text-gray-400 font-mono">{v}</span>
                        </div>
                      : <span className="text-xs text-gray-400">{String(v)}</span>
                    }
                  </div>
                )
              ))}
            </div>
          </Section>

          <Section title={`Emotions (${Object.keys(profile.emotions || {}).length})`}>
            <div className="flex flex-wrap gap-2">
              {Object.keys(profile.emotions || {}).map(name => (
                <span key={name} className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-amber-300 font-mono">
                  {name}
                </span>
              ))}
            </div>
          </Section>

          <Section title={`Actions (${Object.keys(profile.actions || {}).length})`}>
            <div className="flex flex-wrap gap-2">
              {Object.keys(profile.actions || {}).map(name => (
                <span key={name} className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-blue-300 font-mono">
                  {name}
                </span>
              ))}
            </div>
          </Section>
        </>
      )}

      {/* Tools */}
      <ToolsSection agent={agent} onToolConfigSaved={onRefresh} />

      <div className="text-xs text-gray-700 font-mono">
        ID: {agent.agent_id}
      </div>
    </div>
  )
}
