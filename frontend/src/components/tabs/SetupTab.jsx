import React, { useEffect, useState } from 'react'
import { Wrench, ChevronDown, ChevronRight } from 'lucide-react'

export default function SetupTab({ data, onChange }) {
  const [models, setModels] = useState([])

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
