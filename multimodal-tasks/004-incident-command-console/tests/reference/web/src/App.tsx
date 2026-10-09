import { useMemo, useState } from "react";
import rawRecords from "./data/localRecords.json";

type LocalRecord = {
  id: string;
  name: string;
  category: string;
  owner: string;
  status: "clear" | "watch" | "review";
  primary: number;
  secondary: number;
};

const localRecords = rawRecords as LocalRecord[];
const modeOptions = [["baseline", "Baseline"], ["timeline-review", "Response mode"], ["focused", "Focused pass"]];
const workflowTerms = ["timeline", "incident log", "checkpoint", "commander notes", "response plan", "escalation queue", "timeline", "command log", "checkpoint rail", "severity ribbon", "response pane", "incident console"];

function statusClass(status: LocalRecord["status"]) {
  if (status === "review") return "status-critical";
  if (status === "watch") return "status-watch";
  return "status-clear";
}

function formatMetric(value: number) {
  return value.toLocaleString();
}

function App() {
  const categories = useMemo(() => Array.from(new Set(localRecords.map((record) => record.category))), []);
  const [serviceFilter, setServiceFilter] = useState("all");
  const [selectedIncidentId, setSelectedIncidentId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [responseMode, setResponseMode] = useState("timeline-review");
  const [incidentSearch, setIncidentSearch] = useState("");
  const [escalatedOnly, setEscalatedOnly] = useState(false);
  const [slaPressure, setSlaPressure] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = incidentSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = serviceFilter === "all" || record.category === serviceFilter;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !escalatedOnly || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [serviceFilter, incidentSearch, escalatedOnly]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedIncidentId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = responseMode === "timeline-review" ? 1.18 : responseMode === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const impactLoad = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const openMinutes = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const escalationQueue = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const slaAdjustedImpact = Math.round(selectedRecord.primary * modeMultiplier + slaPressure);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(slaPressure / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { impactLoad, openMinutes, escalationQueue, slaAdjustedImpact, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, slaPressure]);

  const selectLeadRecord = () => setSelectedIncidentId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setResponseMode((value) => value === "baseline" ? "timeline-review" : value === "timeline-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-timeline task-004-incident-command-console" aria-label="Build an incident command console">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal timeline handoff</p>
          <h1>Build an incident command console</h1>
          <p className="lead">A local-only incident timeline for incidents with protected records, Service filter, Response mode, Incident search, Escalated only, and SLA pressure.</p>
        </div>
        <span className="status-pill">Response checkpoint</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local timeline controls">
        <label>
          Service filter
          <select value={serviceFilter} onChange={(event) => setServiceFilter(event.target.value)} aria-label="Service filter">
            <option value="all">All incidents</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Response mode
          <select value={responseMode} onChange={(event) => setResponseMode(event.target.value)} aria-label="Response mode">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Incident search
          <input value={incidentSearch} onChange={(event) => setIncidentSearch(event.target.value)} aria-label="Incident search" placeholder="ID, owner, or name" />
        </label>
        <label>
          SLA pressure
          <input type="range" min="0" max="100" value={slaPressure} onChange={(event) => setSlaPressure(Number(event.target.value))} aria-label="SLA pressure" />
        </label>
        <button type="button" aria-pressed={escalatedOnly} onClick={() => setEscalatedOnly((value) => !value)}>Escalated only</button>
        <button type="button" onClick={selectLeadRecord}>Select lead incident</button>
        <button type="button" onClick={cycleMode}>Cycle Response mode</button>
      </section>

      <section className="metric-grid" aria-label="Derived timeline metrics">
        <article className="metric-card"><span>Impact score</span><strong>{formatMetric(summaryMetrics.impactLoad)}</strong><small>{visibleRecords.length} visible incidents</small></article>
        <article className="metric-card"><span>Minutes open</span><strong>{formatMetric(summaryMetrics.openMinutes)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Escalation queue</span><strong>{formatMetric(summaryMetrics.escalationQueue)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Response checkpoint</span><strong>{formatMetric(summaryMetrics.slaAdjustedImpact)}</strong><small>{responseMode} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="incident list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedIncidentId ? "active" : ""}`} onClick={() => setSelectedIncidentId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-timeline" aria-label="incident timeline">
          <div className="surface-head">
            <p className="eyebrow">incident timeline</p>
            <h2>Timeline</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-timeline`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Response checkpoint"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + slaPressure, 100)}%` }} /></div>
          <p className="muted">commander notes / response plan / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected incident inspector">
          <p className="eyebrow">Selected incident</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Impact score</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Minutes open</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Response mode</span><strong>{responseMode}</strong></div>
          </div>
          <p className="muted">Workflow note: Escalated only and SLA pressure are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
