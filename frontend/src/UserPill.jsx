import { useState, useEffect, useRef } from 'react'
import { ChevronDown, LogOut } from 'lucide-react'

const ROLE_COLOUR = { admin: 'text-red-400', paid: 'text-amber-400', free: 'text-blue-400', demo: 'text-gray-400' }
const AVATAR_BG   = { admin: 'bg-red-600',   paid: 'bg-amber-500',   free: 'bg-blue-600',  demo: 'bg-gray-600'  }

export default function UserPill({ user, onLogout }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    function handle(e) { if (!ref.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  const label = user.display_name || user.username

  return (
    <div className="relative" ref={ref}>
      <button onClick={() => setOpen(o => !o)}
        className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 rounded-lg px-2.5 py-1.5 transition-colors">
        <div className={`w-5 h-5 rounded-full ${AVATAR_BG[user.role] ?? 'bg-gray-600'} flex items-center justify-center text-xs font-bold text-white shrink-0`}>
          {label[0].toUpperCase()}
        </div>
        <span className="text-xs font-medium text-gray-200 max-w-24 truncate">{label}</span>
        <ChevronDown size={12} className={`text-gray-500 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-56 bg-gray-900 border border-gray-700 rounded-xl shadow-2xl z-50 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800">
            <div className="flex items-center gap-3">
              <div className={`w-9 h-9 rounded-full ${AVATAR_BG[user.role] ?? 'bg-gray-600'} flex items-center justify-center text-sm font-bold text-white shrink-0`}>
                {label[0].toUpperCase()}
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium text-gray-100 truncate">{label}</div>
                {user.display_name && <div className="text-xs text-gray-500 truncate">@{user.username}</div>}
                <div className={`text-xs font-medium mt-0.5 ${ROLE_COLOUR[user.role] ?? 'text-gray-400'}`}>{user.role}</div>
              </div>
            </div>
          </div>
          <div className="py-1">
            <button onClick={() => { setOpen(false); onLogout() }}
              className="w-full flex items-center gap-2.5 px-4 py-2 text-sm text-gray-400 hover:text-red-400 hover:bg-gray-800 transition-colors">
              <LogOut size={14} /> Sign out
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
