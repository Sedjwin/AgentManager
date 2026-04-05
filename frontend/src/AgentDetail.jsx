import { useEffect, useMemo, useState } from 'react'
import {
  ChevronDown,
  ChevronRight,
  Edit2,
  Trash2,
  Mic,
  MicOff,
  User,
  Bot,
  History,
} from 'lucide-react'
import { getAgentSessionBrowser } from './api.js'

function Field({ label, children }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-1">{label}</div>
      <div className="text-sm text-gray-200">{children}</div>
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-5 space-y-4">
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">{title}</h3>
      {children}
    </div>
  )
}

function SessionUserGroup({ group, open, onToggle }) {
  return (
    <div className="border border-gray-800 rounded-xl overflow-hidden bg-gray-900/60">
      <button
        onClick={onToggle}
        className="w-full px-3 py-2.5 flex items-center justify-between gap-3 text-left hover:bg-gray-800/60 transition-colors"
      >
        <div className="min-w-0">
          <div className="text-sm font-medium text-gray-100 truncate">{group.username}</div>
          <div className="text-xs text-gray-500">{group.session_count} session{group.session_count === 1 ? '' : 's'}</div>
        </div>
        {open ? <ChevronDown className="w-4 h-4 text-gray-500" /> : <ChevronRight className="w-4 h-4 text-gray-500" />}
      </button>
      {open && (
        <div className="border-t border-gray-800">
          {group.sessions.map(session => <SessionRow key={session.session_id} session={session} />)}
        </div>
      )}
    </div>
  )
}

function SessionRow({ session }) {
  const timestamp = formatSessionTime(session.started_at)
  const titleClass = session.has_saved_title ? 'text-violet-300' : 'text-gray-200'

  return (
    <div className="px-3 py-3 border-t border-gray-800 first:border-t-0">
      <div className={`text-sm leading-snug ${titleClass}`}>{session.display_title}</div>
      <div className="mt-1 text-xs text-gray-500">{timestamp}</div>
      <div className="mt-1 text-[11px] text-gray-600 font-mono break-all">{session.session_id}</div>
    </div>
  )
}

