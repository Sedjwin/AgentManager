import React, { useState } from 'react'
import { Sparkles, X, AlertTriangle, Plus, ChevronDown, ChevronRight } from 'lucide-react'

const VOICES = [
  { id: 'glados', label: 'GLaDOS',  hint: 'Robotic · Female · Dry humour',        color: 'cyan'   },
  { id: 'atlas',  label: 'ATLAS',   hint: 'Professional · Male · Neutral',         color: 'blue'   },
  { id: 'jarvis', label: 'JARVIS',  hint: 'Warm · British Male · Sophisticated',   color: 'amber'  },
  { id: 'tars',   label: 'TARS',    hint: 'Direct · US Male · Efficient wit',      color: 'gray'   },
]

const VOICE_STYLES = {
  cyan:  'border-cyan-500/60 bg-cyan-500/10 text-cyan-300',
  blue:  'border-blue-500/60 bg-blue-500/10 text-blue-300',
  amber: 'border-amber-500/60 bg-amber-500/10 text-amber-300',
  gray:  'border-gray-500/60 bg-gray-500/10 text-gray-300',
}

// Emotion performance parameters definition
const EMOTION_PARAMS = [
  { key: 'energy',       label: 'Energy',     hint: 'Lethargic ↔ Frantic',  min: 0,  max: 1,  step: 0.01, fmt: v => v.toFixed(2) },
  { key: 'valence',      label: 'Mood',        hint: 'Gloomy ↔ Elated',     min: -1, max: 1,  step: 0.01, fmt: v => v.toFixed(2) },
  { key: 'eye_openness', label: 'Eyes',        hint: 'Closed ↔ Wide',        min: 0,  max: 1,  step: 0.01, fmt: v => v.toFixed(2) },
  { key: 'mouth_curve',  label: 'Expression',  hint: 'Frown ↔ Smile',        min: -1, max: 1,  step: 0.01, fmt: v => v.toFixed(2) },
]

const DEFAULT_EMOTION = { energy: 0.5, valence: 0.0, eye_openness: 0.8, mouth_curve: 0.0 }

