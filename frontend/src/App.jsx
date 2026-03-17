import React, { useState } from 'react'
import AgentList   from './components/AgentList'
import AgentEditor from './components/AgentEditor'

export default function App() {
  // null = list, 'new' = create form, <id> = edit
  const [view, setView] = useState(null)

  if (view === null) {
    return (
      <AgentList
        onSelect={id => setView(id)}
        onCreate={() => setView('new')}
      />
    )
  }

  return (
    <AgentEditor
      agentId={view}
      onBack={() => setView(null)}
      onDeleted={() => setView(null)}
    />
  )
}
