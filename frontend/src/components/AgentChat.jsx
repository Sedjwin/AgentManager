import React, { useState, useRef, useEffect } from 'react'
import { ArrowLeft, Send, Mic, MicOff, Volume2, VolumeX, Square, ChevronDown } from 'lucide-react'
import AvatarCanvas from './AvatarCanvas'

const MIC_AVAILABLE = !!(navigator.mediaDevices?.getUserMedia)

async function b64ToAudioBuffer(b64, audioCtx) {
  const binary = atob(b64)
  const bytes = new Uint8Array(binary.length)
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i)
  return audioCtx.decodeAudioData(bytes.buffer)
}

function safeJson(v) {
  if (!v) return {}
  if (typeof v === 'object' && !Array.isArray(v)) return v
  try { return JSON.parse(v) } catch { return {} }
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : ''
}

const EMOTION_STYLES = {
  HAPPY:     'text-yellow-400 bg-yellow-400/15 border-yellow-500/30',
  EXCITED:   'text-orange-400 bg-orange-400/15 border-orange-500/30',
  ANGRY:     'text-red-400    bg-red-400/15    border-red-500/30',
  SAD:       'text-blue-400   bg-blue-400/15   border-blue-500/30',
  CALM:      'text-teal-400   bg-teal-400/15   border-teal-500/30',
  SARCASTIC: 'text-purple-400 bg-purple-400/15 border-purple-500/30',
  CONFUSED:  'text-pink-400   bg-pink-400/15   border-pink-500/30',
  NEUTRAL:   'text-gray-400   bg-gray-400/10   border-gray-600/30',
}

const ANIM_STATE_STYLE = {
  idle:       'bg-gray-600',
  processing: 'bg-amber-400 animate-pulse',
  speaking:   'bg-green-400 animate-pulse',
}

// Mini horizontal bar for a -1..1 or 0..1 param
function ParamBar({ value, min = 0, max = 1 }) {
  const pct = Math.round(((value - min) / (max - min)) * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1 bg-gray-800 rounded-full overflow-hidden">
        <div className="h-full bg-amber-500/70 rounded-full transition-all duration-300" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono text-gray-500 w-9 text-right shrink-0">
        {value >= 0 ? '+' : ''}{value.toFixed(2)}
      </span>
    </div>
  )
}

function Toggle({ value, onChange, label }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer">
      <button
        type="button"
        onClick={() => onChange(!value)}
        className={`relative w-8 h-4 rounded-full transition-colors shrink-0 ${value ? 'bg-amber-500' : 'bg-gray-700'}`}
      >
        <span className={`absolute top-0.5 left-0.5 w-3 h-3 rounded-full bg-white transition-transform ${value ? 'translate-x-4' : ''}`} />
      </button>
      <span className="text-xs text-gray-400">{label}</span>
    </label>
  )
}

