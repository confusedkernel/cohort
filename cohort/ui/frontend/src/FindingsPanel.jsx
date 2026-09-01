import { useCallback, useEffect, useState } from 'react'
import { getCitable, getIntegrity, getRebuild, getRejected } from './api'

// The researcher's output view, and the graph's self-checks.
//
// These four capabilities existed in the Python API and in the HTTP API but
// were unreachable from the browser, which broke the parity promise
// (tests/test_parity.py now fails if that happens again).
//
// Citable and rejected belong side by side deliberately. Only accepted nodes
// may be cited, and rejections-with-reasons are part of the scholarly output
// rather than a failure list (docs/design.md §8) — showing findings without
// showing what was thrown out and why would misrepresent the record.
//
// The two integrity checks are on demand, not ambient: `verify_integrity`'s
// own contract is that one tampered row must not turn every future read into
// a crash, so nothing here runs on a timer.

export default function FindingsPanel({ onSelect }) {
  const [citable, setCitable] = useState(null)
  const [rejected, setRejected] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let live = true
    Promise.all([getCitable(), getRejected()])
      .then(([c, r]) => { if (live) { setCitable(c); setRejected(r) } })
      .catch((e) => live && setError(e.message))
    return () => { live = false }
  }, [])

  if (error) return <section className="findings"><p className="error">{error}</p></section>

  return (
    <section className="findings">
      <IntegrityStrip />

      <div className="findings-cols">
        <div>
          <h2>Citable</h2>
          <p className="hint small">
            Accepted nodes. The only ones output may cite, and the only ones
            another agent may build on.
          </p>
          <NodeList
            nodes={citable}
            onSelect={onSelect}
            empty="Nothing is citable yet — only accepted nodes are, and none are accepted."
          />
        </div>

        <div>
          <h2>Rejected</h2>
          <p className="hint small">
            Thrown out, with the reason. Part of the record, not a failure list —
            and a rejected node cannot be re-proposed.
          </p>
          <NodeList
            nodes={rejected}
            onSelect={onSelect}
            reason
            empty="Nothing has been rejected."
          />
        </div>
      </div>
    </section>
  )
}

function NodeList({ nodes, onSelect, reason, empty }) {
  if (!nodes) return <p className="hint">Loading…</p>
  if (!nodes.length) return <p className="hint small">{empty}</p>
  return (
    <ul className="finding-list">
      {nodes.map((n) => (
        <li key={n.id}>
          <button className="finding-row" onClick={() => onSelect(n.id)}>
            <span className={`badge t-${n.type}`}>{n.type}</span>
            <code>{n.id}</code>
          </button>
          {reason && (
            <p className="finding-reason">
              {n.rejected_reason || <em>no reason recorded</em>}
            </p>
          )}
        </li>
      ))}
    </ul>
  )
}

function IntegrityStrip() {
  const [rebuild, setRebuild] = useState(null)
  const [integrity, setIntegrity] = useState(null)
  const [busy, setBusy] = useState(false)

  const check = useCallback(() => {
    setBusy(true)
    Promise.all([getRebuild(), getIntegrity()])
      .then(([rb, ig]) => { setRebuild(rb); setIntegrity(ig) })
      .catch(() => { setRebuild(null); setIntegrity(null) })
      .finally(() => setBusy(false))
  }, [])

  useEffect(check, [check])

  return (
    <div className="integrity">
      <div className="integrity-head">
        <h2>Integrity</h2>
        <button className="btn" onClick={check} disabled={busy}>
          {busy ? 'Checking…' : 'Re-check'}
        </button>
      </div>

      <div className="integrity-rows">
        <Check
          label="Rebuild from the log"
          detail={
            rebuild == null ? 'not run'
              : !rebuild.available ? 'no event log beside this projection'
                : rebuild.ok
                  ? `replayed ${rebuild.events_replayed} events to ${rebuild.nodes} nodes / ${rebuild.edges} edges, matching`
                  : 'the projection disagrees with the log'
          }
          state={rebuild == null || !rebuild.available ? 'unknown' : rebuild.ok ? 'pass' : 'fail'}
        />
        <Check
          label="Payload hashes"
          detail={
            integrity == null ? 'not run'
              : `${integrity.checked} checked · ${integrity.mismatched.length} mismatched · ${integrity.unhashed.length} unhashed`
          }
          state={
            integrity == null ? 'unknown'
              : integrity.mismatched.length ? 'fail' : 'pass'
          }
        />
      </div>

      {rebuild && rebuild.available && !rebuild.ok && (
        <pre className="integrity-diff">{rebuild.mismatch}</pre>
      )}

      <p className="hint small">
        The event log is ground truth and this database is a projection of it, so
        a mismatch means the database is wrong — not the log.
      </p>
    </div>
  )
}

function Check({ label, detail, state }) {
  return (
    <div className={`integrity-row r-${state}`}>
      <span className={`badge r-${state}`}>
        {state === 'pass' ? 'pass' : state === 'fail' ? 'fail' : '—'}
      </span>
      <span className="integrity-label">{label}</span>
      <span className="integrity-detail">{detail}</span>
    </div>
  )
}
