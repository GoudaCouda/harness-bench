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
const modeOptions = [["baseline", "Baseline"], ["diff-review", "Version lens"], ["focused", "Focused pass"]];
const workflowTerms = ["diff", "redline", "comparison", "release review", "clause notes", "change count", "split diff", "comparison pane", "redline", "clause list", "version lens", "release review"];

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
  const [policyArea, setPolicyArea] = useState("all");
  const [selectedSectionId, setSelectedSectionId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [versionLens, setVersionLens] = useState("diff-review");
  const [clauseSearch, setClauseSearch] = useState("");
  const [changedOnly, setChangedOnly] = useState(false);
  const [reviewStrictness, setReviewStrictness] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = clauseSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = policyArea === "all" || record.category === policyArea;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !changedOnly || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [policyArea, clauseSearch, changedOnly]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedSectionId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = versionLens === "diff-review" ? 1.18 : versionLens === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const impactScore = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const reviewDays = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const changeCount = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const releaseRisk = Math.round(selectedRecord.primary * modeMultiplier + reviewStrictness);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(reviewStrictness / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { impactScore, reviewDays, changeCount, releaseRisk, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, reviewStrictness]);

  const selectLeadRecord = () => setSelectedSectionId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setVersionLens((value) => value === "baseline" ? "diff-review" : value === "diff-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-diff task-012-policy-diff-viewer" aria-label="Build a policy diff viewer">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal diff handoff</p>
          <h1>Build a policy diff viewer</h1>
          <p className="lead">A local-only policy diff for sections with protected records, Policy area, Version lens, Clause search, Changed only, and Review strictness.</p>
        </div>
        <span className="status-pill">Policy release review</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local diff controls">
        <label>
          Policy area
          <select value={policyArea} onChange={(event) => setPolicyArea(event.target.value)} aria-label="Policy area">
            <option value="all">All sections</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Version lens
          <select value={versionLens} onChange={(event) => setVersionLens(event.target.value)} aria-label="Version lens">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Clause search
          <input value={clauseSearch} onChange={(event) => setClauseSearch(event.target.value)} aria-label="Clause search" placeholder="ID, owner, or name" />
        </label>
        <label>
          Review strictness
          <input type="range" min="0" max="100" value={reviewStrictness} onChange={(event) => setReviewStrictness(Number(event.target.value))} aria-label="Review strictness" />
        </label>
        <button type="button" aria-pressed={changedOnly} onClick={() => setChangedOnly((value) => !value)}>Changed only</button>
        <button type="button" onClick={selectLeadRecord}>Select lead section</button>
        <button type="button" onClick={cycleMode}>Cycle Version lens</button>
      </section>

      <section className="metric-grid" aria-label="Derived diff metrics">
        <article className="metric-card"><span>Impact score</span><strong>{formatMetric(summaryMetrics.impactScore)}</strong><small>{visibleRecords.length} visible sections</small></article>
        <article className="metric-card"><span>Review days</span><strong>{formatMetric(summaryMetrics.reviewDays)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Change count</span><strong>{formatMetric(summaryMetrics.changeCount)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Policy release review</span><strong>{formatMetric(summaryMetrics.releaseRisk)}</strong><small>{versionLens} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="section list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedSectionId ? "active" : ""}`} onClick={() => setSelectedSectionId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-diff" aria-label="policy diff">
          <div className="surface-head">
            <p className="eyebrow">policy diff</p>
            <h2>Split Diff</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-diff`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Policy release review"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + reviewStrictness, 100)}%` }} /></div>
          <p className="muted">release review / clause notes / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected section inspector">
          <p className="eyebrow">Selected section</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Impact score</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Review days</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Version lens</span><strong>{versionLens}</strong></div>
          </div>
          <p className="muted">Workflow note: Changed only and Review strictness are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
