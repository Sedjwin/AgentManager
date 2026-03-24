import { useState, useEffect } from 'react'
import { X, Save, Loader } from 'lucide-react'
import { createAgent, updateAgent } from './api.js'

async function fetchAgentTools(agentId) {
  const r = await fetch(`/agents/${agentId}/tools`)
  return r.ok ? r.json() : []
}

async function saveAgentTools(agentId, toolUseEnabled, enabledTools) {
  await fetch(`/agents/${agentId}/tools`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ tool_use_enabled: toolUseEnabled, enabled_tools: enabledTools }),
  })
}

function Field({ label, children, hint }) {
  return (
    <div>
      <label className="block text-xs text-gray-400 mb-1">{label}</label>
      {children}
      {hint && <p className="text-xs text-gray-600 mt-1">{hint}</p>}
    </div>
  )
}

function Input({ ...props }) {
  return (
    <input
      {...props}
      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-amber-500 transition-colors"
    />
  )
}

function Textarea({ ...props }) {
  return (
    <textarea
      {...props}
      rows={4}
      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-amber-500 transition-colors resize-y font-mono"
    />
  )
}

function Slider({ label, value, onChange, min = 0, max = 1, step = 0.01 }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>{label}</span>
        <span className="font-mono text-gray-400">{Number(value).toFixed(2)}</span>
      </div>
      <input type="range" min={min} max={max} step={step} value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-full accent-amber-500 h-1.5"
      />
    </div>
  )
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-3 cursor-pointer" onClick={() => onChange(!checked)}>
      <div className={`relative w-10 h-5 rounded-full transition-colors ${checked ? 'bg-amber-500' : 'bg-gray-700'}`}>
        <span className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${checked ? 'translate-x-5' : ''}`} />
      </div>
      <span className="text-sm text-gray-300">{label}</span>
    </label>
  )
}

export default function AgentModal({ agent, onClose, onSaved }) {
  const isEdit = !!agent

  const [name, setName]               = useState(agent?.name ?? '')
  const [token, setToken]             = useState(agent?.ai_gateway_token ?? '')
  const [systemPrompt, setSystemPrompt] = useState(agent?.system_prompt ?? '')
  const [voiceEnabled, setVoiceEnabled] = useState(agent?.voice_enabled ?? false)
  const [voiceId, setVoiceId]         = useState(agent?.voice_config?.voice_id ?? 'glados')
  const [voices, setVoices]           = useState(['glados'])

  useEffect(() => {
    fetch('/voices')
      .then(r => r.json())
      .then(data => setVoices(data.voices.map(v => v.id)))
      .catch(() => {})
  }, [])

  const [hasProfile, setHasProfile]   = useState(!!agent?.profile)
  const [displayName, setDisplayName] = useState(agent?.profile?.display_name ?? '')
  const [tagline, setTagline]         = useState(agent?.profile?.tagline ?? '')

  // Personality base sliders
  const pb = agent?.profile?.personality_base ?? {}
  const [energy, setEnergy]       = useState(pb.energy ?? 0.5)
  const [warmth, setWarmth]       = useState(pb.warmth ?? 0.5)
  const [stability, setStability] = useState(pb.stability ?? 0.7)
  const [confidence, setConfidence] = useState(pb.confidence ?? 0.7)
  const [vpBase, setVpBase]       = useState(pb.voice_pitch_base ?? 0.5)
  const [vsBase, setVsBase]       = useState(pb.voice_speed_base ?? 0.5)
  const [animTempo, setAnimTempo] = useState(pb.animation_tempo ?? 0.5)

  // Appearance colours (simplified)
  const ap = agent?.profile?.appearance ?? {}
  const [primaryColor, setPrimaryColor]     = useState(ap.primary_color ?? '#22d3ee')
  const [secondaryColor, setSecondaryColor] = useState(ap.secondary_color ?? '#0f172a')
  const [eyeColor, setEyeColor]             = useState(ap.eye_color ?? '#FFFFFF')
  const [highlightColor, setHighlightColor] = useState(ap.highlight_color ?? '#7BB8F0')

  // Appearance shape sliders
  const [faceRound, setFaceRound]   = useState(ap.face_roundness ?? 0.5)
  const [eyeCount, setEyeCount]     = useState(ap.eye_count ?? 2)
  const [eyeSize, setEyeSize]       = useState(ap.eye_size ?? 0.5)
  const [eyeRound, setEyeRound]     = useState(ap.eye_shape_roundness ?? 0.5)
  const [mouthWidth, setMouthWidth] = useState(ap.mouth_width ?? 0.5)
  const [lineWeight, setLineWeight] = useState(ap.line_weight ?? 0.4)
  const [complexity, setComplexity] = useState(ap.complexity ?? 0.3)

  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState(null)

  // Tool use
  const [toolUseEnabled, setToolUseEnabled] = useState(agent?.tool_use_enabled ?? false)
  const [enabledTools, setEnabledTools]     = useState(new Set(agent?.enabled_tools ?? []))
  const [grantedTools, setGrantedTools]     = useState([])
  const [toolsLoading, setToolsLoading]     = useState(false)

  useEffect(() => {
    if (!isEdit) return
    setToolsLoading(true)
    fetchAgentTools(agent.agent_id).then(tools => {
      setGrantedTools(tools)
      setToolsLoading(false)
    })
  }, [isEdit, agent?.agent_id])

  async function handleSave() {
    if (!name.trim()) { setError('Name is required'); return }
    if (!isEdit && !token.trim()) { setError('AI Gateway token is required'); return }
    setSaving(true)
    setError(null)
    try {
      const body = {
        name: name.trim(),
        ...(token.trim() ? { ai_gateway_token: token.trim() } : {}),
        system_prompt: systemPrompt,
        voice_enabled: voiceEnabled,
        voice_config: voiceEnabled ? { voice_id: voiceId } : null,
        profile: hasProfile ? buildProfile() : null,
      }
      if (isEdit) {
        await updateAgent(agent.agent_id, body)
        await saveAgentTools(agent.agent_id, toolUseEnabled, [...enabledTools])
      } else {
        await createAgent(body)
      }
      onSaved()
    } catch (e) {
      setError(e.message)
    } finally {
      setSaving(false)
    }
  }

  function buildProfile() {
    const existing = agent?.profile ?? {}
    return {
      display_name: displayName || name,
      tagline,
      appearance: {
        face_roundness: faceRound, face_width: ap.face_width ?? 0.5, face_height: ap.face_height ?? 0.6,
        eye_count: eyeCount,
        eye_size: eyeSize, eye_spacing: ap.eye_spacing ?? 0.5, eye_height: ap.eye_height ?? 0.55,
        eye_shape_roundness: eyeRound, pupil_size: ap.pupil_size ?? 0.6,
        mouth_width: mouthWidth, mouth_height: ap.mouth_height ?? 0.35, mouth_thickness: ap.mouth_thickness ?? 0.3,
        has_nose: ap.has_nose ?? false, nose_size: ap.nose_size ?? 0.0,
        has_eyebrows: ap.has_eyebrows ?? true, eyebrow_thickness: ap.eyebrow_thickness ?? 0.4,
        eyebrow_curve: ap.eyebrow_curve ?? 0.3, has_ears: ap.has_ears ?? false,
        primary_color: primaryColor, secondary_color: secondaryColor,
        eye_color: eyeColor, pupil_color: ap.pupil_color ?? '#1A1A2E',
        mouth_color: ap.mouth_color ?? '#D94A6B', highlight_color: highlightColor,
        line_weight: lineWeight, complexity,
      },
      personality_base: {
        energy, warmth, stability, confidence,
        voice_pitch_base: vpBase, voice_speed_base: vsBase, animation_tempo: animTempo,
      },
      emotions: existing.emotions ?? {},
      actions: existing.actions ?? {},
      idle: existing.idle ?? {
        breathing: { face_scale: { amplitude: 0.01, frequency: 0.25 }, eye_offset_y: { amplitude: 0.005, frequency: 0.25 } },
        blink_interval_ms: 3500, blink_duration_ms: 150,
        micro_movements: true, micro_movement_intensity: 0.3,
      },
      fallback: existing.fallback ?? {
        base_dimensions: ['energy', 'valence', 'arousal'],
        unknown_emotion_strategy: 'approximate', unknown_action_strategy: 'ignore',
      },
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-2xl max-h-[90vh] flex flex-col shadow-2xl">
        {/* Modal header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-800 shrink-0">
          <h2 className="text-base font-semibold text-white">{isEdit ? `Edit — ${agent.name}` : 'New Agent'}</h2>
          <button onClick={onClose} className="p-1.5 rounded hover:bg-gray-800 text-gray-500 hover:text-gray-300 transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="overflow-y-auto flex-1 px-6 py-5 space-y-6">
          {error && (
            <div className="p-3 bg-red-950 border border-red-800 rounded-lg text-xs text-red-300">{error}</div>
          )}

          {/* Basic fields */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Basic</h3>
            <Field label="Name *">
              <Input value={name} onChange={e => setName(e.target.value)} placeholder="GlaDOS" />
            </Field>
            <Field label={isEdit ? 'AI Gateway Token' : 'AI Gateway Token *'} hint={isEdit ? 'Leave blank to keep the existing token.' : 'The Bearer token assigned to this agent in AIGateway.'}>
              <Input value={token} onChange={e => setToken(e.target.value)} placeholder={isEdit ? '(unchanged)' : '34e93070...'} type="password" />
            </Field>
            <Field label="System Prompt" hint="The agent's core instructions. For Interaction agents, annotation instructions are appended automatically.">
              <Textarea value={systemPrompt} onChange={e => setSystemPrompt(e.target.value)} placeholder="You are..." rows={5} />
            </Field>
          </div>

          {/* Voice */}
          <div className="space-y-4">
            <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Voice</h3>
            <Toggle label="Enable voice (TTS/STT)" checked={voiceEnabled} onChange={setVoiceEnabled} />
            {voiceEnabled && (
              <div className="space-y-4 pl-4 border-l-2 border-gray-800">
                <Field label="Voice" hint="Fine-tune speed and pitch in VoiceService admin panel.">
                  <select value={voiceId} onChange={e => setVoiceId(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-amber-500">
                    {voices.map(v => <option key={v} value={v}>{v}</option>)}
                  </select>
                </Field>
              </div>
            )}
          </div>

          {/* Interaction Profile */}
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Interaction Profile</h3>
              <Toggle label="" checked={hasProfile} onChange={setHasProfile} />
              <span className="text-xs text-gray-500">{hasProfile ? 'Enabled (Interaction Agent)' : 'Disabled (Functional Agent)'}</span>
            </div>

            {hasProfile && (
              <div className="space-y-6 pl-4 border-l-2 border-gray-800">
                <div className="space-y-4">
                  <h4 className="text-xs text-gray-600 uppercase tracking-wider">Identity</h4>
                  <Field label="Display Name">
                    <Input value={displayName} onChange={e => setDisplayName(e.target.value)} placeholder={name} />
                  </Field>
                  <Field label="Tagline">
                    <Input value={tagline} onChange={e => setTagline(e.target.value)} placeholder="Brief personality description" />
                  </Field>
                </div>

                <div className="space-y-3">
                  <h4 className="text-xs text-gray-600 uppercase tracking-wider">Personality Base</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <Slider label="Energy" value={energy} onChange={setEnergy} />
                    <Slider label="Warmth" value={warmth} onChange={setWarmth} />
                    <Slider label="Stability" value={stability} onChange={setStability} />
                    <Slider label="Confidence" value={confidence} onChange={setConfidence} />
                    <Slider label="Voice Pitch" value={vpBase} onChange={setVpBase} />
                    <Slider label="Voice Speed" value={vsBase} onChange={setVsBase} />
                    <Slider label="Animation Tempo" value={animTempo} onChange={setAnimTempo} />
                  </div>
                </div>

                <div className="space-y-3">
                  <h4 className="text-xs text-gray-600 uppercase tracking-wider">Appearance</h4>
                  <Field label="Eye Count">
                    <select value={eyeCount} onChange={e => setEyeCount(parseInt(e.target.value))}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-100 focus:outline-none focus:border-amber-500">
                      <option value={0}>Visor / line</option>
                      <option value={1}>Single (centred)</option>
                      <option value={2}>Two eyes</option>
                    </select>
                  </Field>
                  <div className="grid grid-cols-2 gap-4">
                    <Slider label="Face Roundness" value={faceRound} onChange={setFaceRound} />
                    <Slider label="Eye Size" value={eyeSize} onChange={setEyeSize} />
                    <Slider label="Eye Roundness" value={eyeRound} onChange={setEyeRound} />
                    <Slider label="Mouth Width" value={mouthWidth} onChange={setMouthWidth} />
                    <Slider label="Line Weight" value={lineWeight} onChange={setLineWeight} />
                    <Slider label="Complexity" value={complexity} onChange={setComplexity} />
                  </div>
                  <div className="grid grid-cols-2 gap-4 mt-2">
                    {[
                      ['Primary Color', primaryColor, setPrimaryColor],
                      ['Secondary Color', secondaryColor, setSecondaryColor],
                      ['Eye Color', eyeColor, setEyeColor],
                      ['Highlight Color', highlightColor, setHighlightColor],
                    ].map(([label, val, set]) => (
                      <div key={label} className="flex items-center gap-2">
                        <input type="color" value={val} onChange={e => set(e.target.value)}
                          className="w-8 h-8 rounded cursor-pointer border border-gray-700 bg-transparent" />
                        <div>
                          <div className="text-xs text-gray-500">{label}</div>
                          <div className="text-xs text-gray-400 font-mono">{val}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {isEdit && agent?.profile && (
                  <p className="text-xs text-gray-600">
                    Emotions and actions are preserved from the existing profile. Edit the raw profile via API or the JSON editor to modify them.
                  </p>
                )}
              </div>
            )}
          </div>
          {/* Tool Use — edit only */}
          {isEdit && (
            <div className="space-y-4">
              <div className="flex items-center gap-3">
                <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Tool Use</h3>
              </div>
              <Toggle label="Enable tool use" checked={toolUseEnabled} onChange={setToolUseEnabled} />
              {toolUseEnabled && (
                <div className="space-y-2 pl-4 border-l-2 border-gray-800">
                  {toolsLoading && <p className="text-xs text-gray-600">Loading granted tools…</p>}
                  {!toolsLoading && grantedTools.length === 0 && (
                    <p className="text-xs text-gray-600 italic">No tools granted to this agent yet — grant tools in ToolGateway first.</p>
                  )}
                  {grantedTools.map(t => (
                    <label key={t.tool_id} className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer ${
                      t.grant_enabled && t.enabled ? 'border-gray-700 bg-gray-800/50 hover:border-gray-600' : 'border-gray-800 opacity-50 cursor-not-allowed'
                    }`}>
                      <input
                        type="checkbox"
                        checked={enabledTools.has(t.name)}
                        disabled={!t.grant_enabled || !t.enabled}
                        onChange={e => {
                          const next = new Set(enabledTools)
                          e.target.checked ? next.add(t.name) : next.delete(t.name)
                          setEnabledTools(next)
                        }}
                        className="mt-0.5 accent-amber-500"
                      />
                      <div>
                        <div className="text-sm font-mono text-violet-300">{t.name}</div>
                        {t.description && <div className="text-xs text-gray-500">{t.description}</div>}
                        {!t.grant_enabled && <div className="text-xs text-gray-600">(grant disabled in ToolGateway)</div>}
                        {!t.enabled && <div className="text-xs text-gray-600">(tool disabled in ToolGateway)</div>}
                      </div>
                    </label>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-800 shrink-0 flex justify-end gap-3">
          <button onClick={onClose}
            className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-gray-200 hover:bg-gray-800 transition-colors">
            Cancel
          </button>
          <button onClick={handleSave} disabled={saving}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-amber-500 hover:bg-amber-400 text-black text-sm font-semibold transition-colors disabled:opacity-60">
            {saving ? <Loader className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
