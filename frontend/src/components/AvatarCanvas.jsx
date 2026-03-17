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
}

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

function FaceShape({ theme, cx, cy, r, fill, stroke }) {
  const s = { fill, stroke, strokeWidth: 2 }
  if (theme === 'mechanical') return <polygon points={hexPoints(cx, cy, r)} style={s} />
  if (theme === 'organic')    return <ellipse cx={cx} cy={cy} rx={r * 0.88} ry={r} style={s} />
  if (theme === 'abstract')   return <polygon points={`${cx},${cy - r} ${cx + r * 0.9},${cy} ${cx},${cy + r} ${cx - r * 0.9},${cy}`} style={s} />
  return <circle cx={cx} cy={cy} r={r} style={s} />   // minimal
}

function Eyes({ style, cx, cy, r, fill }) {
  const ex = r * 0.32
  const ey = cy - r * 0.18
  if (style === 'visor') {
    return <rect x={cx - r * 0.55} y={ey - 6} width={r * 1.1} height={11} rx={5} fill={fill} opacity={0.9} />
  }
  if (style === 'compound') {
    const dots = [-12, -4, 4, 12].map(dx => <circle key={dx} cx={cx - ex + dx} cy={ey} r={4} fill={fill} />)
    const dots2 = [-12, -4, 4, 12].map(dx => <circle key={dx} cx={cx + ex + dx} cy={ey} r={4} fill={fill} />)
    return <>{dots}{dots2}</>
  }
  if (style === 'circular') {
    return <>
      <circle cx={cx - ex} cy={ey} r={10} fill={fill} />
      <circle cx={cx + ex} cy={ey} r={10} fill={fill} />
      <circle cx={cx - ex + 3} cy={ey - 3} r={4} fill="rgba(0,0,0,0.5)" />
      <circle cx={cx + ex + 3} cy={ey - 3} r={4} fill="rgba(0,0,0,0.5)" />
    </>
  }
  // angular (default)
  return <>
    <rect x={cx - ex - 10} y={ey - 7} width={20} height={12} rx={2} fill={fill} />
    <rect x={cx + ex - 10} y={ey - 7} width={20} height={12} rx={2} fill={fill} />
  </>
}

function Mouth({ style, cx, cy, r, fill }) {
  const my = cy + r * 0.32
  const mw = r * 0.55
  if (style === 'aperture') {
    return <>
      <circle cx={cx} cy={my} r={mw * 0.5} stroke={fill} strokeWidth={2} fill="none" />
      <circle cx={cx} cy={my} r={mw * 0.28} fill={fill} opacity={0.6} />
    </>
  }
  if (style === 'segmented') {
    return <>
      {[-3, -1, 1, 3].map(i => (
        <rect key={i} x={cx + i * 8 - 3} y={my - 4} width={6} height={8} rx={1} fill={fill} />
      ))}
    </>
  }
  if (style === 'wide') {
    return <path d={`M${cx - mw},${my} Q${cx},${my + mw * 0.5} ${cx + mw},${my}`} stroke={fill} strokeWidth={3} fill="none" strokeLinecap="round" />
  }
  // thin (default)
  return <path d={`M${cx - mw * 0.6},${my} Q${cx},${my + mw * 0.2} ${cx + mw * 0.6},${my}`} stroke={fill} strokeWidth={2.5} fill="none" strokeLinecap="round" />
}

export default function AvatarCanvas({ spec = {}, size = 200, animated = true }) {
  const uid = useId().replace(/:/g, '')
  const s = { ...DEFAULTS, ...spec }
  const cx = size / 2
  const cy = size / 2
  const r  = size * 0.36

  const glowId   = `glow-${uid}`
  const animCls  = animated ? `anim-${s.idle_animation}` : ''
  const strokeClr = darken(s.color_primary)

  const animStyle = `
    @keyframes breathing {
      0%,100% { transform: scale(1);       }
      50%      { transform: scale(1.04);    }
    }
    @keyframes pulsing {
      0%,100% { opacity: 0.7; }
      50%      { opacity: 1;   }
    }
    @keyframes flickering {
      0%,100% { opacity: 1;   }
      20%      { opacity: 0.8; }
      40%      { opacity: 1;   }
      60%      { opacity: 0.7; }
      80%      { opacity: 0.9; }
    }
    @keyframes glowPulse {
      0%,100% { r: ${r * 1.3}px; opacity: 0.25; }
      50%      { r: ${r * 1.5}px; opacity: 0.45; }
    }
    .anim-breathing .face-group { animation: breathing 3s ease-in-out infinite; transform-origin: ${cx}px ${cy}px; }
    .anim-pulsing   .face-group { animation: pulsing   2s ease-in-out infinite; }
    .anim-flickering .face-group { animation: flickering 2.5s step-end infinite; }
    .glow-circle { animation: glowPulse ${s.idle_animation === 'scanning' ? '1.8s' : '3s'} ease-in-out infinite; }
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
      <circle className="glow-circle" cx={cx} cy={cy} r={r * 1.35} fill={s.color_secondary || s.color_primary} opacity={0.3} />

      {/* Face */}
      <g className="face-group">
        <FaceShape theme={s.face_theme} cx={cx} cy={cy} r={r} fill={s.color_primary} stroke={strokeClr} />
        <Eyes   style={s.eye_style}   cx={cx} cy={cy} r={r} fill={s.color_accent} />
        <Mouth  style={s.mouth_style} cx={cx} cy={cy} r={r} fill={s.color_accent} />
      </g>

      {/* Scanning sweep line */}
      {animated && s.idle_animation === 'scanning' && (
        <line x1={cx - r * 0.8} y1={cy} x2={cx + r * 0.8} y2={cy}
          stroke={s.color_accent} strokeWidth={1.5} opacity={0.5}
          strokeDasharray="4 6">
          <animate attributeName="y1" values={`${cy - r * 0.5};${cy + r * 0.5};${cy - r * 0.5}`} dur="2s" repeatCount="indefinite" />
          <animate attributeName="y2" values={`${cy - r * 0.5};${cy + r * 0.5};${cy - r * 0.5}`} dur="2s" repeatCount="indefinite" />
        </line>
      )}
    </svg>
  )
}
