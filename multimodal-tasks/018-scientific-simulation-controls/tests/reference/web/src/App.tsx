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
const modeOptions = [["baseline", "Baseline"], ["simulation-review", "Run mode"], ["focused", "Focused pass"]];
const workflowTerms = ["simulation", "parameter", "control", "sensitivity", "noise", "model output", "simulation output", "parameter slider", "result curve", "control panel", "sensitivity chart", "model readout"];

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
  const [modelFamily, setModelFamily] = useState("all");
  const [selectedRunId, setSelectedRunId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [runMode, setRunMode] = useState("simulation-review");
  const [runSearch, setRunSearch] = useState("");
  const [unstableOnly, setUnstableOnly] = useState(false);
  const [parameterValue, setParameterValue] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = runSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = modelFamily === "all" || record.category === modelFamily;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !unstableOnly || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [modelFamily, runSearch, unstableOnly]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedRunId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = runMode === "simulation-review" ? 1.18 : runMode === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const signalStrength = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const noiseLevel = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const parameterDrift = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const sensitivityOutput = Math.round(selectedRecord.primary * modeMultiplier + parameterValue);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(parameterValue / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { signalStrength, noiseLevel, parameterDrift, sensitivityOutput, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, parameterValue]);

  const selectLeadRecord = () => setSelectedRunId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setRunMode((value) => value === "baseline" ? "simulation-review" : value === "simulation-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-simulation task-018-scientific-simulation-controls" aria-label="Build scientific simulation controls">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal simulation handoff</p>
          <h1>Build scientific simulation controls</h1>
          <p className="lead">A local-only simulation controls for runs with protected records, Model family, Run mode, Run search, Unstable only, and Parameter value.</p>
        </div>
        <span className="status-pill">Sensitivity output</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local simulation controls">
        <label>
          Model family
          <select value={modelFamily} onChange={(event) => setModelFamily(event.target.value)} aria-label="Model family">
            <option value="all">All runs</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Run mode
          <select value={runMode} onChange={(event) => setRunMode(event.target.value)} aria-label="Run mode">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Run search
          <input value={runSearch} onChange={(event) => setRunSearch(event.target.value)} aria-label="Run search" placeholder="ID, owner, or name" />
        </label>
        <label>
          Parameter value
          <input type="range" min="0" max="100" value={parameterValue} onChange={(event) => setParameterValue(Number(event.target.value))} aria-label="Parameter value" />
        </label>
        <button type="button" aria-pressed={unstableOnly} onClick={() => setUnstableOnly((value) => !value)}>Unstable only</button>
        <button type="button" onClick={selectLeadRecord}>Select lead run</button>
        <button type="button" onClick={cycleMode}>Cycle Run mode</button>
      </section>

      <section className="metric-grid" aria-label="Derived simulation metrics">
        <article className="metric-card"><span>Signal strength</span><strong>{formatMetric(summaryMetrics.signalStrength)}</strong><small>{visibleRecords.length} visible runs</small></article>
        <article className="metric-card"><span>Noise level</span><strong>{formatMetric(summaryMetrics.noiseLevel)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Parameter drift</span><strong>{formatMetric(summaryMetrics.parameterDrift)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Sensitivity output</span><strong>{formatMetric(summaryMetrics.sensitivityOutput)}</strong><small>{runMode} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="run list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedRunId ? "active" : ""}`} onClick={() => setSelectedRunId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-simulation" aria-label="simulation controls">
          <div className="surface-head">
            <p className="eyebrow">simulation controls</p>
            <h2>Simulation Output</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-simulation`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Sensitivity output"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + parameterValue, 100)}%` }} /></div>
          <p className="muted">sensitivity / noise / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected run inspector">
          <p className="eyebrow">Selected run</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Signal strength</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Noise level</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Run mode</span><strong>{runMode}</strong></div>
          </div>
          <p className="muted">Workflow note: Unstable only and Parameter value are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
