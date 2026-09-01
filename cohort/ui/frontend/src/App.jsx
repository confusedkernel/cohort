import { useEffect, useState } from 'react'
import { getGraph, getHealth } from './api'
import DetailPanel from './DetailPanel'
import GraphView from './GraphView'
import { EDGE_STYLE } from './graph-model'

export default function App() {
  const [data, setData] = useState(null)
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [showAudit, setShowAudit] = useState(false)

  useEffect(() => {
    Promise.all([getGraph(), getHealth()])
      .then(([g, h]) => { setData(g); setHealth(h) })
      .catch((e) => setError(e.message))
  }, [])

  if (error) {
    return (
      <div className="boot error">
        <h1>COHORT</h1>
        <p>{error}</p>
        <p className="hint">
          Seed a graph with <code>scripts/seed_demo_graph.py</code>, then serve it
          with <code>scripts/serve_ui.py</code>.
        </p>
      </div>
    )
  }
  if (!data) return <div className="boot"><h1>COHORT</h1><p className="hint">Loading…</p></div>

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <h1>COHORT</h1>
          <span className="tag">evidence graph · read-only</span>
        </div>
        <div className="counts">
          {health && Object.entries(health.nodes).map(([type, n]) => (
            <span key={type} className="count"><strong>{n}</strong> {type}</span>
          ))}
          <span className="count"><strong>{health?.edges}</strong> edges</span>
        </div>
        <label className="toggle">
          <input
            type="checkbox"
            checked={showAudit}
            onChange={(e) => setShowAudit(e.target.checked)}
          />
          show audit nodes
        </label>
      </header>

      {data.truncated && (
        <div className="banner">
          This view is truncated — some nodes are not shown, so the support
          visible here is not the whole graph.
        </div>
      )}

      <div className="body">
        <main>
          <Legend />
          <GraphView
            data={data}
            selectedId={selectedId}
            onSelect={setSelectedId}
            showAudit={showAudit}
          />
        </main>
        <DetailPanel nodeId={selectedId} onSelect={setSelectedId} />
      </div>
    </div>
  )
}

function Legend() {
  // The discounting edges are called out in words, not only by colour: that
  // agreement between related witnesses is *weaker* evidence is the system's
  // central argument, and a legend that leaves it to be inferred from a dash
  // pattern is doing the reader no favours.
  return (
    <div className="legend">
      <span className="li"><i className="swatch e-attests" /> attests — adds support</span>
      <span className="li"><i className="swatch e-discount" /> parallel of / descends from — <b>discounts</b> support</span>
      <span className="li"><i className="swatch e-contradicts" /> contradicts</span>
      <span className="li"><i className="swatch e-structural" /> structural</span>
      <span className="sep" />
      {['proposed', 'attested', 'accepted', 'rejected'].map((s) => (
        <span className="li" key={s}><i className={`dot s-${s}`} /> {s}</span>
      ))}
    </div>
  )
}
