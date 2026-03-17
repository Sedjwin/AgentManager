import React from 'react'

const FACE_THEMES   = ['mechanical', 'organic', 'abstract', 'minimal']
const EYE_STYLES    = ['angular', 'circular', 'compound', 'visor']
const MOUTH_STYLES  = ['thin', 'wide', 'segmented', 'aperture']
const IDLE_ANIMS    = ['breathing', 'scanning', 'pulsing', 'flickering']

export default function IdentityTab({ data, onChange }) {
  const spec = safeSpec(data.avatar_spec)

  function setSpec(key, val) {
    onChange('avatar_spec', { ...spec, [key]: val })
  }

  return (
    <div className="space-y-6">
      {/* Name */}
      <Field label="Name">
        <input
          value={data.name || ''}
          onChange={e => onChange('name', e.target.value)}
          placeholder="Agent name"
        />
      </Field>

      {/* Bio */}
      <Field label="Bio" hint="Shown on the agent card">
        <textarea
          rows={3}
          value={data.bio || ''}
          onChange={e => onChange('bio', e.target.value)}
          placeholder="A short description of this agent's role or character…"
        />
      </Field>

      {/* Avatar colours */}
      <div>
        <label className="block text-xs text-gray-500 uppercase tracking-wider mb-3">Avatar Colours</label>
        <div className="grid grid-cols-3 gap-4">
          {[
            ['color_primary',   'Primary'],
            ['color_secondary', 'Secondary'],
            ['color_accent',    'Accent'],
          ].map(([key, label]) => (
            <div key={key} className="flex flex-col gap-1">
              <span className="text-xs text-gray-500">{label}</span>
              <div className="flex gap-2 items-center">
                <input
                  type="color"
                  value={spec[key] || '#22d3ee'}
                  onChange={e => setSpec(key, e.target.value)}
                  className="w-10 h-8 rounded cursor-pointer"
                  style={{ width: 36, padding: 2 }}
                />
                <input
                  value={spec[key] || ''}
                  onChange={e => setSpec(key, e.target.value)}
                  placeholder="#hex"
                  style={{ fontSize: 11, padding: '4px 6px' }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Avatar shape */}
      <div>
        <label className="block text-xs text-gray-500 uppercase tracking-wider mb-3">Avatar Shape</label>
        <div className="grid grid-cols-2 gap-4">
          <Field label="Face theme">
            <select value={spec.face_theme || 'mechanical'} onChange={e => setSpec('face_theme', e.target.value)}>
              {FACE_THEMES.map(v => <option key={v}>{v}</option>)}
            </select>
          </Field>
          <Field label="Eye style">
            <select value={spec.eye_style || 'angular'} onChange={e => setSpec('eye_style', e.target.value)}>
              {EYE_STYLES.map(v => <option key={v}>{v}</option>)}
            </select>
          </Field>
          <Field label="Mouth style">
            <select value={spec.mouth_style || 'segmented'} onChange={e => setSpec('mouth_style', e.target.value)}>
              {MOUTH_STYLES.map(v => <option key={v}>{v}</option>)}
            </select>
          </Field>
          <Field label="Idle animation">
            <select value={spec.idle_animation || 'scanning'} onChange={e => setSpec('idle_animation', e.target.value)}>
              {IDLE_ANIMS.map(v => <option key={v}>{v}</option>)}
            </select>
          </Field>
        </div>
      </div>
    </div>
  )
}

function Field({ label, hint, children }) {
  return (
    <div>
      <div className="flex items-baseline gap-2 mb-1.5">
        <label className="text-xs text-gray-400">{label}</label>
        {hint && <span className="text-xs text-gray-600">{hint}</span>}
      </div>
      {children}
    </div>
  )
}

function safeSpec(v) {
  if (!v) return {}
  if (typeof v === 'object') return v
  try { return JSON.parse(v) } catch { return {} }
}
