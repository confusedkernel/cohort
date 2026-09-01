// Node and agent ids are opaque and routinely contain `#` (a passage's ref is
// `{witness}#{excerpt}`), so they travel as encoded query parameters, never as
// path segments — see cohort/ui/api.py's `/api/node` docstring.
const json = async (url, options) => {
  const res = await fetch(url, options)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const detail = body.detail
    // A refused write answers with {rule, message}: the rule is the whole
    // point (it names the commitment that declined), so it must survive into
    // the message the researcher reads rather than being flattened to a code.
    const err = new Error(
      typeof detail === 'object' && detail !== null
        ? `${detail.rule}: ${detail.message}`
        : detail || `${res.status} ${res.statusText}`,
    )
    err.status = res.status
    err.rule = typeof detail === 'object' && detail !== null ? detail.rule : null
    throw err
  }
  return res.json()
}

export const getHealth = () => json('/api/health')
export const getGraph = (limit = 500) => json(`/api/graph?limit=${limit}`)
export const getNode = (id) => json(`/api/node?id=${encodeURIComponent(id)}`)
export const getAgent = (id) => json(`/api/agent?id=${encodeURIComponent(id)}`)
export const getRefusals = (limit = 100) => json(`/api/refusals?limit=${limit}`)

const post = (path, id, body) =>
  json(`${path}?id=${encodeURIComponent(id)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  })

export const acceptNode = (id) => post('/api/accept', id)
export const rejectNode = (id, reason) => post('/api/reject', id, { reason })
export const reopenNode = (id, reason) => post('/api/reopen', id, { reason })
