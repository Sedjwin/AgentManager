/**
 * AvatarCanvas — renders a stylized face SVG from an avatar_spec JSON object.
 *
 * avatar_spec fields used:
 *   color_primary    — head fill
 *   color_secondary  — glow / shadow color
 *   color_accent     — eyes + mouth
 *   face_theme       — "mechanical" | "organic" | "abstract" | "minimal"
 *   eye_style        — "angular" | "circular" | "compound" | "visor"
 *   mouth_style      — "thin" | "wide" | "segmented" | "aperture"
 *   idle_animation   — "breathing" | "scanning" | "pulsing" | "flickering"
 *   dna              — { energy, warmth, confidence, erraticness } (0–1 each)
 *
 * Optional:
 *   currentEmotion   — { eye_openness, mouth_curve } applied live
 */
import React, { useId } from 'react'

const DEFAULTS = {
  color_primary:   '#22d3ee',
  color_secondary: '#0f172a',
  color_accent:    '#f59e0b',
  face_theme:      'mechanical',
  eye_style:       'angular',
  mouth_style:     'segmented',
  idle_animation:  'scanning',
  dna: { energy: 0.5, warmth: 0.5, confidence: 0.7, erraticness: 0.1 },
}

const DNA_DEFAULTS = { energy: 0.5, warmth: 0.5, confidence: 0.7, erraticness: 0.1 }

function hexPoints(cx, cy, r, sides = 6) {
  return Array.from({ length: sides }, (_, i) => {
    const a = (Math.PI / (sides / 2)) * i - Math.PI / 2
    return `${cx + r * Math.cos(a)},${cy + r * Math.sin(a)}`
  }).join(' ')
}

function darken(hex, amount = 40) {
  const n = parseInt(hex.replace('#', ''), 16)
  const r = Math.max(0, (n >> 16) - amount)
  const g = Math.max(0, ((n >> 8) & 0xff) - amount)
  const b = Math.max(0, (n & 0xff) - amount)
  return `#${((r << 16) | (g << 8) | b).toString(16).padStart(6, '0')}`
}

// Linearly interpolate between two values
function lerp(a, b, t) { return a + (b - a) * Math.max(0, Math.min(1, t)) }

function FaceShape({ theme, cx, cy, r, fill, stroke }) {
  const s = { fill, stroke, strokeWidth: 2 }
  if (theme === 'mechanical') return <polygon points={hexPoints(cx, cy, r)} style={s} />
  if (theme === 'organic')    return <ellipse cx={cx} cy={cy} rx={r * 0.88} ry={r} style={s} />
  if (theme === 'abstract')   return <polygon points={`${cx},${cy - r} ${cx + r * 0.9},${cy} ${cx},${cy + r} ${cx - r * 0.9},${cy}`} style={s} />
  return <circle cx={cx} cy={cy} r={r} style={s} />   // minimal
}

function Eyes({ style, cx, cy, r, fill, scale = 1.0, openness = 1.0 }) {
  const ex  = r * 0.32
  const ey  = cy - r * 0.18
  const scl = scale   // confidence-driven scale
  const yScale = openness  // emotion-driven openness (eye_openness param)

  if (style === 'visor') {
    const h = 11 * scl * yScale
    return <rect x={cx - r * 0.55} y={ey - h / 2} width={r * 1.1} height={h} rx={5} fill={fill} opacity={0.9} />
  }
  if (style === 'compound') {
    const cr = 4 * scl
    const dots  = [-12, -4, 4, 12].map(dx => <circle key={dx} cx={cx - ex + dx} cy={ey} r={cr} fill={fill} />)
    const dots2 = [-12, -4, 4, 12].map(dx => <circle key={dx} cx={cx + ex + dx} cy={ey} r={cr} fill={fill} />)
    return <>{dots}{dots2}</>
  }
  if (style === 'circular') {
    const er = 10 * scl
    return <>
      <circle cx={cx - ex} cy={ey} r={er} fill={fill} />
      <circle cx={cx + ex} cy={ey} r={er} fill={fill} />
      <circle cx={cx - ex + 3} cy={ey - 3} r={er * 0.4} fill="rgba(0,0,0,0.5)" />
      <circle cx={cx + ex + 3} cy={ey - 3} r={er * 0.4} fill="rgba(0,0,0,0.5)" />
    </>
  }
  // angular (default)
  const ew = 20 * scl
  const eh = Math.max(2, 12 * scl * yScale)
  return <>
    <rect x={cx - ex - ew / 2} y={ey - eh / 2} width={ew} height={eh} rx={2} fill={fill} />
    <rect x={cx + ex - ew / 2} y={ey - eh / 2} width={ew} height={eh} rx={2} fill={fill} />
  </>
}

function Mouth({ style, cx, cy, r, fill, curve = 0 }) {
  const my = cy + r * 0.32
  const mw = r * 0.55
  // curve: -1 (frown) to +1 (smile), applied as a vertical offset on the control point
  const curveY = curve * mw * 0.5

  if (style === 'aperture') {
    return <>
      <circle cx={cx} cy={my} r={mw * 0.5} stroke={fill} strokeWidth={2} fill="none" />
      <circle cx={cx} cy={my} r={mw * 0.28} fill={fill} opacity={0.6} />
    </>
  }
  if (style === 'segmented') {
    // Slight curve by vertically shifting middle segments
    return <>
      {[-3, -1, 1, 3].map((i, idx) => {
        const yOff = curve * (1 - Math.abs(i) / 3) * 4
        return <rect key={i} x={cx + i * 8 - 3} y={my - 4 + yOff} width={6} height={8} rx={1} fill={fill} />
      })}
    </>
  }
  if (style === 'wide') {
    return <path d={`M${cx - mw},${my} Q${cx},${my + mw * 0.4 + curveY} ${cx + mw},${my}`} stroke={fill} strokeWidth={3} fill="none" strokeLinecap="round" />
  }
  // thin (default)
  return <path d={`M${cx - mw * 0.6},${my} Q${cx},${my + mw * 0.25 + curveY} ${cx + mw * 0.6},${my}`} stroke={fill} strokeWidth={2.5} fill="none" strokeLinecap="round" />
}

