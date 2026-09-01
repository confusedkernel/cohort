// Node and agent ids are opaque and routinely contain `#` (a passage's ref is
// `{witness}#{excerpt}`), so they travel as encoded query parameters, never as
// path segments — see cohort/ui/api.py's `/api/node` docstring.
const json = async (url) => {
  const res = await fetch(url)
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}))
    throw new Error(detail.detail || `${res.status} ${res.statusText}`)
  }
  return res.json()
}

export const getHealth = () => json('/api/health')
export const getGraph = (limit = 500) => json(`/api/graph?limit=${limit}`)
export const getNode = (id) => json(`/api/node?id=${encodeURIComponent(id)}`)
export const getAgent = (id) => json(`/api/agent?id=${encodeURIComponent(id)}`)
