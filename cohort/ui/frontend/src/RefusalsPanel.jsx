// The refused writes.
//
// This is an output surface, not a log viewer. docs/design.md §15 claims the
// system's "refusals are part of its scholarly output", and §5 principle 4
// makes the write boundary the thing that produces them — so a refusal shown
// here is the system declining to record something, with the name of the
// commitment that made it decline. That is the most distinctive thing COHORT
// does, and until this panel existed it was visible only in terminal output.
//
// Presented most-recent-first, because the useful question is almost always
// "what did the run I just watched refuse to do?".

const RULE_NOTE = {
  UnattestableClaim: 'A claim needs an attested passage behind it. Citation is the requirement, not a formality.',
  UnattestableConjecture: 'A conjecture needs a query that would refute it — the falsifiability gate.',
  PersistentRejection: 'A rejected node cannot be re-proposed. Reopening is a researcher action.',
  NotResearcher: 'Only the researcher may accept, reject or reopen.',
  MissingRejectionReason: 'Rejection requires a stated reason.',
  RungSkipped: 'The promotion ladder does not allow skipping a rung.',
  NodeNotFound: 'The write named a node that does not exist — usually an agent inventing an id.',
  EdgeDomainViolation: 'That edge type is not valid between those two node types.',
  EdgeEndpointMissing: 'An edge pointed at a node that does not exist.',
  EdgeSelfLoop: 'A node cannot be linked to itself.',
  SingleWriterViolation: 'Another process held the write lock.',
  PassageNotLocated: 'A passage must sit inside a witness.',
}

export default function RefusalsPanel({ refusals, closing }) {
  // `closing` is set while the panel is on its way out (see motion.js): the
  // pill that opens it is a toggle, and a toggled surface that vanishes on a
  // frame reads as a glitch rather than a dismissal.
  const cls = `refusals ${closing ? 'closing' : ''}`

  if (!refusals?.available) {
    return (
      <section className={cls}>
        <h2>Refused writes</h2>
        <p className="hint">
          No event log beside this projection, so refusals cannot be read. This
          is not the same as none having happened.
        </p>
      </section>
    )
  }

  const rows = [...refusals.refusals].reverse()
  const byRule = rows.reduce((acc, r) => ({ ...acc, [r.rule]: (acc[r.rule] || 0) + 1 }), {})

  return (
    <section className={cls}>
      <h2>
        Refused writes <span className="refusal-total">{refusals.total}</span>
      </h2>
      <p className="hint">
        Writes this graph declined, and the rule that declined each one. These
        are part of the record, not errors that were worked around.
      </p>

      {rows.length === 0 ? (
        <p className="hint">
          Nothing has been refused. That is a real result, not a missing one.
        </p>
      ) : (
        <>
          <div className="rule-tally">
            {Object.entries(byRule)
              .sort((a, b) => b[1] - a[1])
              .map(([rule, n]) => (
                <span className="rule-chip" key={rule}>
                  {rule} <strong>{n}</strong>
                </span>
              ))}
          </div>

          {refusals.truncated && (
            <p className="hint small">
              Showing the most recent {rows.length} of {refusals.total}.
            </p>
          )}

          <ul className="refusal-list">
            {rows.map((r) => (
              <li key={r.seq} className="refusal-item">
                <div className="refusal-head">
                  <span className="refusal-rule">{r.rule}</span>
                  <code className="refusal-attempted">{r.attempted}</code>
                  <span className="refusal-author">{r.authored_by}</span>
                  <time>{r.at}</time>
                </div>
                <p className="refusal-message">{r.message}</p>
                {RULE_NOTE[r.rule] && (
                  <p className="refusal-note">{RULE_NOTE[r.rule]}</p>
                )}
                <div className="refusal-meta">
                  {r.node_id && <code>{r.node_id}</code>}
                  {r.model_call_id !== null && r.model_call_id !== undefined && (
                    <span className="chip">model call #{r.model_call_id}</span>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
