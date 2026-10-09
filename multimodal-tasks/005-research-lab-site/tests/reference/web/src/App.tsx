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
const modeOptions = [["baseline", "Baseline"], ["site-review", "Review lens"], ["focused", "Focused pass"]];
const workflowTerms = ["lab", "laboratory", "research group", "publication", "collaboration", "replication review", "hero", "lab site", "publication cards", "collaborator rail", "project profile", "contact-safe triage"];

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
  const [researchArea, setResearchArea] = useState("all");
  const [selectedProjectId, setSelectedProjectId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [reviewLens, setReviewLens] = useState("site-review");
  const [projectSearch, setProjectSearch] = useState("");
  const [replicationWatch, setReplicationWatch] = useState(false);
  const [evidenceWeight, setEvidenceWeight] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = projectSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = researchArea === "all" || record.category === researchArea;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !replicationWatch || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [researchArea, projectSearch, replicationWatch]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedProjectId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = reviewLens === "site-review" ? 1.18 : reviewLens === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const publicationTotal = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const replicationIndex = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const collaborationDepth = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const evidenceAdjustedScore = Math.round(selectedRecord.primary * modeMultiplier + evidenceWeight);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(evidenceWeight / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { publicationTotal, replicationIndex, collaborationDepth, evidenceAdjustedScore, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, evidenceWeight]);

  const selectLeadRecord = () => setSelectedProjectId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setReviewLens((value) => value === "baseline" ? "site-review" : value === "site-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-site task-005-research-lab-site" aria-label="Create a research lab project site">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal site handoff</p>
          <h1>Create a research lab project site</h1>
          <p className="lead">A local-only research project site for projects with protected records, Research area, Review lens, Project search, Replication watch, and Evidence weight.</p>
        </div>
        <span className="status-pill">Lab contact triage</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local site controls">
        <label>
          Research area
          <select value={researchArea} onChange={(event) => setResearchArea(event.target.value)} aria-label="Research area">
            <option value="all">All projects</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Review lens
          <select value={reviewLens} onChange={(event) => setReviewLens(event.target.value)} aria-label="Review lens">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Project search
          <input value={projectSearch} onChange={(event) => setProjectSearch(event.target.value)} aria-label="Project search" placeholder="ID, owner, or name" />
        </label>
        <label>
          Evidence weight
          <input type="range" min="0" max="100" value={evidenceWeight} onChange={(event) => setEvidenceWeight(Number(event.target.value))} aria-label="Evidence weight" />
        </label>
        <button type="button" aria-pressed={replicationWatch} onClick={() => setReplicationWatch((value) => !value)}>Replication watch</button>
        <button type="button" onClick={selectLeadRecord}>Select lead project</button>
        <button type="button" onClick={cycleMode}>Cycle Review lens</button>
      </section>

      <section className="metric-grid" aria-label="Derived site metrics">
        <article className="metric-card"><span>Publication count</span><strong>{formatMetric(summaryMetrics.publicationTotal)}</strong><small>{visibleRecords.length} visible projects</small></article>
        <article className="metric-card"><span>Replication risk</span><strong>{formatMetric(summaryMetrics.replicationIndex)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Collaboration depth</span><strong>{formatMetric(summaryMetrics.collaborationDepth)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Lab contact triage</span><strong>{formatMetric(summaryMetrics.evidenceAdjustedScore)}</strong><small>{reviewLens} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="project list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedProjectId ? "active" : ""}`} onClick={() => setSelectedProjectId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-site" aria-label="research project site">
          <div className="surface-head">
            <p className="eyebrow">research project site</p>
            <h2>Hero</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-site`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Lab contact triage"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + evidenceWeight, 100)}%` }} /></div>
          <p className="muted">publication / collaboration / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected project inspector">
          <p className="eyebrow">Selected project</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Publication count</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Replication risk</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Review lens</span><strong>{reviewLens}</strong></div>
          </div>
          <p className="muted">Workflow note: Replication watch and Evidence weight are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
