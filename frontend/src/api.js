const BASE = '/agents'

export async function listAgents() {
  const r = await fetch(BASE)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function getAgent(id) {
  const r = await fetch(`${BASE}/${id}`)
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function createAgent(body) {
  const r = await fetch(BASE, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function updateAgent(id, body) {
  const r = await fetch(`${BASE}/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}

export async function deleteAgent(id) {
  const r = await fetch(`${BASE}/${id}`, { method: 'DELETE' })
  if (!r.ok) throw new Error(await r.text())
}
