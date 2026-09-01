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
//     it is the most interesting thing on the screen (docs/design.md §15).
//
// A run is one *or several* agents. What several buy is declared viewpoint
// diversity, so each row asks for a corpus scope and a method — real research
// commitments that change what an agent looks at — rather than a personality.
// The agents cannot see each other: there is no channel and no shared
// transcript (docs/design.md §5 principle 3), and the panel says so rather than
// letting a viewer assume they collaborate.

const ACTIVE = new Set(['starting', 'running'])

export default function RunPanel({ instructionSeed, onGraphChanged }) {
  const [config, setConfig] = useState(null)
  const [runs, setRuns] = useState(null)
  const [agents, setAgents] = useState([blankAgent(0)])
  const [budget, setBudget] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const settledRef = useRef(null)

  useEffect(() => {
    getRunConfig()
      .then((c) => { setConfig(c); setBudget(String(c.default_budget_usd)) })
      .catch((e) => setError(e.message))
  }, [])

  useEffect(() => {
    if (!instructionSeed) return
    setAgents((prev) => {
      if (prev[0].instructions) return prev
      const next = [...prev]
      next[0] = {
        ...next[0],
        instructions:
          `Find attestations for the phrase ${instructionSeed} and propose one claim about its distribution.`,
      }
      return next
    })
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

  const update = (i, patch) =>
    setAgents((prev) => prev.map((a, j) => (j === i ? { ...a, ...patch } : a)))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await startRun({
        budget_usd: Number(budget),
        agents: agents.map((a) => ({
          agent_id: a.agent_id,
          instructions: a.instructions,
          corpus_scope: a.corpus_scope,
          method_label: a.method_label,
          model: a.model,
        })),
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
        {agents.map((a, i) => (
          <div className="agent-card" key={a.key}>
            <div className="agent-head">
              <span className="agent-n">Agent {i + 1}</span>
              <input
                className="agent-id"
                value={a.agent_id}
                onChange={(e) => update(i, { agent_id: e.target.value })}
                aria-label={`Agent ${i + 1} id`}
              />
              {agents.length > 1 && (
                <button
                  type="button" className="btn tiny"
                  onClick={() => setAgents(agents.filter((_, j) => j !== i))}
                >remove</button>
              )}
            </div>
            <label className="field">
              <span>Task</span>
              <textarea
                rows={3}
                placeholder="e.g. Find attestations for 色即是空 and propose one claim about how it is distributed."
                value={a.instructions}
                onChange={(e) => update(i, { instructions: e.target.value })}
              />
            </label>
            <div className="field-row">
              <label className="field">
                <span>Model</span>
                <select
                  value={a.model}
                  onChange={(e) => update(i, { model: e.target.value })}
                >
                  <option value="">{config.model || 'server default'}</option>
                  {(config.models || [])
                    .filter((m) => m !== config.model)
                    .map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </label>
              <label className="field">
                <span>Corpus scope</span>
                <input
                  placeholder="e.g. Prajñāpāramitā translations only"
                  value={a.corpus_scope}
                  onChange={(e) => update(i, { corpus_scope: e.target.value })}
                />
              </label>
              <label className="field">
                <span>Method</span>
                <input
                  placeholder="e.g. phrase distribution"
                  value={a.method_label}
                  onChange={(e) => update(i, { method_label: e.target.value })}
                />
              </label>
            </div>
            <p className="hint small">
              Scope and method are recorded on the agent&apos;s profile and
              prepended to its instructions. Give two agents different ones and
              their disagreement means something &mdash; which is only true if
              they also read on different models, so a run whose agents share a
              model family is refused.
            </p>
          </div>
        ))}

        <div className="agent-add">
          <button
            type="button" className="btn"
            disabled={agents.length >= (config.max_agents || 1)}
            onClick={() => setAgents([...agents, blankAgent(agents.length)])}
          >
            + Add agent
          </button>
          <span className="hint small">
            {agents.length} of {config.max_agents} · they run concurrently
            against one graph and share the budget below. They cannot see each
            other&apos;s work. Each needs its own model family: two agents on
            one model share priors, so their agreement would be one observation
            reported twice.
            {agents.length > 1 && (config.models || []).length < agents.length && (
              <> Set <code>OPENROUTER_MODELS</code> to add more.</>
            )}
          </span>
        </div>

        <div className="field-row">
          <label className="field">
            <span>Budget (USD)</span>
            <input
              type="number" step="0.01" min="0.01" max={config.max_budget_usd}
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
            <small>
              hard cap for the whole run; server ceiling ${config.max_budget_usd.toFixed(2)}
            </small>
          </label>
        </div>

        <div className="run-actions">
          <button
            className="btn accept" type="submit"
            disabled={busy || active || blocked || agents.some((a) => !a.instructions.trim())}
          >
            {active ? 'Run in progress…' : `Start run (${agents.length} agent${agents.length === 1 ? '' : 's'})`}
          </button>
          {active && (
            <button className="btn reject" type="button" onClick={() => stopRun().then(poll)}>
              Stop after this turn
            </button>
          )}
        </div>
        <p className="hint small">
          Model {config.model || '—'} · at most {config.max_turns} turns each · the
          run holds this graph&apos;s writer lock, so accept/reject will conflict
          until it finishes.
        </p>
      </form>

      {error && <p className="error">{error}</p>}

      {shown && <RunReport run={shown} active={active} />}
    </section>
  )
}

function blankAgent(i) {
  return {
    key: `a${i}-${Math.random().toString(36).slice(2, 7)}`,
    agent_id: `agent:ui-${i + 1}`,
    instructions: '',
    corpus_scope: '',
    method_label: '',
    model: '',
  }
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

      {(run.agents || []).map((a) => (
        <div className="agent-report" key={a.agent_id}>
          <h3>
            {a.agent_id}
            {a.model && <code className="agent-model">{a.model}</code>}
            {a.corpus_scope && <em> · {a.corpus_scope}</em>}
          </h3>
          {a.error && <p className="error">{a.error}</p>}
          {a.tool_calls.length === 0 && !a.error && (
            <p className="hint small">No tool calls yet.</p>
          )}
          <ul className="tool-calls">
            {a.tool_calls.map((c, i) => (
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
        </div>
      ))}

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
