import React, { useState } from 'react'
import { Sparkles, X, AlertTriangle } from 'lucide-react'

const EMOTION_OPTIONS = {
  idle:       ['neutral', 'calm', 'alert', 'curious', 'bored'],
  processing: ['focused', 'thinking', 'calculating', 'scanning', 'anxious'],
  speaking:   ['engaged', 'animated', 'precise', 'warm', 'cold'],
  error:      ['irritated', 'confused', 'apologetic', 'stern', 'dismissive'],
}

const VOICES = [
  { id: 'glados', label: 'GLaDOS',  hint: 'Robotic · Female · Dry humour' },
  { id: 'atlas',  label: 'ATLAS',   hint: 'Professional · Male · Neutral' },
]

export default function PersonalityTab({ data, onChange, onGenerate, generating }) {
  const [showPremiumWarning, setShowPremiumWarning] = useState(false)
  const emotions = safeObj(data.emotions)
  const traits   = safeArr(data.traits)

  function setEmotion(key, val) {
    onChange('emotions', { ...emotions, [key]: val })
  }

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
            <GenerateBtn
              label="AI"
              title="Generate using free/standard model"
              color="white"
              onClick={() => handleGenerate('standard')}
              loading={generating === 'standard'}
              disabled={!!generating}
            />
            <GenerateBtn
              label="AI+"
              title="Generate using premium model (may cost tokens)"
              color="gold"
              onClick={() => handleGenerate('premium')}
              loading={generating === 'premium'}
              disabled={!!generating}
            />
          </div>
        </div>

        {/* Premium warning */}
        {showPremiumWarning && (
          <div className="mb-2 flex items-start gap-2 bg-amber-500/10 border border-amber-500/30 rounded-lg p-3 text-xs text-amber-300">
            <AlertTriangle size={14} className="shrink-0 mt-0.5" />
            <div className="flex-1">
              AI+ will request a premium model which may use paid tokens. Smart routing is enabled, so the actual model chosen may still be free.
            </div>
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
          Click <span className="text-gray-400">AI</span> to auto-fill traits, emotions, avatar and system prompt from this description.
        </p>
      </div>

      {/* Traits */}
      <div>
        <label className="block text-xs text-gray-400 mb-2">Traits</label>
        <div className="flex flex-wrap gap-2 mb-2">
          {traits.map(t => (
            <span key={t} className="tag">
              {t}
              <button onClick={() => removeTrait(t)} className="text-gray-600 hover:text-red-400">
                <X size={10} />
              </button>
            </span>
          ))}
        </div>
        <input
          placeholder="Type a trait and press Enter…"
          onKeyDown={addTrait}
          style={{ width: 220 }}
        />
      </div>

      {/* Emotions */}
      <div>
        <label className="block text-xs text-gray-500 uppercase tracking-wider mb-3">Emotional States</label>
        <div className="grid grid-cols-2 gap-3">
          {Object.entries(EMOTION_OPTIONS).map(([state, opts]) => (
            <div key={state}>
              <label className="block text-xs text-gray-500 capitalize mb-1">{state}</label>
              <select
                value={emotions[state] || opts[0]}
                onChange={e => setEmotion(state, e.target.value)}
              >
                {opts.map(o => <option key={o}>{o}</option>)}
              </select>
            </div>
          ))}
        </div>
      </div>

      {/* Voice */}
      <div>
        <label className="block text-xs text-gray-500 uppercase tracking-wider mb-3">Voice</label>

        {/* Voice picker */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          {VOICES.map(v => (
            <button
              key={v.id}
              type="button"
              onClick={() => onChange('voice', v.id)}
              className={`p-3 rounded-lg border text-left transition-colors ${
                data.voice === v.id
                  ? 'border-amber-500/60 bg-amber-500/10 text-white'
                  : 'border-gray-800 bg-gray-900 text-gray-400 hover:border-gray-700'
              }`}
            >
              <div className="font-medium text-sm">{v.label}</div>
              <div className="text-xs text-gray-500 mt-0.5">{v.hint}</div>
            </button>
          ))}
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
          />
          <SliderField
            label="Noise W"
            value={data.noise_w ?? 0.333}
            min={0} max={1} step={0.01}
            onChange={v => onChange('noise_w', v)}
            display={v => v.toFixed(2)}
          />
        </div>
      </div>
    </div>
  )
}

function GenerateBtn({ label, title, color, onClick, loading, disabled }) {
  const isGold = color === 'gold'
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
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

function SliderField({ label, value, min, max, step, onChange, display }) {
  return (
    <div>
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>{label}</span>
        <span className="text-gray-400 font-mono">{display(value)}</span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        onChange={e => onChange(parseFloat(e.target.value))}
        className="w-full accent-amber-500"
        style={{ border: 'none', background: 'transparent', padding: 0 }}
      />
    </div>
  )
}

function safeObj(v) {
  if (!v) return {}
  if (typeof v === 'object') return v
  try { return JSON.parse(v) } catch { return {} }
}

function safeArr(v) {
  if (!v) return []
  if (Array.isArray(v)) return v
  try { return JSON.parse(v) } catch { return [] }
}
