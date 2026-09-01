import {
  COLUMNS,
  EDGE_STYLE,
  NODE_H,
  NODE_W,
  edgePath,
  fitText,
  layout,
  nodeTitle,
} from './graph-model'

export default function GraphView({ data, selectedId, onSelect, showAudit }) {
  const { columns, positions, width, height } = layout(data.nodes, { showAudit })

  const edges = data.edges.filter(
    (e) => positions.has(e.src) && positions.has(e.dst),
  )
  // `parallel_of` and `contradicts` are stored in both directions; drawing
  // both would double the visual weight of exactly the edges the design wants
  // read at their true strength.
  const seen = new Set()
  const drawn = edges.filter((e) => {
    const key = [e.type, ...[e.src, e.dst].sort()].join('\x00')
    if (seen.has(key)) return false
    seen.add(key)
    return true
  })

  const neighbours = new Set()
  if (selectedId) {
    drawn.forEach((e) => {
      if (e.src === selectedId) neighbours.add(e.dst)
      if (e.dst === selectedId) neighbours.add(e.src)
    })
  }

  return (
    <div className="graph-scroll">
      <svg width={width} height={height} className="graph" role="img" aria-label="Evidence graph">
        <defs>
          {['attests', 'discount', 'contradicts', 'structural', 'tests'].map((k) => (
            <marker
              key={k} id={`arrow-${k}`} viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="6" markerHeight="6" orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" className={`arrow a-${k}`} />
            </marker>
          ))}
          {/* The hard guarantee behind `fitText`'s estimate: label text can
              never paint outside its node box, whatever the font or script
              actually measures. Defined once at the node's own origin, which
              is where every node group's coordinates start. */}
          <clipPath id="node-clip">
            <rect width={NODE_W} height={NODE_H} rx="7" />
          </clipPath>
        </defs>

        {columns.map((col, ci) => {
          const first = col.nodes[0] && positions.get(col.nodes[0].id)
          return first ? (
            <text key={col.key} className="col-label" x={first.x} y={26}>
              {COLUMNS.find((c) => c.key === col.key)?.label}
            </text>
          ) : null
        })}

        <g className="edges">
          {drawn.map((e) => {
            const style = EDGE_STYLE[e.type] || EDGE_STYLE.part_of
            const dim = selectedId && e.src !== selectedId && e.dst !== selectedId
            const marker = style.klass.replace('e-', '')
            return (
              <path
                key={e.id}
                d={edgePath(positions.get(e.src), positions.get(e.dst))}
                className={`edge ${style.klass} ${dim ? 'dim' : ''}`}
                markerEnd={`url(#arrow-${marker})`}
              >
                <title>{style.label}{e.discounts ? ' — discounts support' : ''}</title>
              </path>
            )
          })}
        </g>

        <g className="nodes">
          {[...positions.values()].map(({ x, y, w, h, node }) => {
            const isSel = node.id === selectedId
            const dim = selectedId && !isSel && !neighbours.has(node.id)
            return (
              <g
                key={node.id}
                transform={`translate(${x},${y})`}
                className={`node n-${node.type} s-${node.status} ${isSel ? 'selected' : ''} ${dim ? 'dim' : ''}`}
                onClick={() => onSelect(node.id)}
                tabIndex={0}
                role="button"
                onKeyDown={(ev) => (ev.key === 'Enter' || ev.key === ' ') && onSelect(node.id)}
              >
                <rect width={w} height={h} rx="7" className="node-box" />
                <g clipPath="url(#node-clip)">
                  {/* status as a visual channel, not a tooltip (docs/design.md §10) */}
                  <rect width="5" height={h} rx="2" className="status-bar" />
                  <text className="node-type" x="14" y="19">{node.type}</text>
                  <text className="node-status" x={w - 12} y="19" textAnchor="end">
                    {node.status}
                  </text>
                  <text className="node-title" x="14" y="39">
                    {fitText(nodeTitle(node))}
                  </text>
                </g>
                <title>{`${node.type} · ${node.status} · ${node.assurance}\n${nodeTitle(node)}`}</title>
              </g>
            )
          })}
        </g>
      </svg>
    </div>
  )
}
