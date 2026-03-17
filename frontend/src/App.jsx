import React, { useState } from 'react'
import AgentList   from './components/AgentList'
import AgentEditor from './components/AgentEditor'
import AgentChat   from './components/AgentChat'

export default function App() {
  // null = list, 'new' = create, <number> = edit
  const [view, setView]           = useState(null)
  const [chatAgent, setChatAgent] = useState(null)

  if (chatAgent) {
    return <AgentChat agent={chatAgent} onBack={() => setChatAgent(null)} />
  }

  if (view === null) {
    return (
      <AgentList
        onSelect={id => setView(id)}
        onCreate={() => setView('new')}
        onChat={agent => setChatAgent(agent)}
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
