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
const modeOptions = [["baseline", "Baseline"], ["router-review", "Routing mode"], ["focused", "Focused pass"]];
const workflowTerms = ["routing", "queue", "triage", "assignee", "priority", "sla risk", "routing desk", "queue lanes", "triage card", "assignee panel", "priority meter", "sla rail"];

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
  const [queueFilter, setQueueFilter] = useState("all");
  const [selectedTicketId, setSelectedTicketId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [routingMode, setRoutingMode] = useState("router-review");
  const [ticketSearch, setTicketSearch] = useState("");
  const [urgentOnly, setUrgentOnly] = useState(false);
  const [agentCapacity, setAgentCapacity] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = ticketSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = queueFilter === "all" || record.category === queueFilter;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !urgentOnly || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [queueFilter, ticketSearch, urgentOnly]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedTicketId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = routingMode === "router-review" ? 1.18 : routingMode === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const priorityScore = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const ageHours = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const queueLoad = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const routingConfidence = Math.round(selectedRecord.primary * modeMultiplier + agentCapacity);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(agentCapacity / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { priorityScore, ageHours, queueLoad, routingConfidence, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, agentCapacity]);

  const selectLeadRecord = () => setSelectedTicketId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setRoutingMode((value) => value === "baseline" ? "router-review" : value === "router-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-router task-010-support-ticket-router" aria-label="Build a support ticket routing desk">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal router handoff</p>
          <h1>Build a support ticket routing desk</h1>
          <p className="lead">A local-only ticket router for tickets with protected records, Queue filter, Routing mode, Ticket search, Urgent only, and Agent capacity.</p>
        </div>
        <span className="status-pill">Routing confidence</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local router controls">
        <label>
          Queue filter
          <select value={queueFilter} onChange={(event) => setQueueFilter(event.target.value)} aria-label="Queue filter">
            <option value="all">All tickets</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Routing mode
          <select value={routingMode} onChange={(event) => setRoutingMode(event.target.value)} aria-label="Routing mode">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Ticket search
          <input value={ticketSearch} onChange={(event) => setTicketSearch(event.target.value)} aria-label="Ticket search" placeholder="ID, owner, or name" />
        </label>
        <label>
          Agent capacity
          <input type="range" min="0" max="100" value={agentCapacity} onChange={(event) => setAgentCapacity(Number(event.target.value))} aria-label="Agent capacity" />
        </label>
        <button type="button" aria-pressed={urgentOnly} onClick={() => setUrgentOnly((value) => !value)}>Urgent only</button>
        <button type="button" onClick={selectLeadRecord}>Select lead ticket</button>
        <button type="button" onClick={cycleMode}>Cycle Routing mode</button>
      </section>

      <section className="metric-grid" aria-label="Derived router metrics">
        <article className="metric-card"><span>Priority score</span><strong>{formatMetric(summaryMetrics.priorityScore)}</strong><small>{visibleRecords.length} visible tickets</small></article>
        <article className="metric-card"><span>Age hours</span><strong>{formatMetric(summaryMetrics.ageHours)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Queue load</span><strong>{formatMetric(summaryMetrics.queueLoad)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Routing confidence</span><strong>{formatMetric(summaryMetrics.routingConfidence)}</strong><small>{routingMode} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="ticket list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedTicketId ? "active" : ""}`} onClick={() => setSelectedTicketId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-router" aria-label="ticket router">
          <div className="surface-head">
            <p className="eyebrow">ticket router</p>
            <h2>Routing Desk</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-router`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Routing confidence"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + agentCapacity, 100)}%` }} /></div>
          <p className="muted">assignee / priority / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected ticket inspector">
          <p className="eyebrow">Selected ticket</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Priority score</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Age hours</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Routing mode</span><strong>{routingMode}</strong></div>
          </div>
          <p className="muted">Workflow note: Urgent only and Agent capacity are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