export default function AvatarCanvas({ spec = {}, size = 200, animated = true, currentEmotion = null }) {
  const uid = useId().replace(/:/g, '')
  const s = { ...DEFAULTS, ...spec }
  const dna = { ...DNA_DEFAULTS, ...(s.dna || {}) }

  const cx = size / 2
  const cy = size / 2
  const r  = size * 0.36

  // DNA influence on rendering
  const eyeScale    = lerp(0.75, 1.25, dna.confidence)
  const glowOpacity = lerp(0.15, 0.45, dna.warmth)
  // Animation speed multiplier (lower energy = slower = longer duration)
  const animSpeed = lerp(0.4, 2.0, dna.energy)
  // Erraticness: mix flickering at high values
  const useFlicker = dna.erraticness > 0.65

  // Current emotion overrides (for live avatar response)
  const eyeOpenness = currentEmotion?.eye_openness ?? 1.0
  const mouthCurve  = currentEmotion?.mouth_curve  ?? 0.0

  // Per-animation base durations (in seconds), scaled by energy
  const dur = {
    breathing: (3.0 / animSpeed).toFixed(2),
    pulsing:   (2.0 / animSpeed).toFixed(2),
    flickering:(2.5 / animSpeed).toFixed(2),
    scanning:  (2.0 / animSpeed).toFixed(2),
  }

  const glowId   = `glow-${uid}`
  const idleAnim = useFlicker ? 'flickering' : s.idle_animation
  const animCls  = animated ? `anim-${idleAnim}` : ''
  const strokeClr = darken(s.color_primary)

  // Warmth: subtle amber tint overlay on the glow
  const warmOverlay = `rgba(251,191,36,${(dna.warmth * 0.25).toFixed(2)})`

  const animStyle = `
    @keyframes breathing {
      0%,100% { transform: scale(1);    }
      50%      { transform: scale(1.04); }
    }
    @keyframes pulsing {
      0%,100% { opacity: 0.7; }
      50%      { opacity: 1;   }
    }
    @keyframes flickering {
      0%,100% { opacity: 1;   }
      20%      { opacity: ${lerp(0.7, 0.3, dna.erraticness).toFixed(2)}; }
      40%      { opacity: 1;   }
      60%      { opacity: ${lerp(0.8, 0.4, dna.erraticness).toFixed(2)}; }
      80%      { opacity: 0.9; }
    }
    @keyframes glowPulse {
      0%,100% { r: ${r * 1.3}px; opacity: ${(glowOpacity * 0.6).toFixed(2)}; }
      50%      { r: ${r * 1.5}px; opacity: ${glowOpacity.toFixed(2)}; }
    }
    .anim-breathing  .face-group { animation: breathing  ${dur.breathing}s ease-in-out infinite; transform-origin: ${cx}px ${cy}px; }
    .anim-pulsing    .face-group { animation: pulsing    ${dur.pulsing}s ease-in-out infinite; }
    .anim-flickering .face-group { animation: flickering ${dur.flickering}s step-end infinite; }
    .glow-circle { animation: glowPulse ${idleAnim === 'scanning' ? (1.8 / animSpeed).toFixed(2) : (3.0 / animSpeed).toFixed(2)}s ease-in-out infinite; }
  `

  return (
    <svg viewBox={`0 0 ${size} ${size}`} width={size} height={size} className={animCls}>
      <style>{animStyle}</style>
      <defs>
        <filter id={glowId} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="8" result="blur" />
          <feMerge><feMergeNode in="blur" /><feMergeNode in="SourceGraphic" /></feMerge>
        </filter>
      </defs>

      {/* Ambient glow */}
      <circle className="glow-circle" cx={cx} cy={cy} r={r * 1.35} fill={s.color_secondary || s.color_primary} opacity={glowOpacity * 0.7} />
      {/* Warmth overlay on glow */}
      {dna.warmth > 0.3 && (
        <circle cx={cx} cy={cy} r={r * 1.2} fill={warmOverlay} />
      )}

      {/* Face */}
      <g className="face-group">
        <FaceShape theme={s.face_theme} cx={cx} cy={cy} r={r} fill={s.color_primary} stroke={strokeClr} />
        <Eyes
          style={s.eye_style}
          cx={cx} cy={cy} r={r}
          fill={s.color_accent}
          scale={eyeScale}
          openness={eyeOpenness}
        />
        <Mouth
          style={s.mouth_style}
          cx={cx} cy={cy} r={r}
          fill={s.color_accent}
          curve={mouthCurve}
        />
      </g>

      {/* Scanning sweep line */}
      {animated && idleAnim === 'scanning' && (
        <line x1={cx - r * 0.8} y1={cy} x2={cx + r * 0.8} y2={cy}
          stroke={s.color_accent} strokeWidth={1.5} opacity={0.5}
          strokeDasharray="4 6">
          <animate attributeName="y1" values={`${cy - r * 0.5};${cy + r * 0.5};${cy - r * 0.5}`} dur={`${dur.scanning}s`} repeatCount="indefinite" />
          <animate attributeName="y2" values={`${cy - r * 0.5};${cy + r * 0.5};${cy - r * 0.5}`} dur={`${dur.scanning}s`} repeatCount="indefinite" />
        </line>
      )}
    </svg>
  )
}
