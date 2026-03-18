import React, { useEffect, useState } from 'react'
import { Wrench, Eye, EyeOff, RefreshCw } from 'lucide-react'

export default function SetupTab({ data, onChange, onRegisterGateway }) {
  const [models, setModels] = useState([])
  const [showToken, setShowToken] = useState(false)

  useEffect(() => {
    fetch('/agents')   // just for warming; models come from AIGateway
      .catch(() => {})
    fetchModels()
  }, [])

  async function fetchModels() {
    try {
      const r = await fetch('/setup/models').catch(() => null)
      if (r?.ok) {
        const data = await r.json()
        setModels(data.map(m => ({ id: m.id, name: m.id, provider: m.provider })))
      }
    } catch { /* best-effort */ }
  }

  return (
    <div className="space-y-6">
      {/* Gateway Token */}
      <div>
        <div className="flex items-baseline justify-between mb-1.5">
          <label className="text-xs text-gray-400">AIGateway Token</label>
          <span className="text-xs text-gray-600">Bearer token used for all LLM and tool calls</span>
        </div>
        <div className="flex gap-2 items-center">
          <div className="relative flex-1">
            <input
              type={showToken ? 'text' : 'password'}
              value={data.gateway_token || ''}
              onChange={e => onChange('gateway_token', e.target.value)}
              placeholder="Paste AIGateway api_key, or use Re-register →"
              className="font-mono text-xs w-full pr-8"
            />
            <button
              type="button"
              onClick={() => setShowToken(v => !v)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-600 hover:text-gray-400"
            >
              {showToken ? <EyeOff size={13} /> : <Eye size={13} />}
            </button>
          </div>
          {onRegisterGateway && (
            <button
              type="button"
              onClick={onRegisterGateway}
              className="flex items-center gap-1.5 text-xs text-amber-500 hover:text-amber-400 border border-amber-500/30 px-2 py-1.5 rounded whitespace-nowrap"
              title="Create or refresh this agent's entry in AIGateway"
            >
              <RefreshCw size={12} /> Re-register
            </button>
          )}
        </div>
        {!data.gateway_token && (
          <p className="text-xs text-red-400/70 mt-1">No token set — LLM and tool calls will fail until registered.</p>
        )}
      </div>

      {/* System prompt */}
      <div>
        <div className="flex items-baseline justify-between mb-1.5">
          <label className="text-xs text-gray-400">System Prompt</label>
          <span className="text-xs text-gray-600">Defines the agent's core behaviour</span>
        </div>
        <textarea
          rows={8}
          value={data.system_prompt || ''}
          onChange={e => onChange('system_prompt', e.target.value)}
          placeholder="You are…"
          className="font-mono text-xs leading-relaxed"
        />
      </div>

      {/* Model */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Default Model</label>
          {models.length > 0 ? (
            <select
              value={data.default_model || ''}
              onChange={e => onChange('default_model', e.target.value)}
            >
              <option value="">— auto / smart routing —</option>
              {models.map(m => (
                <option key={m.id} value={m.id}>[{m.provider}] {m.name}</option>
              ))}
            </select>
          ) : (
            <input
              value={data.default_model || ''}
              onChange={e => onChange('default_model', e.target.value)}
              placeholder="e.g. google/gemma-3n-e4b-it:free"
            />
          )}
        </div>

        {/* Smart routing */}
        <div>
          <label className="block text-xs text-gray-400 mb-1.5">Smart Routing</label>
          <Toggle
            value={data.smart_routing}
            onChange={v => onChange('smart_routing', v)}
            label="Let AIGateway pick the best model"
          />
        </div>
      </div>

      {/* Attachments */}
      <div>
        <label className="block text-xs text-gray-500 uppercase tracking-wider mb-3">Accepts</label>
        <div className="flex gap-6">
          <Toggle
            value={data.accepts_attachments}
            onChange={v => onChange('accepts_attachments', v)}
            label="File attachments"
          />
          <Toggle
            value={data.accepts_images}
            onChange={v => onChange('accepts_images', v)}
            label="Images"
          />
        </div>
      </div>

      {/* MCP Tools — placeholder */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-xs text-gray-500 uppercase tracking-wider">MCP Tools</label>
          <span className="text-xs bg-gray-800 text-gray-500 border border-gray-700 px-2 py-0.5 rounded-full">
            Coming soon
          </span>
        </div>
        <div className="border border-dashed border-gray-800 rounded-lg p-4 text-center">
          <Wrench size={20} className="mx-auto mb-2 text-gray-700" />
          <p className="text-xs text-gray-600">
            Tool Manager not yet configured.<br />
            Agents will gain tool access when the Tool Manager service is available.
          </p>
        </div>
      </div>
    </div>
  )
}

function Toggle({ value, onChange, label }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer group">
      <button
        type="button"
        onClick={() => onChange(!value)}
        className={`relative w-9 h-5 rounded-full transition-colors ${value ? 'bg-amber-500' : 'bg-gray-700'}`}
      >
        <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${value ? 'translate-x-4' : ''}`} />
      </button>
      <span className="text-xs text-gray-400 group-hover:text-gray-300">{label}</span>
    </label>
  )
}
