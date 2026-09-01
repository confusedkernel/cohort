import { useCallback, useEffect, useState } from 'react'
import { acceptNode, attestNode, getAgent, getNode, rejectNode, reopenNode } from './api'
import { EDGE_STYLE, nodeTitle } from './graph-model'

export default function DetailPanel({ nodeId, onSelect, onClose, canWrite, onChanged }) {
  const [node, setNode] = useState(null)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    if (!nodeId) { setNode(null); return undefined }
    let live = true
    setError(null)
    getNode(nodeId)
      .then((d) => live && setNode(d))
      .catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [nodeId])

  useEffect(load, [load])

  if (!nodeId) {
    return (
      <aside className="panel empty">
        <p className="hint">Select a node to see its provenance — who wrote it, what
        attests it, how it was verified, and whether its support is independent.</p>
      </aside>
    )
  }
  if (error) {
    return (
      <aside className="panel">
        <CloseButton onClose={onClose} />
        <p className="error">{error}</p>
      </aside>
    )
  }
  if (!node) {
    return (
      <aside className="panel">
        <CloseButton onClose={onClose} />
        <p className="hint">Loading…</p>
      </aside>
    )
  }

  const support = node.independent_support

  return (
    <aside className="panel">
      <CloseButton onClose={onClose} />
      <header className="panel-head">
        <div className={`badge t-${node.type}`}>{node.type}</div>
        <div className={`badge s-${node.status}`}>{node.status}</div>
        {/* the level travels as a class too, so CSS can single out A0 —
            "nothing has been verified" is the one value not to skim past */}
        <div className={`badge assurance lvl-${node.assurance}`}>{node.assurance}</div>
      </header>

      <h2>{nodeTitle(node)}</h2>
      <code className="node-id">{node.id}</code>

      {canWrite && (
        <Verdict
          node={node}
          onDone={() => { load(); onChanged?.() }}
        />
      )}

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
                <span className={`badge assurance lvl-${v.payload.assurance_level}`}>
                  {v.payload.assurance_level}
                </span>
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
              <AuthorLink author={a.author} />
              <time>{a.at}</time>
            </li>
          ))}
        </ul>
      </Section>
    </aside>
  )
}

// An author's contribution history, one click from a node they wrote. The
// endpoint has always existed; nothing in the browser reached it until now.
//
// It is counts and never a score. A reputation number would reward volume, and
// an agent that proposes ten weak claims would outrank one that proposes a
// single good one — which is why docs/design.md §9 rules it out.
function AuthorLink({ author }) {
  const [report, setReport] = useState(null)
  const [open, setOpen] = useState(false)

  const toggle = () => {
    const next = !open
    setOpen(next)
    if (next && !report) getAgent(author).then(setReport).catch(() => setReport(false))
  }

  return (
    <span className="author-wrap">
      <button className={`author link ${open ? 'on' : ''}`} onClick={toggle} title="Contribution history">
        {author}
      </button>
      {open && (
        <span className="author-report">
          {report === false && <em>no report available</em>}
          {report === null && <em>loading…</em>}
          {report && (
            <>
              {Object.entries(report)
                .filter(([, v]) => typeof v === 'number')
                .map(([k, v]) => (
                  <span key={k}><b>{v}</b> {k.replace(/_/g, ' ')}</span>
                ))}
              <span className="hint small">counts, not a score</span>
            </>
          )}
        </span>
      )}
    </span>
  )
}

function CloseButton({ onClose }) {
  if (!onClose) return null
  return (
    <button className="panel-close" onClick={onClose} aria-label="Close inspector"
            title="Close (Esc)">
      ×
    </button>
  )
}

function EdgeList({ title, edges, field, onSelect }) {
  if (!edges?.length) return null
  return (
    <Section title={`${title} (${edges.length})`}>
      {edges.map((e) => (
        <div className={`edge-row ${e.discounts ? 'discount' : ''}`} key={e.id}>
          <div className="edge-line">
            <span className="edge-type">{EDGE_STYLE[e.type]?.label || e.type}</span>
            {e.discounts && <span className="chip">discounts</span>}
            <button onClick={() => onSelect(e[field])}>{short(e[field])}</button>
          </div>
          {/* A contradicts edge is drawn as heavily as evidence, so the grounds
              for it belong next to it — an unexplained disagreement asserted
              this prominently is worse than none. */}
          {e.reason && <p className="edge-reason">{e.reason}</p>}
        </div>
      ))}
    </Section>
  )
}

// The researcher's own actions. Deliberately the only writes in the UI, and
// only mounted when the server was started with --allow-writes: docs/design.md §8
// makes accept/reject the one thing agents may never do, so the interface for
// it should look like an authority being exercised, not a form being filled.
function Verdict({ node, onDone }) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [refusal, setRefusal] = useState(null)

  const act = async (fn, needsReason) => {
    if (needsReason && !reason.trim()) {
      // Mirrors MissingRejectionReason locally so the researcher gets the
      // answer immediately; the server enforces it regardless.
      setRefusal({ rule: 'MissingRejectionReason', message: 'a reason is required' })
      return
    }
    setBusy(true)
    setRefusal(null)
    try {
      await fn()
      setReason('')
      onDone()
    } catch (e) {
      setRefusal({ rule: e.rule, message: e.message, status: e.status })
    } finally {
      setBusy(false)
    }
  }

  const isRejected = node.status === 'rejected'
  const canAccept = node.status === 'attested'
  // A proposed node is one rung short, not a refusal. Telling the researcher
  // "only an attested node can be accepted" and stopping there was a dead end:
  // attestation is a mechanical check, not a judgement, so offer to run it.
  const canAttest = node.status === 'proposed'

  return (
    <section className="verdict">
      <h3>Researcher decision</h3>
      {!isRejected && (
        <p className="hint small">
          {canAccept
            ? 'Accepting makes this citable and usable as a premise by other agents.'
            : canAttest
              ? 'The ladder runs proposed → attested → accepted, and no rung may be '
                + 'skipped. Attesting is the mechanical check — do this node\u2019s '
                + 'citations resolve? — not a judgement about whether it is right. '
                + 'The graph refuses it if nothing attests this node.'
              : `Only an attested node can be accepted — this one is ${node.status}.`}
        </p>
      )}
      <textarea
        className="reason-input"
        placeholder={isRejected ? 'Why reopen it?' : 'Reason (required to reject)'}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        rows={2}
      />
      <div className="verdict-actions">
        {isRejected ? (
          <button
            className="btn reopen" disabled={busy}
            onClick={() => act(() => reopenNode(node.id, reason), true)}
          >Reopen</button>
        ) : (
          <>
            {canAttest && (
              <button
                className="btn attest" disabled={busy}
                onClick={() => act(() => attestNode(node.id), false)}
                title="Run the mechanical check: do this node's citations resolve?"
              >Attest</button>
            )}
            <button
              className="btn accept" disabled={busy || !canAccept}
              onClick={() => act(() => acceptNode(node.id), false)}
            >Accept</button>
            <button
              className="btn reject" disabled={busy}
              onClick={() => act(() => rejectNode(node.id, reason), true)}
            >Reject</button>
          </>
        )}
      </div>
      {refusal && (
        <div className={`refusal ${refusal.status === 409 ? 'conflict' : ''}`}>
          {refusal.rule && <strong>{refusal.rule}</strong>}
          <p>{refusal.message}</p>
          {refusal.status === 409 && (
            <p className="small">Single-writer discipline: nothing was changed.</p>
          )}
        </div>
      )}
    </section>
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
