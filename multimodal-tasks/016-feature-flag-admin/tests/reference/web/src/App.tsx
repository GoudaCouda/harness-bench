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
const modeOptions = [["baseline", "Baseline"], ["flags-review", "Rollout mode"], ["focused", "Focused pass"]];
const workflowTerms = ["feature flag", "rollout", "cohort", "guardrail", "environment", "kill switch", "flag matrix", "environment cells", "guardrail rail", "rollout slider", "cohort meter", "kill switch panel"];

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
  const [environmentFilter, setEnvironmentFilter] = useState("all");
  const [selectedFlagId, setSelectedFlagId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [rolloutMode, setRolloutMode] = useState("flags-review");
  const [flagSearch, setFlagSearch] = useState("");
  const [guardrailsOnly, setGuardrailsOnly] = useState(false);
  const [cohortPercent, setCohortPercent] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = flagSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = environmentFilter === "all" || record.category === environmentFilter;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !guardrailsOnly || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [environmentFilter, flagSearch, guardrailsOnly]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedFlagId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = rolloutMode === "flags-review" ? 1.18 : rolloutMode === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const exposurePercent = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const errorBudget = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const guardrailTrips = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const rolloutDecision = Math.round(selectedRecord.primary * modeMultiplier + cohortPercent);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(cohortPercent / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { exposurePercent, errorBudget, guardrailTrips, rolloutDecision, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, cohortPercent]);

  const selectLeadRecord = () => setSelectedFlagId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setRolloutMode((value) => value === "baseline" ? "flags-review" : value === "flags-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-flags task-016-feature-flag-admin" aria-label="Build a feature flag rollout matrix">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal flags handoff</p>
          <h1>Build a feature flag rollout matrix</h1>
          <p className="lead">A local-only rollout matrix for flags with protected records, Environment, Rollout mode, Flag search, Guardrails only, and Cohort percent.</p>
        </div>
        <span className="status-pill">Rollout decision</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local flags controls">
        <label>
          Environment
          <select value={environmentFilter} onChange={(event) => setEnvironmentFilter(event.target.value)} aria-label="Environment">
            <option value="all">All flags</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Rollout mode
          <select value={rolloutMode} onChange={(event) => setRolloutMode(event.target.value)} aria-label="Rollout mode">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Flag search
          <input value={flagSearch} onChange={(event) => setFlagSearch(event.target.value)} aria-label="Flag search" placeholder="ID, owner, or name" />
        </label>
        <label>
          Cohort percent
          <input type="range" min="0" max="100" value={cohortPercent} onChange={(event) => setCohortPercent(Number(event.target.value))} aria-label="Cohort percent" />
        </label>
        <button type="button" aria-pressed={guardrailsOnly} onClick={() => setGuardrailsOnly((value) => !value)}>Guardrails only</button>
        <button type="button" onClick={selectLeadRecord}>Select lead flag</button>
        <button type="button" onClick={cycleMode}>Cycle Rollout mode</button>
      </section>

      <section className="metric-grid" aria-label="Derived flags metrics">
        <article className="metric-card"><span>Exposure percent</span><strong>{formatMetric(summaryMetrics.exposurePercent)}</strong><small>{visibleRecords.length} visible flags</small></article>
        <article className="metric-card"><span>Error budget</span><strong>{formatMetric(summaryMetrics.errorBudget)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Guardrail trips</span><strong>{formatMetric(summaryMetrics.guardrailTrips)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Rollout decision</span><strong>{formatMetric(summaryMetrics.rolloutDecision)}</strong><small>{rolloutMode} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="flag list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedFlagId ? "active" : ""}`} onClick={() => setSelectedFlagId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-flags" aria-label="rollout matrix">
          <div className="surface-head">
            <p className="eyebrow">rollout matrix</p>
            <h2>Flag Matrix</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-flags`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Rollout decision"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + cohortPercent, 100)}%` }} /></div>
          <p className="muted">guardrail / environment / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected flag inspector">
          <p className="eyebrow">Selected flag</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Exposure percent</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Error budget</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Rollout mode</span><strong>{rolloutMode}</strong></div>
          </div>
          <p className="muted">Workflow note: Guardrails only and Cohort percent are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