export default function PersonalityTab({ data, onChange, onGenerate, generating }) {
  const [showPremiumWarning, setShowPremiumWarning] = useState(false)
  const [expandedEmotions, setExpandedEmotions]     = useState({})   // name → bool
  const [editingName, setEditingName]               = useState(null) // name being renamed

  const emotions = safeObj(data.emotions)
  const traits   = safeArr(data.traits)

  // ── Traits ────────────────────────────────────────────────────────────────
  function addTrait(e) {
    if (e.key !== 'Enter') return
    const val = e.target.value.trim()
    if (!val || traits.includes(val)) return
    onChange('traits', [...traits, val])
    e.target.value = ''
  }

  function removeTrait(t) {
    onChange('traits', traits.filter(x => x !== t))
  }

  // ── Emotions ──────────────────────────────────────────────────────────────
  function addEmotion() {
    let name = 'new_emotion'
    let i = 2
    while (emotions[name]) { name = `new_emotion_${i++}` }
    const next = { ...emotions, [name]: { ...DEFAULT_EMOTION } }
    onChange('emotions', next)
    setExpandedEmotions(prev => ({ ...prev, [name]: true }))
    setEditingName(name)
  }

  function removeEmotion(name) {
    const next = { ...emotions }
    delete next[name]
    onChange('emotions', next)
  }

  function setEmotionParam(name, param, val) {
    onChange('emotions', {
      ...emotions,
      [name]: { ...emotions[name], [param]: val },
    })
  }

  function renameEmotion(oldName, newName) {
    const trimmed = newName.trim().toLowerCase().replace(/\s+/g, '_')
    if (!trimmed || trimmed === oldName || emotions[trimmed]) return
    const next = {}
    for (const [k, v] of Object.entries(emotions)) {
      next[k === oldName ? trimmed : k] = v
    }
    // Transfer expand state
    setExpandedEmotions(prev => {
      const n = { ...prev }
      if (n[oldName]) { n[trimmed] = n[oldName]; delete n[oldName] }
      return n
    })
    onChange('emotions', next)
    setEditingName(null)
  }

  function toggleExpand(name) {
    setExpandedEmotions(prev => ({ ...prev, [name]: !prev[name] }))
  }

  // ── Generate ──────────────────────────────────────────────────────────────
  function handleGenerate(quality) {
    if (quality === 'premium' && !showPremiumWarning) {
      setShowPremiumWarning(true)
      return
    }
    setShowPremiumWarning(false)
    onGenerate(quality)
  }

  return (
    <div className="space-y-6">
      {/* Description + generate buttons */}
      <div>
        <div className="flex items-center justify-between mb-1.5">
          <label className="text-xs text-gray-400">Personality Description</label>
          <div className="flex gap-2">
            <GenerateBtn label="AI"  title="Generate all fields using standard model" color="white" onClick={() => handleGenerate('standard')} loading={generating === 'standard'} disabled={!!generating} />
            <GenerateBtn label="AI+" title="Generate using premium model (may cost tokens)" color="gold"  onClick={() => handleGenerate('premium')}  loading={generating === 'premium'}  disabled={!!generating} />
          </div>
        </div>

        {showPremiumWarning && (
          <div className="mb-2 flex items-start gap-2 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-xs text-amber-300">
            <AlertTriangle size={14} className="shrink-0 mt-0.5" />
            <div className="flex-1">AI+ will request a premium model which may use paid tokens. Smart routing is enabled, so the actual model chosen may still be free.</div>
            <div className="flex gap-2">
              <button onClick={() => setShowPremiumWarning(false)} className="text-gray-500 hover:text-gray-400">Cancel</button>
              <button onClick={() => handleGenerate('premium')} className="text-amber-400 hover:text-amber-300 font-medium">Proceed</button>
            </div>
          </div>
        )}

        <textarea
          rows={5}
          value={data.personality_description || ''}
          onChange={e => onChange('personality_description', e.target.value)}
          placeholder="Describe the agent's character, appearance, tone and mood. E.g. 'Cold, sardonic AI. Speaks in short clipped sentences. Cyan glow. Becomes genuinely frustrated with incorrect answers.'"
        />
        <p className="text-xs text-gray-600 mt-1">
          Click <span className="text-gray-400">AI</span> or <span className="text-gray-400">AI+</span> to auto-fill all fields — traits, emotions, avatar, DNA, voice and system prompt — from this description.
        </p>
      </div>

      {/* Traits */}
      <div>
        <label className="block text-xs text-gray-400 mb-2">Traits</label>
        <div className="flex flex-wrap gap-2 mb-2">
          {traits.map(t => (
            <span key={t} className="tag">
              {t}
              <button onClick={() => removeTrait(t)} className="text-gray-600 hover:text-red-400"><X size={10} /></button>
            </span>
          ))}
        </div>
        <input placeholder="Type a trait and press Enter…" onKeyDown={addTrait} style={{ width: 220 }} />
      </div>

      {/* Emotions */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="block text-xs text-gray-500 uppercase tracking-wider">Emotional States</label>
          <button
            type="button"
            onClick={addEmotion}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs text-gray-400 border border-gray-700 hover:border-gray-500 hover:text-white transition-colors"
          >
            <Plus size={11} /> Add emotion
          </button>
        </div>
        <p className="text-xs text-gray-600 mb-3">
          Each named emotion is injected into the system prompt so the LLM knows which tags to use (e.g. <span className="font-mono text-gray-500">[SARCASTIC]</span>).
          Sliders define how it looks and sounds.
        </p>

        {Object.keys(emotions).length === 0 && (
          <div className="text-xs text-gray-700 border border-gray-800 rounded-lg p-4 text-center">
            No emotions defined yet — click <span className="text-gray-500">Add emotion</span> or use <span className="text-gray-500">AI</span> to generate.
          </div>
        )}

        <div className="space-y-2">
          {Object.entries(emotions).map(([name, params]) => {
            const p = safeParams(params)
            const expanded = !!expandedEmotions[name]
            const isEditing = editingName === name

            return (
              <div key={name} className="border border-gray-800 rounded-lg overflow-hidden">
                {/* Emotion header */}
                <div
                  className="flex items-center gap-2 px-3 py-2 bg-gray-900/60 cursor-pointer hover:bg-gray-800/60 transition-colors"
                  onClick={() => { if (!isEditing) toggleExpand(name) }}
                >
                  <span className="text-gray-600">{expanded ? <ChevronDown size={13} /> : <ChevronRight size={13} />}</span>

                  {isEditing ? (
                    <input
                      autoFocus
                      defaultValue={name}
                      className="flex-1 text-xs font-mono bg-transparent border-b border-amber-500/50 text-white focus:outline-none"
                      onBlur={e => renameEmotion(name, e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') renameEmotion(name, e.target.value); if (e.key === 'Escape') setEditingName(null) }}
                      onClick={e => e.stopPropagation()}
                    />
                  ) : (
                    <span
                      className="flex-1 text-xs font-mono text-white font-medium hover:text-amber-400 transition-colors"
                      onDoubleClick={e => { e.stopPropagation(); setEditingName(name) }}
                      title="Double-click to rename"
                    >
                      [{name.toUpperCase()}]
                    </span>
                  )}

                  {/* Mini param preview */}
                  {!expanded && (
                    <div className="flex gap-2 text-xs text-gray-600">
                      <span title="Energy">⚡{p.energy.toFixed(1)}</span>
                      <span title="Mood">{p.valence >= 0 ? '😊' : '😞'}{Math.abs(p.valence).toFixed(1)}</span>
                    </div>
                  )}

                  <button
                    type="button"
                    onClick={e => { e.stopPropagation(); removeEmotion(name) }}
                    className="text-gray-700 hover:text-red-400 transition-colors ml-1"
                  >
                    <X size={12} />
                  </button>
                </div>

                {/* Expanded sliders */}
                {expanded && (
                  <div className="px-4 py-3 space-y-3 bg-gray-900/30">
                    <p className="text-xs text-gray-600">Double-click the tag name above to rename. Sliders control how this emotion affects animations and speech.</p>
                    {EMOTION_PARAMS.map(({ key, label, hint, min, max, step, fmt }) => (
                      <div key={key}>
                        <div className="flex justify-between text-xs mb-1">
                          <div className="flex gap-2 text-gray-400">
                            <span>{label}</span>
                            <span className="text-gray-600">{hint}</span>
                          </div>
                          <span className="font-mono text-amber-400">{fmt(p[key] ?? (min + max) / 2)}</span>
                        </div>
                        <input
                          type="range" min={min} max={max} step={step}
                          value={p[key] ?? (min + max) / 2}
                          onChange={e => setEmotionParam(name, key, parseFloat(e.target.value))}
                          className="w-full accent-amber-500"
                          style={{ border: 'none', background: 'transparent', padding: 0 }}
                        />
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Voice */}
      <div>
        <label className="block text-xs text-gray-500 uppercase tracking-wider mb-3">Voice</label>
        <div className="grid grid-cols-2 gap-3 mb-4">
          {VOICES.map(v => {
            const active = data.voice === v.id
            return (
              <button
                key={v.id}
                type="button"
                onClick={() => onChange('voice', v.id)}
                className={`p-3 rounded-lg border text-left transition-colors ${
                  active
                    ? VOICE_STYLES[v.color]
                    : 'border-gray-800 bg-gray-900 text-gray-400 hover:border-gray-700'
                }`}
              >
                <div className="font-medium text-sm">{v.label}</div>
                <div className="text-xs text-gray-500 mt-0.5">{v.hint}</div>
              </button>
            )
          })}
        </div>

        {/* Voice params */}
        <div className="grid grid-cols-3 gap-4">
          <SliderField
            label="Speed"
            value={data.voice_speed ?? 1.0}
            min={0.5} max={2.0} step={0.05}
            onChange={v => onChange('voice_speed', v)}
            display={v => `${v.toFixed(2)}×`}
          />
          <SliderField
            label="Noise scale"
            value={data.noise_scale ?? 0.333}
            min={0} max={1} step={0.01}
            onChange={v => onChange('noise_scale', v)}
            display={v => v.toFixed(2)}
            hint={data.voice === 'glados' ? null : 'GLaDOS only'}
            disabled={data.voice !== 'glados'}
          />
          <SliderField
            label="Noise W"
            value={data.noise_w ?? 0.333}
            min={0} max={1} step={0.01}
            onChange={v => onChange('noise_w', v)}
            display={v => v.toFixed(2)}
            hint={data.voice === 'glados' ? null : 'GLaDOS only'}
            disabled={data.voice !== 'glados'}
          />
        </div>
      </div>
    </div>
  )
}

// ── Sub-components ───────────────────────────────────────────────────────────

function GenerateBtn({ label, title, color, onClick, loading, disabled }) {
  const isGold = color === 'gold'
  return (
    <button
      type="button" title={title} onClick={onClick} disabled={disabled}
      className={`flex items-center gap-1.5 px-3 py-1 rounded-md text-xs font-bold border transition-all
        ${isGold
          ? 'border-amber-500/60 text-amber-400 bg-amber-500/10 hover:bg-amber-500/20'
          : 'border-gray-600 text-gray-300 bg-gray-800 hover:bg-gray-700'}
        ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
      `}
    >
      <Sparkles size={11} className={isGold ? 'text-amber-400' : ''} />
      {loading ? '…' : label}
    </button>
  )
}

function SliderField({ label, value, min, max, step, onChange, display, hint, disabled }) {
  return (
    <div className={disabled ? 'opacity-40' : ''}>
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <div>
          <span>{label}</span>
          {hint && <span className="text-gray-700 ml-1 text-xs">({hint})</span>}
        </div>
        <span className="text-gray-400 font-mono">{display(value)}</span>
      </div>
      <input
        type="range" min={min} max={max} step={step} value={value}
        onChange={e => !disabled && onChange(parseFloat(e.target.value))}
        disabled={disabled}
        className="w-full accent-amber-500"
        style={{ border: 'none', background: 'transparent', padding: 0 }}
      />
    </div>
  )
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function safeObj(v) {
  if (!v) return {}
  if (typeof v === 'object' && !Array.isArray(v)) return v
  try { return JSON.parse(v) } catch { return {} }
}

function safeArr(v) {
  if (!v) return []
  if (Array.isArray(v)) return v
  try { return JSON.parse(v) } catch { return [] }
}

function safeParams(v) {
  const base = { ...DEFAULT_EMOTION }
  if (!v || typeof v !== 'object') return base
  return { ...base, ...v }
}