function formatSessionTime(value) {
  if (!value) return 'Unknown time'
  const dt = new Date(value)
  if (Number.isNaN(dt.getTime())) return value
  return new Intl.DateTimeFormat(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(dt)
}

export default function AgentDetail({ agent, user, onEdit, onDelete }) {
  const profile = agent.profile
  const vc = agent.voice_config
  const enabledTools = agent.enabled_tools || []
  const [sessionGroups, setSessionGroups] = useState([])
  const [sessionsLoading, setSessionsLoading] = useState(true)
  const [sessionsError, setSessionsError] = useState(null)
  const [expandedUsers, setExpandedUsers] = useState({})

  useEffect(() => {
    let cancelled = false

    async function loadSessions() {
      setSessionsLoading(true)
      setSessionsError(null)
      try {
        const data = await getAgentSessionBrowser(agent.agent_id)
        if (cancelled) return
        setSessionGroups(data)
      } catch (error) {
        if (cancelled) return
        setSessionsError(error.message || 'Failed to load sessions')
        setSessionGroups([])
      } finally {
        if (!cancelled) setSessionsLoading(false)
      }
    }

    setExpandedUsers({})
    loadSessions()
    return () => { cancelled = true }
  }, [agent.agent_id])

  const visibleGroups = useMemo(() => {
    if (user?.role === 'admin') return sessionGroups
    return sessionGroups.filter(group => group.username === user?.username)
  }, [sessionGroups, user?.role, user?.username])

  useEffect(() => {
    if (visibleGroups.length !== 1) return
    const onlyUser = visibleGroups[0].username
    setExpandedUsers(current => current[onlyUser] ? current : { ...current, [onlyUser]: true })
  }, [visibleGroups])

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(320px,1fr)]">
      <div className="space-y-4">
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${
              profile ? 'bg-amber-500/20' : 'bg-gray-800'
            }`}>
              {profile ? <User className="w-5 h-5 text-amber-400" /> : <Bot className="w-5 h-5 text-gray-500" />}
            </div>
            <div>
              <h2 className="text-lg font-bold text-white">{agent.name}</h2>
              <div className="flex items-center gap-2 mt-0.5">
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  profile ? 'bg-amber-500/15 text-amber-400' : 'bg-gray-800 text-gray-500'
                }`}>
                  {profile ? 'Interaction Agent' : 'Functional Agent'}
                </span>
                {agent.voice_enabled
                  ? <span className="flex items-center gap-1 text-xs text-blue-400"><Mic className="w-3 h-3" /> Voice</span>
                  : <span className="flex items-center gap-1 text-xs text-gray-600"><MicOff className="w-3 h-3" /> No voice</span>
                }
                {agent.tool_use_enabled && (
                  <span className="text-xs px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-400">Tools</span>
                )}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onEdit}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-gray-800 hover:bg-gray-700 text-xs text-gray-300 transition-colors"
            >
              <Edit2 className="w-3.5 h-3.5" /> Edit
            </button>
            <button
              onClick={onDelete}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-950 hover:bg-red-900 text-xs text-red-400 transition-colors"
            >
              <Trash2 className="w-3.5 h-3.5" /> Delete
            </button>
          </div>
        </div>

        <Section title="System Prompt">
          <pre className="text-xs text-gray-300 whitespace-pre-wrap leading-relaxed font-sans">
            {agent.system_prompt || <span className="text-gray-600 italic">No system prompt</span>}
          </pre>
        </Section>

        {agent.voice_enabled && vc && (
          <Section title="Voice Configuration">
            <Field label="Voice">{vc.voice_id || '-'}</Field>
          </Section>
        )}

        {agent.tool_use_enabled && (
          <Section title="Tool Use">
            {enabledTools.length === 0
              ? <span className="text-xs text-gray-600 italic">Enabled but no tools selected</span>
              : <div className="flex flex-wrap gap-2">
                  {enabledTools.map(name => (
                    <span key={name} className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-violet-300 font-mono">
                      {name}
                    </span>
                  ))}
                </div>
            }
          </Section>
        )}

        {profile && (
          <>
            <Section title="Identity">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Display Name">{profile.display_name}</Field>
                <Field label="Tagline">{profile.tagline}</Field>
              </div>
            </Section>

            <Section title="Appearance">
              <div className="grid grid-cols-3 gap-3">
                {Object.entries(profile.appearance || {}).map(([k, v]) => (
                  typeof v === 'number' ? (
                    <div key={k}>
                      <div className="text-xs text-gray-600 mb-1">{k.replace(/_/g, ' ')}</div>
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-1.5 bg-gray-800 rounded-full">
                          <div className="h-1.5 bg-amber-500/60 rounded-full" style={{ width: `${Math.min(v * 100, 100)}%` }} />
                        </div>
                        <span className="text-xs text-gray-500 font-mono w-8 text-right">{v.toFixed(2)}</span>
                      </div>
                    </div>
                  ) : (
                    <div key={k}>
                      <div className="text-xs text-gray-600 mb-1">{k.replace(/_/g, ' ')}</div>
                      {typeof v === 'string' && v.startsWith('#')
                        ? <div className="flex items-center gap-2">
                            <div className="w-4 h-4 rounded border border-gray-700" style={{ background: v }} />
                            <span className="text-xs text-gray-400 font-mono">{v}</span>
                          </div>
                        : <span className="text-xs text-gray-400">{String(v)}</span>
                      }
                    </div>
                  )
                ))}
              </div>
            </Section>

            <Section title={`Emotions (${Object.keys(profile.emotions || {}).length})`}>
              <div className="flex flex-wrap gap-2">
                {Object.keys(profile.emotions || {}).map(name => (
                  <span key={name} className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-amber-300 font-mono">
                    {name}
                  </span>
                ))}
              </div>
            </Section>

            <Section title={`Actions (${Object.keys(profile.actions || {}).length})`}>
              <div className="flex flex-wrap gap-2">
                {Object.keys(profile.actions || {}).map(name => (
                  <span key={name} className="px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-blue-300 font-mono">
                    {name}
                  </span>
                ))}
              </div>
            </Section>
          </>
        )}

        <div className="text-xs text-gray-700 font-mono">
          ID: {agent.agent_id}
        </div>
      </div>

      <Section title="Sessions">
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <History className="w-3.5 h-3.5" />
          {user?.role === 'admin'
            ? 'Grouped by user'
            : `Showing ${user?.username || 'your'} sessions`}
        </div>

        {sessionsLoading && (
          <div className="text-sm text-gray-500">Loading sessions...</div>
        )}

        {!sessionsLoading && sessionsError && (
          <div className="text-sm text-red-300">{sessionsError}</div>
        )}

        {!sessionsLoading && !sessionsError && visibleGroups.length === 0 && (
          <div className="text-sm text-gray-500">No sessions found for this agent.</div>
        )}

        {!sessionsLoading && !sessionsError && visibleGroups.length > 0 && (
          <div className="space-y-3">
            {visibleGroups.map(group => (
              <SessionUserGroup
                key={group.username}
                group={group}
                open={!!expandedUsers[group.username]}
                onToggle={() => setExpandedUsers(current => ({
                  ...current,
                  [group.username]: !current[group.username],
                }))}
              />
            ))}
          </div>
        )}
      </Section>
    </div>
  )
}
