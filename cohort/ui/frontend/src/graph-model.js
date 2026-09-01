// Layout and visual encoding.
//
// DESIGN.md §10 is explicit that a naive rendering of this graph "flattens
// exactly the epistemics that justify the system", so three things below are
// requirements rather than styling choices:
//
//   * node status is a visual channel, not a tooltip;
//   * `descends_from`/`parallel_of` are visually distinct from `attests`,
//     because they *discount* support rather than adding it;
//   * contradiction edges are as visible as agreement edges.
//
// The layout is a deterministic evidence chain — witness → passage →
// claim/conjecture — rather than a force simulation. A force blob would place
// the same graph differently on every load, which is a poor property for
// something a researcher is meant to read, cite and return to.

export const COLUMNS = [
  { key: 'witness', label: 'Witnesses', types: ['witness'] },
  { key: 'passage', label: 'Passages', types: ['passage'] },
  { key: 'assertion', label: 'Claims & conjectures', types: ['claim', 'conjecture'] },
  { key: 'audit', label: 'Queries & audit', types: ['query', 'verification', 'decision'] },
]

// Audit bookkeeping, not evidence (DESIGN.md §5 principle 6). Hidden by
// default so the evidence chain stays legible; never removed, because hiding
// verification permanently would overstate how checked the graph is.
export const AUDIT_TYPES = new Set(['verification', 'decision'])

export const STATUS_ORDER = ['proposed', 'attested', 'accepted', 'rejected']

export const EDGE_STYLE = {
  attests:      { klass: 'e-attests',      label: 'attests' },
  part_of:      { klass: 'e-structural',   label: 'part of' },
  verifies:     { klass: 'e-structural',   label: 'verifies' },
  searched_for: { klass: 'e-structural',   label: 'searched for' },
  tests:        { klass: 'e-tests',        label: 'tests' },
  supersedes:   { klass: 'e-structural',   label: 'supersedes' },
  quotes:       { klass: 'e-structural',   label: 'quotes' },
  contradicts:  { klass: 'e-contradicts',  label: 'contradicts' },
  parallel_of:  { klass: 'e-discount',     label: 'parallel of' },
  descends_from:{ klass: 'e-discount',     label: 'descends from' },
}

const NODE_W = 190
const NODE_H = 54
const COL_GAP = 250
const ROW_GAP = 74
const PAD_X = 40
const PAD_Y = 56

export function layout(nodes, { showAudit }) {
  const visible = nodes.filter((n) => showAudit || !AUDIT_TYPES.has(n.type))
  const columns = COLUMNS.map((col) => ({
    ...col,
    nodes: visible
      .filter((n) => col.types.includes(n.type))
      .sort((a, b) => a.created_seq - b.created_seq),
  })).filter((col) => col.nodes.length > 0)

  const positions = new Map()
  columns.forEach((col, ci) => {
    col.nodes.forEach((node, ri) => {
      positions.set(node.id, {
        x: PAD_X + ci * COL_GAP,
        y: PAD_Y + ri * ROW_GAP,
        w: NODE_W,
        h: NODE_H,
        node,
      })
    })
  })

  const width = PAD_X * 2 + Math.max(1, columns.length) * COL_GAP
  const rows = Math.max(1, ...columns.map((c) => c.nodes.length))
  const height = PAD_Y * 2 + rows * ROW_GAP
  return { columns, positions, width, height }
}

// A curve rather than a straight line: with columns, many edges share
// endpoints, and straight segments overlap into an unreadable bundle.
export function edgePath(from, to) {
  const x1 = from.x + from.w
  const y1 = from.y + from.h / 2
  const x2 = to.x
  const y2 = to.y + to.h / 2
  if (x2 < x1) {
    // a backward edge (e.g. passage -> witness): leave from the left side
    const bx1 = from.x
    const bx2 = to.x + to.w
    const mid = (bx1 + bx2) / 2
    return `M ${bx1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${bx2} ${y2}`
  }
  const mid = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${mid} ${y1}, ${mid} ${y2}, ${x2} ${y2}`
}

export function nodeTitle(node) {
  const p = node.payload || {}
  if (node.type === 'witness') return p.label || p.canonical_ref || node.id
  if (node.type === 'passage') return p.excerpt || p.canonical_ref || node.id
  if (node.type === 'verification') return `${p.method || 'verification'} · ${p.result || ''}`
  if (node.type === 'decision') return p.action || 'decision'
  return p.text || node.id
}