export default function AgentChat({ agent: initialAgent, onBack }) {
  const [allAgents, setAllAgents]       = useState([initialAgent])
  const [agent, setAgent]               = useState(initialAgent)
  const [messages, setMessages]         = useState([])
  const [input, setInput]               = useState('')
  const [loading, setLoading]           = useState(false)
  const [wantVoice, setWantVoice]       = useState(true)
  const [wantVisemes, setWantVisemes]   = useState(true)
  const [showAvatar, setShowAvatar]     = useState(true)
  const [muted, setMuted]               = useState(false)
  const [playing, setPlaying]           = useState(false)
  const [recording, setRecording]       = useState(false)
  const [avatarState, setAvatarState]   = useState('idle')
  const [currentEmotion, setCurrentEmotion] = useState(null) // {name, params}
  const [lastStats, setLastStats]       = useState(null)

  const audioCtxRef   = useRef(null)
  const currentSrcRef = useRef(null)
  const mediaRecRef   = useRef(null)
  const chunksRef     = useRef([])
  const messagesRef   = useRef(null)
  const analyserRef   = useRef(null)
  const silenceRafRef = useRef(null)

  // Load full agent list for selector
  useEffect(() => {
    fetch('/agents')
      .then(r => r.json())
      .then(list => setAllAgents(list.filter(a => a.enabled && a.gateway_token)))
      .catch(() => {})
  }, [])

  const spec = safeJson(agent.avatar_spec)

  // Override idle_animation based on avatar state
  const liveSpec = {
    ...spec,
    idle_animation:
      avatarState === 'processing' ? 'pulsing' :
      avatarState === 'speaking'   ? 'flickering' :
      spec.idle_animation,
  }

  function switchAgent(newAgent) {
    if (newAgent.id === agent.id) return
    setAgent(newAgent)
    setMessages([])
    setCurrentEmotion(null)
    setAvatarState('idle')
    setLastStats(null)
    stopAudio()
  }

  function getAudioCtx() {
    if (!audioCtxRef.current || audioCtxRef.current.state === 'closed')
      audioCtxRef.current = new AudioContext({ sampleRate: 22050 })
    return audioCtxRef.current
  }

  function stopAudio() {
    try { currentSrcRef.current?.stop() } catch {}
    currentSrcRef.current = null
    setPlaying(false)
    setAvatarState('idle')
  }

  async function playAudio(b64) {
    if (muted || !b64) { setAvatarState('idle'); return }
    const ctx = getAudioCtx()
    try {
      if (ctx.state === 'suspended') await ctx.resume()
      const buffer = await b64ToAudioBuffer(b64, ctx)
      try { currentSrcRef.current?.stop() } catch {}
      const source = ctx.createBufferSource()
      source.buffer = buffer
      source.connect(ctx.destination)
      source.start()
      currentSrcRef.current = source
      setPlaying(true)
      setAvatarState('speaking')
      source.onended = () => {
        currentSrcRef.current = null
        setPlaying(false)
        setAvatarState('idle')
      }
    } catch {
      setAvatarState('idle')
    }
  }

  function scrollDown() {
    setTimeout(() => {
      if (messagesRef.current) messagesRef.current.scrollTop = messagesRef.current.scrollHeight
    }, 50)
  }

  function addMsg(msg) {
    setMessages(prev => [...prev, msg])
    scrollDown()
  }

  function historyPayload() {
    return JSON.stringify(
      messages
        .filter(m => m.role !== 'error')
        .map(m => ({ role: m.role, content: m.content }))
    )
  }

  async function afterResponse(data) {
    // emotion_params comes directly from orchestrator — use it
    if (data.emotion && data.emotion_params) {
      setCurrentEmotion({ name: data.emotion, params: data.emotion_params })
    } else {
      setCurrentEmotion(null)
    }
    if (data.stats) setLastStats(data.stats)

    addMsg({
      role: 'assistant',
      content: data.clean_text || '(no response)',
      emotion: data.emotion,
      actions: data.actions || [],
      stats: data.stats,
    })
    if (wantVoice && data.audio_b64) {
      await playAudio(data.audio_b64)
    } else {
      setAvatarState('idle')
    }
  }

  async function sendText(text) {
    if (!text.trim() || loading) return
    setInput('')
    addMsg({ role: 'user', content: text })
    setLoading(true)
    setAvatarState('processing')
    setCurrentEmotion(null)

    try {
      const fd = new FormData()
      fd.append('text', text)
      fd.append('history', historyPayload())
      const r = await fetch(`/agents/${agent.id}/chat`, { method: 'POST', body: fd })
      if (!r.ok) throw new Error(await r.text())
      await afterResponse(await r.json())
    } catch (e) {
      addMsg({ role: 'error', content: e.message })
      setAvatarState('idle')
    } finally {
      setLoading(false)
    }
  }

  async function sendVoiceBlob(blob) {
    if (loading) return
    setLoading(true)
    setAvatarState('processing')
    setCurrentEmotion(null)
    addMsg({ role: 'user', content: '🎤 …' })

    try {
      const fd = new FormData()
      fd.append('audio', blob, 'recording.webm')
      fd.append('history', historyPayload())
      const r = await fetch(`/agents/${agent.id}/chat`, { method: 'POST', body: fd })
      if (!r.ok) throw new Error(await r.text())
      const data = await r.json()
      if (data.transcript) {
        setMessages(prev => {
          const next = [...prev]
          for (let i = next.length - 1; i >= 0; i--)
            if (next[i].role === 'user') { next[i] = { ...next[i], content: `🎤 "${data.transcript}"` }; break }
          return next
        })
      }
      await afterResponse(data)
    } catch (e) {
      addMsg({ role: 'error', content: e.message })
      setAvatarState('idle')
    } finally {
      setLoading(false)
    }
  }

  function stopRecording() {
    if (silenceRafRef.current) { cancelAnimationFrame(silenceRafRef.current); silenceRafRef.current = null }
    analyserRef.current = null
    mediaRecRef.current?.stop()
    setRecording(false)
  }

  async function toggleRecord() {
    if (recording) { stopRecording(); return }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    chunksRef.current = []
    const mr = new MediaRecorder(stream)
    mr.ondataavailable = e => chunksRef.current.push(e.data)
    mr.onstop = () => {
      stream.getTracks().forEach(t => t.stop())
      sendVoiceBlob(new Blob(chunksRef.current, { type: 'audio/webm' }))
    }
    mr.start()
    mediaRecRef.current = mr
    setRecording(true)
    try {
      const silCtx = new AudioContext()
      const src = silCtx.createMediaStreamSource(stream)
      const an = silCtx.createAnalyser()
      an.fftSize = 512
      src.connect(an)
      analyserRef.current = an
      const buf = new Float32Array(an.fftSize)
      let silStart = null
      function check() {
        if (!analyserRef.current) return
        an.getFloatTimeDomainData(buf)
        const rms = Math.sqrt(buf.reduce((s, v) => s + v * v, 0) / buf.length)
        if (rms < 0.01) {
          if (!silStart) silStart = Date.now()
          else if (Date.now() - silStart >= 1800) { silCtx.close(); stopRecording(); return }
        } else { silStart = null }
        silenceRafRef.current = requestAnimationFrame(check)
      }
      silenceRafRef.current = requestAnimationFrame(check)
    } catch { /* silence detection unavailable */ }
  }

  const emotionStyle = EMOTION_STYLES[currentEmotion?.name?.toUpperCase()] ?? EMOTION_STYLES.NEUTRAL

  return (
    <div className="min-h-screen p-6 flex flex-col">
      {/* Header + agent selector */}
      <div className="flex items-center gap-3 mb-4 shrink-0 flex-wrap gap-y-2">
        <button onClick={onBack} className="flex items-center gap-2 text-gray-500 hover:text-white transition-colors text-sm shrink-0">
          <ArrowLeft size={16} /> Agents
        </button>
        <span className="text-gray-700">/</span>

        {/* Agent selector */}
        <div className="relative flex items-center gap-1">
          <select
            value={agent.id}
            onChange={e => {
              const a = allAgents.find(x => x.id === parseInt(e.target.value))
              if (a) switchAgent(a)
            }}
            className="appearance-none bg-gray-900 border border-gray-700 rounded-lg pl-3 pr-8 py-1.5
              text-sm text-white font-semibold focus:outline-none focus:border-amber-500 cursor-pointer"
          >
            {allAgents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
          </select>
          <ChevronDown size={12} className="absolute right-2 text-gray-500 pointer-events-none" />
        </div>

        {/* Status dot */}
        <div className="flex items-center gap-1.5 ml-1">
          <span className={`w-2 h-2 rounded-full ${ANIM_STATE_STYLE[avatarState]}`} />
          <span className="text-xs text-gray-500 capitalize">{avatarState}</span>
        </div>

        {agent.gateway_token && (
          <span className="text-xs text-gray-700 font-mono ml-auto truncate max-w-40" title={agent.gateway_token}>
            gw: {agent.gateway_token.substring(0, 12)}…
          </span>
        )}
      </div>

      {/* Body */}
      <div className="flex gap-4 flex-1 min-h-0">

        {/* Left: avatar + data panel */}
        {showAvatar && (
          <div className="w-52 shrink-0 flex flex-col gap-3 overflow-y-auto" style={{ maxHeight: 'calc(100vh - 140px)' }}>

            {/* Avatar */}
            <div className="flex flex-col items-center gap-2">
              <AvatarCanvas spec={liveSpec} size={176} animated currentEmotion={currentEmotion?.params ?? null} />

              {/* Emotion badge */}
              {currentEmotion?.name ? (
                <span className={`text-xs px-2 py-0.5 rounded-full border font-medium tracking-wide ${emotionStyle}`}>
                  {currentEmotion.name.toUpperCase()}
                </span>
              ) : (
                <span className="text-xs text-gray-600 capitalize">{avatarState}</span>
              )}
            </div>

            {/* Emotion params — live data from orchestrator */}
            {currentEmotion?.params && (
              <div className="w-full border border-gray-800 rounded-lg p-3 bg-gray-900/40">
                <p className="text-xs text-gray-600 uppercase tracking-wider mb-2">State params</p>
                <div className="space-y-2">
                  {[
                    { key: 'energy',       label: 'Energy',     min: 0,  max: 1  },
                    { key: 'valence',      label: 'Mood',       min: -1, max: 1  },
                    { key: 'eye_openness', label: 'Eyes',       min: 0,  max: 1  },
                    { key: 'mouth_curve',  label: 'Expression', min: -1, max: 1  },
                  ].map(({ key, label, min, max }) => {
                    const v = currentEmotion.params[key] ?? 0
                    return (
                      <div key={key}>
                        <span className="text-xs text-gray-600">{label}</span>
                        <ParamBar value={v} min={min} max={max} />
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Last response stats */}
            {lastStats && (
              <div className="w-full border border-gray-800 rounded-lg p-3 bg-gray-900/40">
                <p className="text-xs text-gray-600 uppercase tracking-wider mb-2">Last response</p>
                <div className="space-y-1 text-xs">
                  <StatRow label="LLM" value={`${lastStats.t_llm_ms}ms`} />
                  {lastStats.t_tts_ms > 0 && <StatRow label="TTS" value={`${lastStats.t_tts_ms}ms`} />}
                  {lastStats.t_stt_ms > 0 && <StatRow label="STT" value={`${lastStats.t_stt_ms}ms`} />}
                  {lastStats.model_used && (
                    <StatRow
                      label="Model"
                      value={lastStats.model_used.split('/').pop().replace(/:.*/, '').substring(0, 18)}
                      mono
                    />
                  )}
                  {lastStats.completion_tokens > 0 && (
                    <StatRow label="Tokens" value={`${lastStats.prompt_tokens}↑ ${lastStats.completion_tokens}↓`} />
                  )}
                  {lastStats.audio_duration_ms > 0 && (
                    <StatRow label="Audio" value={`${(lastStats.audio_duration_ms / 1000).toFixed(1)}s`} />
                  )}
                </div>
              </div>
            )}

            {/* Controls */}
            <div className="border-t border-gray-800 pt-3 space-y-2.5">
              <Toggle value={wantVoice}  onChange={setWantVoice}  label="Voice output" />
              {wantVoice && (
                <Toggle value={wantVisemes} onChange={setWantVisemes} label="Visemes" />
              )}
            </div>

            <div className="space-y-2">
              <button
                onClick={() => setMuted(m => !m)}
                className={`flex items-center gap-2 text-xs transition-colors ${muted ? 'text-red-400' : 'text-gray-500 hover:text-gray-300'}`}
              >
                {muted ? <VolumeX size={13} /> : <Volume2 size={13} />}
                {muted ? 'Muted' : 'Audio on'}
              </button>
              {playing && (
                <button onClick={stopAudio} className="flex items-center gap-1.5 text-xs text-red-400 hover:text-red-300 transition-colors">
                  <Square size={12} /> Stop
                </button>
              )}
            </div>
          </div>
        )}

        {/* Right: chat */}
        <div className="flex-1 min-w-0 flex flex-col gap-3">
          {/* Show/hide avatar toggle when hidden */}
          {!showAvatar && (
            <button
              onClick={() => setShowAvatar(true)}
              className="self-start text-xs text-gray-600 hover:text-gray-400 transition-colors"
            >
              Show avatar
            </button>
          )}
          {showAvatar && (
            <button
              onClick={() => setShowAvatar(false)}
              className="self-start text-xs text-gray-700 hover:text-gray-500 transition-colors"
            >
              Hide avatar
            </button>
          )}

          {/* Messages */}
          <div
            ref={messagesRef}
            className="flex-1 min-h-0 bg-gray-900 border border-gray-800 rounded-xl p-4 overflow-y-auto flex flex-col gap-2"
            style={{ height: 'calc(100vh - 220px)' }}
          >
            {messages.length === 0 && (
              <p className="text-gray-600 text-sm m-auto text-center">
                Start a conversation with {agent.name}…
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`flex flex-col max-w-[80%] ${m.role === 'user' ? 'self-end items-end' : 'self-start items-start'}`}
              >
                <div className={`rounded-lg px-3 py-2 text-sm whitespace-pre-wrap ${
                  m.role === 'user'  ? 'bg-gray-800 text-gray-100' :
                  m.role === 'error' ? 'bg-red-950 border border-red-800 text-red-300' :
                                       'bg-amber-950 border border-amber-900 text-amber-100'
                }`}>
                  {m.content}
                </div>

                {/* Emotion + action badges under message */}
                {(m.emotion || (m.actions && m.actions.length > 0)) && (
                  <div className="flex gap-1.5 flex-wrap mt-0.5 px-1">
                    {m.emotion && m.emotion !== 'NEUTRAL' && (
                      <span className={`text-xs px-1.5 py-0.5 rounded border ${EMOTION_STYLES[m.emotion.toUpperCase()] ?? EMOTION_STYLES.NEUTRAL}`}>
                        {m.emotion.toLowerCase()}
                      </span>
                    )}
                    {m.actions?.map(a => (
                      <span key={a} className="text-xs text-gray-600 font-mono">[{a}]</span>
                    ))}
                  </div>
                )}

                {m.stats && (
                  <span className="text-xs text-gray-700 mt-0.5 px-1 font-mono">
                    {m.stats.t_llm_ms}ms
                    {m.stats.model_used && ` · ${m.stats.model_used.split('/').pop().replace(/:.*/, '')}`}
                  </span>
                )}
              </div>
            ))}

            {loading && (
              <div className="self-start flex items-center gap-2 text-amber-500 text-xs animate-pulse">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />
                Thinking…
              </div>
            )}
          </div>

          {/* Input */}
          <form onSubmit={e => { e.preventDefault(); sendText(input) }} className="flex gap-2 shrink-0">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={`Message ${agent.name}…`}
              disabled={loading}
              className="flex-1 bg-gray-800 border border-gray-700 rounded-lg px-4 py-2 text-sm text-white placeholder-gray-600 focus:outline-none focus:border-amber-500 disabled:opacity-50"
            />
            {MIC_AVAILABLE && (
              <button
                type="button"
                onClick={toggleRecord}
                disabled={loading && !recording}
                title={recording ? 'Stop recording' : 'Voice input'}
                className={`p-2 rounded-lg transition-colors disabled:opacity-50 ${
                  recording ? 'bg-red-600 hover:bg-red-700 text-white animate-pulse' : 'bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white'
                }`}
              >
                {recording ? <MicOff size={16} /> : <Mic size={16} />}
              </button>
            )}
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="bg-amber-600 hover:bg-amber-500 disabled:opacity-40 text-white px-4 py-2 rounded-lg transition-colors"
            >
              <Send size={16} />
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}

function StatRow({ label, value, mono }) {
  return (
    <div className="flex justify-between gap-2 text-gray-600">
      <span>{label}</span>
      <span className={`${mono ? 'font-mono text-gray-500' : ''} text-right truncate max-w-28`}>{value}</span>
    </div>
  )
}
