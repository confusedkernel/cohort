import { useCallback, useEffect, useRef, useState } from 'react'
import { getRunConfig, getRuns, startRun, stopRun } from './api'

// Starting an agent run from the browser.
//
// This is the only part of the UI that spends money, and the design follows
// from that. Three things are deliberate:
//
//   * The budget is shown as a hard cap, with the server's ceiling stated next
//     to it. The browser proposes; `RunManager` bounds. A field that let
//     someone type any number, with the rejection arriving only after they
//     pressed the button, would be worse than no field.
//
//   * Spend is displayed while the run is going, not summarised at the end.
//     A cap you cannot watch approaching is a cap you only learn about by
//     hitting it.
//
//   * Refusals are shown as results, not as errors. A run whose agent was
//     refused five times did not fail; that is the write boundary working, and
//     it is the most interesting thing on the screen (DESIGN.md §15).

const ACTIVE = new Set(['starting', 'running'])

export default function RunPanel({ instructionSeed, onGraphChanged }) {
  const [config, setConfig] = useState(null)
  const [runs, setRuns] = useState(null)
  const [instructions, setInstructions] = useState('')
  const [budget, setBudget] = useState('')
  const [agentId, setAgentId] = useState('agent:ui-worker')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const settledRef = useRef(null)

  useEffect(() => {
    getRunConfig()
      .then((c) => { setConfig(c); setBudget(String(c.default_budget_usd)) })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (instructionSeed) {
      setInstructions((prev) =>
        prev ? prev : `Find attestations for the phrase ${instructionSeed} and propose one claim about its distribution.`,
      )
    }
  }, [instructionSeed])

  const poll = useCallback(async () => {
    try {
      const data = await getRuns()
      setRuns(data)
      // Reload the graph once, when a run stops being active — an agent run
      // writes continuously, so the view behind this panel is stale.
      const id = data.current?.id ?? data.history?.[0]?.id
      const active = ACTIVE.has(data.current?.state)
      if (!active && id && settledRef.current !== id) {
        settledRef.current = id
        onGraphChanged?.()
      }
      return active
    } catch {
      return false
    }
  }, [onGraphChanged])

  useEffect(() => {
    let timer
    let cancelled = false
    const tick = async () => {
      const active = await poll()
      if (cancelled) return
      timer = setTimeout(tick, active ? 900 : 4000)
    }
    tick()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [poll])

  const current = runs?.current
  const active = ACTIVE.has(current?.state)
  const last = runs?.history?.[0]
  const shown = current || last

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await startRun({
        instructions,
        budget_usd: Number(budget),
        agent_id: agentId,
      })
      settledRef.current = null
      await poll()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (error && !config) return <section className="runs"><p className="error">{error}</p></section>
  if (!config) return <section className="runs"><p className="hint">Loading…</p></section>

  const blocked = !config.model_configured || !config.corpus_available

  return (
    <section className="runs">
      <h2>Agent run</h2>

      {blocked && (
        <p className="warn">
          {!config.corpus_available
            ? 'No corpus is configured on this server, so an agent would have nothing to search.'
            : config.config_error}
        </p>
      )}

      <form className="run-form" onSubmit={submit}>
        <label className="field">
          <span>Task</span>
          <textarea
            rows={3}
            placeholder="e.g. Find attestations for 色即是空 across the corpus and propose one claim about how it is distributed."
            value={instructions}
            onChange={(e) => setInstructions(e.target.value)}
          />
        </label>

        <div className="field-row">
          <label className="field">
            <span>Budget (USD)</span>
            <input
              type="number" step="0.01" min="0.01" max={config.max_budget_usd}
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
            <small>
              hard cap; server ceiling ${config.max_budget_usd.toFixed(2)}
            </small>
          </label>
          <label className="field">
            <span>Agent id</span>
            <input value={agentId} onChange={(e) => setAgentId(e.target.value)} />
            <small>its declared scope shapes what it looks at</small>
          </label>
        </div>

        <div className="run-actions">
          <button
            className="btn accept" type="submit"
            disabled={busy || active || blocked || !instructions.trim()}
          >
            {active ? 'Run in progress…' : 'Start run'}
          </button>
          {active && (
            <button className="btn reject" type="button" onClick={() => stopRun().then(poll)}>
              Stop after this turn
            </button>
          )}
        </div>
        <p className="hint small">
          Model {config.model || '—'} · at most {config.max_turns} turns · the run
          holds this graph&apos;s writer lock, so accept/reject will conflict until
          it finishes.
        </p>
      </form>

      {error && <p className="error">{error}</p>}

      {shown && <RunReport run={shown} active={active} />}
    </section>
  )
}

function RunReport({ run, active }) {
  const s = run.spend
  const pct = Math.min(100, (s.spent_usd / s.budget_usd) * 100)
  return (
    <div className={`run-report ${active ? 'active' : ''}`}>
      <div className="run-head">
        <span className={`badge run-${run.state}`}>{run.state}</span>
        <code>{run.id}</code>
        <span>{run.elapsed_s}s</span>
        <span>{run.agent_id}</span>
      </div>

      <div className="spend">
        <div className="spend-bar"><i style={{ width: `${pct}%` }} /></div>
        <div className="spend-row">
          <span>
            <strong>${s.spent_usd.toFixed(5)}</strong> of ${s.budget_usd.toFixed(2)}
          </span>
          <span>{s.calls} model call{s.calls === 1 ? '' : 's'}</span>
        </div>
        {s.unpriced_calls > 0 && (
          <p className="warn small">
            {s.unpriced_calls} call{s.unpriced_calls === 1 ? '' : 's'} reported no
            cost and {s.unpriced_calls === 1 ? 'was' : 'were'} charged at an
            estimate, so the figure above is a lower bound.
          </p>
        )}
      </div>

      {run.stopped_early && <p className="warn small">{run.stopped_early}</p>}
      {run.error && <p className="error">{run.error}</p>}

      {run.tool_calls.length > 0 && (
        <>
          <h3>Tool calls ({run.tool_calls.length})</h3>
          <ul className="tool-calls">
            {run.tool_calls.map((c, i) => (
              <li key={i} className={c.is_error ? 'refused' : ''}>
                <div className="tc-head">
                  <code>{c.tool}</code>
                  <span className={`badge ${c.is_error ? 'tc-refused' : 'tc-ok'}`}>
                    {c.is_error ? 'refused' : 'ok'}
                  </span>
                </div>
                <p className="tc-result">{String(c.result)}</p>
              </li>
            ))}
          </ul>
        </>
      )}

      {run.refusals.length > 0 && (
        <>
          <h3>Refusals this run ({run.refusals.length})</h3>
          <p className="hint small">
            Writes the graph declined. Not failures — the boundary holding.
          </p>
          <ul className="tool-calls">
            {run.refusals.map((r) => (
              <li key={r.seq} className="refused">
                <div className="tc-head">
                  <code>{r.rule}</code>
                  <span>{r.attempted}</span>
                </div>
                <p className="tc-result">{r.message}</p>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
