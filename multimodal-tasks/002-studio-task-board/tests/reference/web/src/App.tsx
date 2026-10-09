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
const modeOptions = [["baseline", "Baseline"], ["kanban-review", "Capacity mode"], ["focused", "Focused pass"]];
const workflowTerms = ["kanban", "production lane", "board repair", "blocked work", "wip limit", "capacity warning", "priority", "urgency", "kanban board", "lane stack", "production board", "blocked card", "capacity meter", "wip panel"];

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
  const groupedLanes = useMemo(() => new Map(categories.map((category) => [category, localRecords.filter((record) => record.category === category)])), [categories]);
  const [visibleLane, setVisibleLane] = useState("all");
  const [selectedTaskId, setSelectedTaskId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [capacityMode, setCapacityMode] = useState("kanban-review");
  const [taskSearch, setTaskSearch] = useState("");
  const [showBlockers, setShowBlockers] = useState(false);
  const [wipLimit, setWipLimit] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = taskSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = visibleLane === "all" || record.category === visibleLane;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !showBlockers || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [visibleLane, taskSearch, showBlockers]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedTaskId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = capacityMode === "kanban-review" ? 1.18 : capacityMode === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const laneEffort = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const blockedDays = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const blockedLaneCount = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const capacityPressure = Math.round(selectedRecord.primary * modeMultiplier + wipLimit);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(wipLimit / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { laneEffort, blockedDays, blockedLaneCount, capacityPressure, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, wipLimit]);

  const selectLeadRecord = () => setSelectedTaskId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setCapacityMode((value) => value === "baseline" ? "kanban-review" : value === "kanban-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-board task-002-studio-task-board" aria-label="Repair a studio production board">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal kanban handoff</p>
          <h1>Repair a studio production board</h1>
          <p className="lead">A local-only production board for tasks with protected records, Lane filter, Capacity mode, Task search, Show blockers, WIP limit, and {groupedLanes.size} priority lane groups.</p>
        </div>
        <span className="status-pill">WIP capacity warning</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local kanban controls">
        <label>
          Lane filter
          <select value={visibleLane} onChange={(event) => setVisibleLane(event.target.value)} aria-label="Lane filter">
            <option value="all">All tasks</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Capacity mode
          <select value={capacityMode} onChange={(event) => setCapacityMode(event.target.value)} aria-label="Capacity mode">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Task search
          <input value={taskSearch} onChange={(event) => setTaskSearch(event.target.value)} aria-label="Task search" placeholder="ID, owner, or name" />
        </label>
        <label>
          WIP limit
          <input type="range" min="0" max="100" value={wipLimit} onChange={(event) => setWipLimit(Number(event.target.value))} aria-label="WIP limit" />
        </label>
        <button type="button" aria-pressed={showBlockers} onClick={() => setShowBlockers((value) => !value)}>Show blockers</button>
        <button type="button" onClick={selectLeadRecord}>Select lead task</button>
        <button type="button" onClick={cycleMode}>Cycle Capacity mode</button>
      </section>

      <section className="metric-grid" aria-label="Derived kanban metrics">
        <article className="metric-card"><span>Effort points</span><strong>{formatMetric(summaryMetrics.laneEffort)}</strong><small>{visibleRecords.length} visible tasks</small></article>
        <article className="metric-card"><span>Days blocked</span><strong>{formatMetric(summaryMetrics.blockedDays)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Blocked lane count</span><strong>{formatMetric(summaryMetrics.blockedLaneCount)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>WIP capacity warning</span><strong>{formatMetric(summaryMetrics.capacityPressure)}</strong><small>{capacityMode} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="task list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedTaskId ? "active" : ""}`} onClick={() => setSelectedTaskId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-board" aria-label="production board">
          <div className="surface-head">
            <p className="eyebrow">production board</p>
            <h2>Kanban Board</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className="surface-card card-board" key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="WIP capacity warning"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + wipLimit, 100)}%` }} /></div>
          <p className="muted">blocked work / wip limit / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected task inspector">
          <p className="eyebrow">Selected task</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Effort points</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Days blocked</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Capacity mode</span><strong>{capacityMode}</strong></div>
          </div>
          <p className="muted">Workflow note: Show blockers and WIP limit are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
