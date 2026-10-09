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
const modeOptions = [["baseline", "Baseline"], ["game-review", "Care mode"], ["focused", "Focused pass"]];
const workflowTerms = ["feed", "play", "rest", "pet care loop", "action streak", "energy forecast", "game stage", "care meter", "companion card", "routine tray", "energy meter", "action log"];

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
  const [speciesFilter, setSpeciesFilter] = useState("all");
  const [selectedPetId, setSelectedPetId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [careMode, setCareMode] = useState("game-review");
  const [companionSearch, setCompanionSearch] = useState("");
  const [nightRoutine, setNightRoutine] = useState(false);
  const [energyBoost, setEnergyBoost] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = companionSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = speciesFilter === "all" || record.category === speciesFilter;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !nightRoutine || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [speciesFilter, companionSearch, nightRoutine]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedPetId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = careMode === "game-review" ? 1.18 : careMode === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const careScore = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const hungerRisk = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const actionStreak = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const energyForecast = Math.round(selectedRecord.primary * modeMultiplier + energyBoost);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(energyBoost / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { careScore, hungerRisk, actionStreak, energyForecast, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, energyBoost]);

  const selectLeadRecord = () => setSelectedPetId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setCareMode((value) => value === "baseline" ? "game-review" : value === "game-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-game task-003-pet-care-game" aria-label="Build a pet care game stage">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal game handoff</p>
          <h1>Build a pet care game stage</h1>
          <p className="lead">A local-only care game stage for pets with protected records, Species filter, Care mode, Companion search, Night routine, and Energy boost.</p>
        </div>
        <span className="status-pill">Energy forecast</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local game controls">
        <label>
          Species filter
          <select value={speciesFilter} onChange={(event) => setSpeciesFilter(event.target.value)} aria-label="Species filter">
            <option value="all">All pets</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Care mode
          <select value={careMode} onChange={(event) => setCareMode(event.target.value)} aria-label="Care mode">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Companion search
          <input value={companionSearch} onChange={(event) => setCompanionSearch(event.target.value)} aria-label="Companion search" placeholder="ID, owner, or name" />
        </label>
        <label>
          Energy boost
          <input type="range" min="0" max="100" value={energyBoost} onChange={(event) => setEnergyBoost(Number(event.target.value))} aria-label="Energy boost" />
        </label>
        <button type="button" aria-pressed={nightRoutine} onClick={() => setNightRoutine((value) => !value)}>Night routine</button>
        <button type="button" onClick={selectLeadRecord}>Select lead pet</button>
        <button type="button" onClick={cycleMode}>Cycle Care mode</button>
      </section>

      <section className="metric-grid" aria-label="Derived game metrics">
        <article className="metric-card"><span>Care score</span><strong>{formatMetric(summaryMetrics.careScore)}</strong><small>{visibleRecords.length} visible pets</small></article>
        <article className="metric-card"><span>Hunger risk</span><strong>{formatMetric(summaryMetrics.hungerRisk)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Action streak</span><strong>{formatMetric(summaryMetrics.actionStreak)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Energy forecast</span><strong>{formatMetric(summaryMetrics.energyForecast)}</strong><small>{careMode} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="pet list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedPetId ? "active" : ""}`} onClick={() => setSelectedPetId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-game" aria-label="care game stage">
          <div className="surface-head">
            <p className="eyebrow">care game stage</p>
            <h2>Game Stage</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-game`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Energy forecast"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + energyBoost, 100)}%` }} /></div>
          <p className="muted">pet care loop / action streak / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected pet inspector">
          <p className="eyebrow">Selected pet</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Care score</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Hunger risk</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Care mode</span><strong>{careMode}</strong></div>
          </div>
          <p className="muted">Workflow note: Night routine and Energy boost are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
