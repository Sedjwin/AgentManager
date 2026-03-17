import React, { useState, useRef } from 'react'
import { ArrowLeft, Send, Mic, MicOff, Volume2, VolumeX, Square } from 'lucide-react'
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
  if (typeof v === 'object') return v
  try { return JSON.parse(v) } catch { return {} }
}

function capitalize(s) {
  return s ? s.charAt(0).toUpperCase() + s.slice(1).toLowerCase() : ''
}

const EMOTION_COLOR = {
  HAPPY:     'text-yellow-400',
  EXCITED:   'text-orange-400',
  ANGRY:     'text-red-400',
  SAD:       'text-blue-400',
  CALM:      'text-teal-400',
  SARCASTIC: 'text-purple-400',
  CONFUSED:  'text-pink-400',
  NEUTRAL:   'text-gray-400',
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

export default function AgentChat({ agent, onBack }) {
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
  const [currentEmotion, setCurrentEmotion] = useState(null)

  const audioCtxRef   = useRef(null)
  const currentSrcRef = useRef(null)
  const mediaRecRef   = useRef(null)
  const chunksRef     = useRef([])
  const messagesRef   = useRef(null)
  const analyserRef   = useRef(null)
  const silenceRafRef = useRef(null)

  const spec     = safeJson(agent.avatar_spec)
  const emotions = safeJson(agent.emotions)

  // Adjust animation for current state
  const liveSpec = {
    ...spec,
    idle_animation:
      avatarState === 'processing' ? 'pulsing' :
      avatarState === 'speaking'   ? 'flickering' :
      spec.idle_animation,
  }

  // Mood word shown under avatar
  const moodWord = currentEmotion
    ? capitalize(currentEmotion)
    : capitalize(emotions[avatarState] || avatarState)

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
    setMessages(prev => { const n = [...prev, msg]; return n })
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
    setCurrentEmotion(data.emotion || null)
    addMsg({
      role: 'assistant',
      content: data.clean_text || '(no response)',
      emotion: data.emotion,
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

  return (
    <div className="min-h-screen p-6 flex flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 mb-6 shrink-0">
        <button onClick={onBack} className="flex items-center gap-2 text-gray-500 hover:text-white transition-colors text-sm">
          <ArrowLeft size={16} /> Agents
        </button>
        <span className="text-gray-700">/</span>
        <span className="text-white font-semibold">{agent.name}</span>
      </div>

      {/* Body */}
      <div className="flex gap-6 flex-1 min-h-0">

        {/* Left: avatar + controls */}
        <div className="w-48 shrink-0 flex flex-col gap-5">

          {showAvatar && (
            <div className="flex flex-col items-center gap-3">
              <AvatarCanvas spec={liveSpec} size={160} animated />

              {/* Current mood */}
              <div className="text-center">
                <p className={`text-base font-semibold tracking-wide ${EMOTION_COLOR[currentEmotion] ?? 'text-gray-300'}`}>
                  {moodWord}
                </p>
              </div>

              {/* Mood state map */}
              {Object.keys(emotions).length > 0 && (
                <div className="w-full text-xs font-mono space-y-1 border-t border-gray-800 pt-3">
                  {Object.entries(emotions).map(([state, word]) => (
                    <div
                      key={state}
                      className={`flex justify-between gap-2 transition-colors ${
                        avatarState === state ? 'text-amber-400' : 'text-gray-700'
                      }`}
                    >
                      <span className="capitalize">{state}</span>
                      <span className="text-right">{word}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="space-y-3 border-t border-gray-800 pt-4">
            <Toggle value={showAvatar}   onChange={setShowAvatar}   label="Avatar" />
            <Toggle value={wantVoice}    onChange={setWantVoice}    label="Voice output" />
            {wantVoice && (
              <Toggle value={wantVisemes} onChange={setWantVisemes} label="Visemes" />
            )}
          </div>

          {wantVoice && (
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
          )}
        </div>

        {/* Right: chat */}
        <div className="flex-1 min-w-0 flex flex-col gap-3">
          {/* Messages */}
          <div
            ref={messagesRef}
            className="flex-1 min-h-0 bg-gray-900 border border-gray-800 rounded-xl p-4 overflow-y-auto flex flex-col gap-2"
            style={{ height: 'calc(100vh - 200px)' }}
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
                  m.role === 'user'      ? 'bg-gray-800 text-gray-100' :
                  m.role === 'error'     ? 'bg-red-950 border border-red-800 text-red-300' :
                                           'bg-amber-950 border border-amber-900 text-amber-100'
                }`}>
                  {m.content}
                </div>
                {m.emotion && m.emotion !== 'NEUTRAL' && (
                  <span className={`text-xs mt-0.5 px-1 capitalize ${EMOTION_COLOR[m.emotion] ?? 'text-gray-500'}`}>
                    {m.emotion.toLowerCase()}
                  </span>
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
                {capitalize(emotions.processing || 'thinking')}…
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
