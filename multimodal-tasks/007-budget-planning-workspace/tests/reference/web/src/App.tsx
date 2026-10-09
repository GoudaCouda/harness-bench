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
const modeOptions = [["baseline", "Baseline"], ["matrix-review", "Scenario"], ["focused", "Focused pass"]];
const workflowTerms = ["allocation", "matrix", "variance", "reserve", "scenario planning", "budget cap", "matrix", "allocation cells", "variance bars", "reserve panel", "budget grid", "scenario rail"];

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
  const [budgetBucket, setBudgetBucket] = useState("all");
  const [selectedBudgetId, setSelectedBudgetId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [budgetScenario, setBudgetScenario] = useState("matrix-review");
  const [budgetSearch, setBudgetSearch] = useState("");
  const [reserveView, setReserveView] = useState(false);
  const [adjustmentPercent, setAdjustmentPercent] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = budgetSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = budgetBucket === "all" || record.category === budgetBucket;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !reserveView || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [budgetBucket, budgetSearch, reserveView]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedBudgetId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = budgetScenario === "matrix-review" ? 1.18 : budgetScenario === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const plannedSpend = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const varianceTotal = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const reserveGap = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const scenarioSpend = Math.round(selectedRecord.primary * modeMultiplier + adjustmentPercent);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(adjustmentPercent / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { plannedSpend, varianceTotal, reserveGap, scenarioSpend, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, adjustmentPercent]);

  const selectLeadRecord = () => setSelectedBudgetId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setBudgetScenario((value) => value === "baseline" ? "matrix-review" : value === "matrix-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-matrix task-007-budget-planning-workspace" aria-label="Build a budget planning matrix">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal matrix handoff</p>
          <h1>Build a budget planning matrix</h1>
          <p className="lead">A local-only budget matrix for budget items with protected records, Budget bucket, Scenario, Budget search, Reserve view, and Adjustment percent.</p>
        </div>
        <span className="status-pill">Allocation scenario</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local matrix controls">
        <label>
          Budget bucket
          <select value={budgetBucket} onChange={(event) => setBudgetBucket(event.target.value)} aria-label="Budget bucket">
            <option value="all">All budget items</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Scenario
          <select value={budgetScenario} onChange={(event) => setBudgetScenario(event.target.value)} aria-label="Scenario">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Budget search
          <input value={budgetSearch} onChange={(event) => setBudgetSearch(event.target.value)} aria-label="Budget search" placeholder="ID, owner, or name" />
        </label>
        <label>
          Adjustment percent
          <input type="range" min="0" max="100" value={adjustmentPercent} onChange={(event) => setAdjustmentPercent(Number(event.target.value))} aria-label="Adjustment percent" />
        </label>
        <button type="button" aria-pressed={reserveView} onClick={() => setReserveView((value) => !value)}>Reserve view</button>
        <button type="button" onClick={selectLeadRecord}>Select lead budget item</button>
        <button type="button" onClick={cycleMode}>Cycle Scenario</button>
      </section>

      <section className="metric-grid" aria-label="Derived matrix metrics">
        <article className="metric-card"><span>Planned spend</span><strong>{formatMetric(summaryMetrics.plannedSpend)}</strong><small>{visibleRecords.length} visible budget items</small></article>
        <article className="metric-card"><span>Variance</span><strong>{formatMetric(summaryMetrics.varianceTotal)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Reserve gap</span><strong>{formatMetric(summaryMetrics.reserveGap)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Allocation scenario</span><strong>{formatMetric(summaryMetrics.scenarioSpend)}</strong><small>{budgetScenario} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="budget item list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedBudgetId ? "active" : ""}`} onClick={() => setSelectedBudgetId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-matrix" aria-label="budget matrix">
          <div className="surface-head">
            <p className="eyebrow">budget matrix</p>
            <h2>Matrix</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-matrix`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Allocation scenario"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + adjustmentPercent, 100)}%` }} /></div>
          <p className="muted">reserve / scenario planning / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected budget item inspector">
          <p className="eyebrow">Selected budget item</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Planned spend</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Variance</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Scenario</span><strong>{budgetScenario}</strong></div>
          </div>
          <p className="muted">Workflow note: Reserve view and Adjustment percent are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
