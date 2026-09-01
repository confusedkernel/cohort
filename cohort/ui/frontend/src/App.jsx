import { useCallback, useEffect, useState } from 'react'
import { getGraph, getHealth, getRefusals } from './api'
import DetailPanel from './DetailPanel'
import GraphView from './GraphView'
import CorpusPanel from './CorpusPanel'
import RefusalsPanel from './RefusalsPanel'
import RunPanel from './RunPanel'
import Settings, { applyTheme, loadTheme } from './Settings'
import StatsBar from './StatsBar'
import { EDGE_STYLE } from './graph-model'

export default function App() {
  const [data, setData] = useState(null)
  const [health, setHealth] = useState(null)
  const [refusals, setRefusals] = useState(null)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [showAudit, setShowAudit] = useState(false)
  const [showRefusals, setShowRefusals] = useState(false)
  const [tab, setTab] = useState('graph')
  const [theme, setTheme] = useState(loadTheme)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [statsOpen, setStatsOpen] = useState(false)
  const [agentSeed, setAgentSeed] = useState(null)

  const reload = useCallback(() => {
    Promise.all([getGraph(), getHealth()])
      .then(([g, h]) => { setData(g); setHealth(h) })
      .catch((e) => setError(e.message))
    // A missing log is a legitimate state, not an error, so a failure here
    // must not blank the whole view.
    getRefusals().then(setRefusals).catch(() => setRefusals(null))
  }, [])

  useEffect(() => { applyTheme(theme) }, [theme])

  useEffect(reload, [reload])

  // Escape dismisses the floating inspector — the ordinary gesture for a panel
  // that overlays content rather than sitting beside it.
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') setSelectedId(null) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
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
          <span className="tag">
            evidence graph · {health?.writes_enabled ? 'researcher' : 'read-only'}
          </span>
        </div>
        <div className="counts">
          <StatsBar
            health={health}
            open={statsOpen}
            onToggle={(v) => { setStatsOpen(v); if (v) setSettingsOpen(false) }}
          />
        </div>
        <nav className="tabs">
          {[
            ['graph', 'Graph'],
            health?.corpus_enabled && ['corpus', 'Corpus'],
            health?.runs_enabled && ['run', 'Agent run'],
          ].filter(Boolean).map(([key, label]) => (
            <button
              key={key}
              className={`tab ${tab === key ? 'on' : ''}`}
              onClick={() => setTab(key)}
            >{label}</button>
          ))}
        </nav>

        <div className="topbar-controls">
          {/* Refusals are an output of this system, not a debug view
              (DESIGN.md §15), so the count is always on screen — a zero is
              itself a fact worth showing. */}
          <button
            className={`refusal-tab ${showRefusals ? 'on' : ''}`}
            onClick={() => setShowRefusals((v) => !v)}
            disabled={!refusals?.available}
            title={
              refusals?.available
                ? 'Writes this graph refused, and which rule refused them'
                : 'No event log beside this projection, so refusals cannot be read'
            }
          >
            refused writes
            <span className="refusal-count">
              {refusals?.available ? refusals.total : '—'}
            </span>
          </button>
          <Settings
            open={settingsOpen}
            onToggle={(v) => { setSettingsOpen(v); if (v) setStatsOpen(false) }}
            theme={theme}
            onTheme={setTheme}
            showAudit={showAudit}
            onShowAudit={setShowAudit}
          />
        </div>
      </header>

      {data.truncated && (
        <div className="banner">
          This view is truncated — some nodes are not shown, so the support
          visible here is not the whole graph.
        </div>
      )}

      <div className="body">
        <main>
          {tab === 'graph' && (
            <>
              <Legend />
              <GraphView
                data={data}
                selectedId={selectedId}
                onSelect={setSelectedId}
                showAudit={showAudit}
              />
            </>
          )}
          {tab === 'corpus' && (
            <CorpusPanel
              onCite={(phrase) => { setAgentSeed(phrase); setTab('run') }}
            />
          )}
          {tab === 'run' && (
            <RunPanel instructionSeed={agentSeed} onGraphChanged={reload} />
          )}
          {showRefusals && <RefusalsPanel refusals={refusals} />}
        </main>
        {/* Floating inspector, and only over the graph: it is the graph's
            detail view, so overlaying the corpus or run panels with it would
            cover unrelated content. */}
        {tab === 'graph' && (
          <DetailPanel
            nodeId={selectedId}
            onSelect={setSelectedId}
            onClose={() => setSelectedId(null)}
            canWrite={!!health?.writes_enabled}
            onChanged={reload}
          />
        )}
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
