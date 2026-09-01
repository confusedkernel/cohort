import { useEffect, useState } from 'react'
import { getNode } from './api'
import { EDGE_STYLE, nodeTitle } from './graph-model'

export default function DetailPanel({ nodeId, onSelect }) {
  const [node, setNode] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!nodeId) { setNode(null); return }
    let live = true
    setError(null)
    getNode(nodeId)
      .then((d) => live && setNode(d))
      .catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [nodeId])

  if (!nodeId) {
    return (
      <aside className="panel empty">
        <p className="hint">Select a node to see its provenance — who wrote it, what
        attests it, how it was verified, and whether its support is independent.</p>
      </aside>
    )
  }
  if (error) return <aside className="panel"><p className="error">{error}</p></aside>
  if (!node) return <aside className="panel"><p className="hint">Loading…</p></aside>

  const support = node.independent_support

  return (
    <aside className="panel">
      <header className="panel-head">
        <div className={`badge t-${node.type}`}>{node.type}</div>
        <div className={`badge s-${node.status}`}>{node.status}</div>
        <div className="badge assurance">{node.assurance}</div>
      </header>

      <h2>{nodeTitle(node)}</h2>
      <code className="node-id">{node.id}</code>

      {node.rejected_reason && (
        <Section title="Rejected because">
          <p className="reason">{node.rejected_reason}</p>
        </Section>
      )}

      {support && (
        <Section title="Independent support">
          <div className={`support ${support.independent ? 'ok' : 'discounted'}`}>
            <div className="support-row">
              <span>attesting passages</span><strong>{support.attesting_count}</strong>
            </div>
            <div className="support-row">
              <span>distinct witnesses</span><strong>{support.distinct_witnesses}</strong>
            </div>
            <div className="support-row">
              <span>independent</span>
              <strong>{support.independent ? 'yes' : 'no'}</strong>
            </div>
          </div>
          {!support.independent && (
            <p className="note">
              Agreement here is evidence of shared transmission, not independent
              confirmation — the count above is unchanged, but these witnesses are
              related:
            </p>
          )}
          {support.non_independent_pairs.map(([a, b]) => (
            <div className="pair" key={`${a}|${b}`}>
              <button onClick={() => onSelect(a)}>{short(a)}</button>
              <span>↔</span>
              <button onClick={() => onSelect(b)}>{short(b)}</button>
            </div>
          ))}
        </Section>
      )}

      <Section title="Payload">
        <dl className="kv">
          {Object.entries(node.payload || {}).map(([k, v]) => (
            <div key={k}>
              <dt>{k}</dt>
              <dd>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd>
            </div>
          ))}
        </dl>
      </Section>

      {node.verifications?.length > 0 && (
        <Section title={`Verifications (${node.verifications.length})`}>
          {node.verifications.map((v) => (
            <div className={`verification r-${v.payload.result}`} key={v.id}>
              <div className="v-head">
                <strong>{v.payload.method}</strong>
                <span className={`badge r-${v.payload.result}`}>{v.payload.result}</span>
                <span className="badge assurance">{v.payload.assurance_level}</span>
              </div>
              <p>{v.payload.detail}</p>
              {v.payload.limitations && (
                <p className="limitations"><em>Limitations:</em> {v.payload.limitations}</p>
              )}
            </div>
          ))}
        </Section>
      )}

      <EdgeList title="Outgoing" edges={node.edges_out} field="dst" onSelect={onSelect} />
      <EdgeList title="Incoming" edges={node.edges_in} field="src" onSelect={onSelect} />

      <Section title="Authorship">
        <ul className="authorship">
          {node.authorship.map((a, i) => (
            <li key={i}>
              <span className="action">{a.action}</span>
              <span className="author">{a.author}</span>
              <time>{a.at}</time>
            </li>
          ))}
        </ul>
      </Section>
    </aside>
  )
}

function EdgeList({ title, edges, field, onSelect }) {
  if (!edges?.length) return null
  return (
    <Section title={`${title} (${edges.length})`}>
      {edges.map((e) => (
        <div className={`edge-row ${e.discounts ? 'discount' : ''}`} key={e.id}>
          <span className="edge-type">{EDGE_STYLE[e.type]?.label || e.type}</span>
          {e.discounts && <span className="chip">discounts</span>}
          <button onClick={() => onSelect(e[field])}>{short(e[field])}</button>
        </div>
      ))}
    </Section>
  )
}

function Section({ title, children }) {
  return (
    <section className="section">
      <h3>{title}</h3>
      {children}
    </section>
  )
}

const short = (id) => {
  const s = String(id)
  return s.length > 34 ? `${s.slice(0, 33)}…` : s
}
