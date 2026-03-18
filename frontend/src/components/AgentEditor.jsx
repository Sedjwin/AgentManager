import React, { useEffect, useState } from 'react'
import { ArrowLeft, Save, Trash2, RefreshCw, AlertCircle, CheckCircle } from 'lucide-react'
import AvatarCanvas from './AvatarCanvas'
import IdentityTab   from './tabs/IdentityTab'
import SetupTab      from './tabs/SetupTab'
import PersonalityTab from './tabs/PersonalityTab'

const TABS = ['Identity', 'Setup', 'Personality']

export default function AgentEditor({ agentId, onBack, onDeleted }) {
  const isNew = agentId === 'new'

  const [data, setData] = useState(defaultAgent())
  const [saved, setSaved] = useState(null)   // null | 'saving' | 'ok' | 'err'
  const [saveError, setSaveError] = useState('')
  const [activeTab, setActiveTab] = useState('Identity')
  const [generating, setGenerating] = useState(null)   // null | 'standard' | 'premium'
  const [dirty, setDirty] = useState(false)

  useEffect(() => {
    if (!isNew) fetchAgent()
  }, [agentId])

  async function fetchAgent() {
    try {
      const r = await fetch(`/agents/${agentId}`)
      if (!r.ok) throw new Error(await r.text())
      setData(await r.json())
      setDirty(false)
    } catch (e) {
      console.error(e)
    }
  }

  function setField(key, val) {
    setData(d => ({ ...d, [key]: val }))
    setDirty(true)
  }

  async function save() {
    setSaved('saving')
    setSaveError('')
    try {
      const url    = isNew ? '/agents' : `/agents/${agentId}`
      const method = isNew ? 'POST'    : 'PUT'
      const r = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      })
      if (!r.ok) throw new Error(await r.text())
      const fresh = await r.json()
      setData(fresh)
      setDirty(false)
      setSaved('ok')
      if (isNew) onBack()
      setTimeout(() => setSaved(null), 3000)
      return true
    } catch (e) {
      setSaved('err')
      setSaveError(e.message)
      return false
    }
  }

  async function handleDelete() {
    if (!confirm(`Delete agent "${data.name}"? This cannot be undone.`)) return
    await fetch(`/agents/${agentId}`, { method: 'DELETE' })
    onDeleted()
  }

  async function handleGenerate(quality) {
    if (!agentId || isNew) {
      setSaveError('Save the agent first before using AI generation.')
      setSaved('err')
      setTimeout(() => setSaved(null), 3000)
      return
    }

    // Save first so the AI sees the latest form state (name, bio, description, etc.)
    if (dirty) {
      const ok = await save()
      if (!ok) return   // abort if save failed
    }

    setGenerating(quality)
    try {
      const r = await fetch(`/agents/${agentId}/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quality }),
      })
      if (!r.ok) {
        const body = await r.text()
        throw new Error(body)
      }
      const result = await r.json()
      // Apply the returned agent directly — no second round-trip needed
      if (result.agent) {
        setData(result.agent)
        setDirty(false)
      }
      setSaved('ok')
      setTimeout(() => setSaved(null), 3000)
    } catch (e) {
      setSaveError(`AI generation failed: ${e.message}`)
      setSaved('err')
    } finally {
      setGenerating(null)
    }
  }

  const avatarSpec = safeSpec(data.avatar_spec)

  return (
    <div className="min-h-screen p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <button onClick={onBack} className="flex items-center gap-2 text-gray-500 hover:text-white transition-colors text-sm">
          <ArrowLeft size={16} /> Agents
        </button>

        <div className="flex items-center gap-3">
          {/* Enabled toggle */}
          {!isNew && (
            <label className="flex items-center gap-2 cursor-pointer text-xs text-gray-500">
              <button
                type="button"
                onClick={() => setField('enabled', !data.enabled)}
                className={`relative w-8 h-4 rounded-full transition-colors ${data.enabled ? 'bg-green-500' : 'bg-gray-700'}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${data.enabled ? 'translate-x-4' : ''}`} />
              </button>
              {data.enabled ? 'Enabled' : 'Disabled'}
            </label>
          )}

          {/* Demo playground visibility toggle */}
          {!isNew && (
            <label className="flex items-center gap-2 cursor-pointer text-xs text-gray-500">
              <button
                type="button"
                onClick={() => setField('demo_playground_enabled', !data.demo_playground_enabled)}
                className={`relative w-8 h-4 rounded-full transition-colors ${data.demo_playground_enabled ? 'bg-amber-500' : 'bg-gray-700'}`}
              >
                <span className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${data.demo_playground_enabled ? 'translate-x-4' : ''}`} />
              </button>
              Demo playground
            </label>
          )}

          {/* Delete */}
          {!isNew && (
            <button onClick={handleDelete} className="text-gray-600 hover:text-red-400 transition-colors p-1">
              <Trash2 size={15} />
            </button>
          )}


          {/* Save */}
          <button
            onClick={save}
            disabled={saved === 'saving'}
            className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-sm font-medium transition-colors
              ${dirty || isNew
                ? 'bg-amber-500 hover:bg-amber-400 text-black'
                : 'bg-gray-800 text-gray-500 cursor-default'
              }`}
          >
            {saved === 'saving' ? <><RefreshCw size={14} className="animate-spin" /> Saving…</>
              : saved === 'ok'  ? <><CheckCircle size={14} /> Saved</>
              : saved === 'err' ? <><AlertCircle size={14} /> Error</>
              : <><Save size={14} /> Save</>
            }
          </button>
        </div>
      </div>

      {saveError && (
        <div className="mb-4 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded p-2">
          {saveError}
        </div>
      )}

      {/* Main layout */}
      <div className="flex gap-6">
        {/* Left: avatar column */}
        <div className="shrink-0 w-52 flex flex-col items-center gap-4">
          <AvatarCanvas spec={avatarSpec} size={180} animated />

          <div className="text-center">
            <h2 className="font-bold text-white text-lg">{data.name || 'New Agent'}</h2>
            {data.gateway_token && (
              <p className="text-xs text-gray-600 mt-1 font-mono truncate w-44" title={data.gateway_token}>
                gw: {data.gateway_token.substring(0, 12)}…
              </p>
            )}
          </div>

          {/* Quick voice badge */}
          {data.voice && (
            <span className="text-xs bg-purple-500/10 border border-purple-500/20 text-purple-400 px-3 py-1 rounded-full">
              {data.voice}
            </span>
          )}

          {/* Emotion preview */}
          {safeObj(data.emotions).idle && (
            <div className="w-full text-xs text-gray-600 space-y-1">
              {Object.entries(safeObj(data.emotions)).map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-gray-700 capitalize">{k}</span>
                  <span className="text-gray-500">{v}</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: tabs */}
        <div className="flex-1 min-w-0">
          {/* Tab bar */}
          <div className="flex border-b border-gray-800 mb-6">
            {TABS.map(t => (
              <button
                key={t}
                onClick={() => setActiveTab(t)}
                className={`px-5 py-2 text-sm font-medium border-b-2 transition-colors -mb-px
                  ${activeTab === t
                    ? 'border-amber-500 text-white'
                    : 'border-transparent text-gray-500 hover:text-gray-300'
                  }`}
              >
                {t}
              </button>
            ))}

            {/* Generating indicator */}
            {generating && (
              <span className="ml-auto flex items-center gap-2 text-xs text-amber-400 pr-1">
                <RefreshCw size={12} className="animate-spin" />
                Generating ({generating})…
              </span>
            )}
          </div>

          {/* Tab content */}
          <div className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 220px)' }}>
            {activeTab === 'Identity'    && <IdentityTab    data={data} onChange={setField} />}
            {activeTab === 'Setup'       && <SetupTab       data={data} onChange={setField} onRegisterGateway={!isNew ? async () => { await fetch(`/agents/${agentId}/register-gateway`, { method: 'POST' }); fetchAgent() } : null} />}
            {activeTab === 'Personality' && <PersonalityTab data={data} onChange={setField} onGenerate={handleGenerate} generating={generating} />}
          </div>
        </div>
      </div>
    </div>
  )
}

function defaultAgent() {
  return {
    name: '',
    bio: '',
    enabled: true,
    system_prompt: '',
    default_model: '',
    smart_routing: false,
    mcp_tools: [],
    accepts_attachments: false,
    accepts_images: false,
    voice: 'glados',
    demo_playground_enabled: true,
    voice_speed: 1.0,
    noise_scale: 0.333,
    noise_w: 0.333,
    personality_description: '',
    traits: [],
    emotions: { idle: 'neutral', processing: 'focused', speaking: 'engaged', error: 'irritated' },
    avatar_spec: {
      color_primary: '#22d3ee',
      color_secondary: '#0f172a',
      color_accent: '#f59e0b',
      face_theme: 'mechanical',
      eye_style: 'angular',
      mouth_style: 'segmented',
      idle_animation: 'scanning',
    },
  }
}

function safeSpec(v) {
  if (!v) return {}
  if (typeof v === 'object') return v
  try { return JSON.parse(v) } catch { return {} }
}

function safeObj(v) {
  if (!v) return {}
  if (typeof v === 'object') return v
  try { return JSON.parse(v) } catch { return {} }
}
