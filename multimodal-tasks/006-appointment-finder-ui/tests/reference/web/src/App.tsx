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
const modeOptions = [["baseline", "Baseline"], ["appointment-review", "Visit mode"], ["focused", "Focused pass"]];
const workflowTerms = ["appointment", "slot", "service", "shortlist", "travel window", "availability", "slot rail", "appointment cards", "shortlist", "travel window", "provider panel", "availability cue"];

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
  const [serviceType, setServiceType] = useState("all");
  const [selectedSlotId, setSelectedSlotId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [visitMode, setVisitMode] = useState("appointment-review");
  const [providerSearch, setProviderSearch] = useState("");
  const [shortlistOnly, setShortlistOnly] = useState(false);
  const [travelWindow, setTravelWindow] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = providerSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = serviceType === "all" || record.category === serviceType;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !shortlistOnly || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [serviceType, providerSearch, shortlistOnly]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedSlotId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = visitMode === "appointment-review" ? 1.18 : visitMode === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const fitScore = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const travelMinutes = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const shortlistSize = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const windowAdjustedFit = Math.round(selectedRecord.primary * modeMultiplier + travelWindow);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(travelWindow / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { fitScore, travelMinutes, shortlistSize, windowAdjustedFit, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, travelWindow]);

  const selectLeadRecord = () => setSelectedSlotId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setVisitMode((value) => value === "baseline" ? "appointment-review" : value === "appointment-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-appointment task-006-appointment-finder-ui" aria-label="Build an appointment finder UI">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal appointment handoff</p>
          <h1>Build an appointment finder UI</h1>
          <p className="lead">A local-only appointment shortlist for slots with protected records, Service type, Visit mode, Provider search, Shortlist only, and Travel window.</p>
        </div>
        <span className="status-pill">Travel window review</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local appointment controls">
        <label>
          Service type
          <select value={serviceType} onChange={(event) => setServiceType(event.target.value)} aria-label="Service type">
            <option value="all">All slots</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Visit mode
          <select value={visitMode} onChange={(event) => setVisitMode(event.target.value)} aria-label="Visit mode">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Provider search
          <input value={providerSearch} onChange={(event) => setProviderSearch(event.target.value)} aria-label="Provider search" placeholder="ID, owner, or name" />
        </label>
        <label>
          Travel window
          <input type="range" min="0" max="100" value={travelWindow} onChange={(event) => setTravelWindow(Number(event.target.value))} aria-label="Travel window" />
        </label>
        <button type="button" aria-pressed={shortlistOnly} onClick={() => setShortlistOnly((value) => !value)}>Shortlist only</button>
        <button type="button" onClick={selectLeadRecord}>Select lead slot</button>
        <button type="button" onClick={cycleMode}>Cycle Visit mode</button>
      </section>

      <section className="metric-grid" aria-label="Derived appointment metrics">
        <article className="metric-card"><span>Fit score</span><strong>{formatMetric(summaryMetrics.fitScore)}</strong><small>{visibleRecords.length} visible slots</small></article>
        <article className="metric-card"><span>Minutes travel</span><strong>{formatMetric(summaryMetrics.travelMinutes)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Shortlist size</span><strong>{formatMetric(summaryMetrics.shortlistSize)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Travel window review</span><strong>{formatMetric(summaryMetrics.windowAdjustedFit)}</strong><small>{visitMode} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="slot list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedSlotId ? "active" : ""}`} onClick={() => setSelectedSlotId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-appointment" aria-label="appointment shortlist">
          <div className="surface-head">
            <p className="eyebrow">appointment shortlist</p>
            <h2>Slot Rail</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-appointment`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Travel window review"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + travelWindow, 100)}%` }} /></div>
          <p className="muted">shortlist / travel window / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected slot inspector">
          <p className="eyebrow">Selected slot</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Fit score</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Minutes travel</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Visit mode</span><strong>{visitMode}</strong></div>
          </div>
          <p className="muted">Workflow note: Shortlist only and Travel window are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
