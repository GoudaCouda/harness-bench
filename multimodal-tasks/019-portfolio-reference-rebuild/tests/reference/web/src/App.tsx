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
const modeOptions = [["baseline", "Baseline"], ["portfolio-review", "Theme mode"], ["focused", "Focused pass"]];
const workflowTerms = ["portfolio", "case study", "project", "hero", "story section", "featured work", "hero", "portfolio grid", "case study", "project narrative", "theme preview", "featured work"];

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
  const [projectType, setProjectType] = useState("all");
  const [selectedCaseId, setSelectedCaseId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [themeMode, setThemeMode] = useState("portfolio-review");
  const [caseSearch, setCaseSearch] = useState("");
  const [featuredOnly, setFeaturedOnly] = useState(false);
  const [heroEmphasis, setHeroEmphasis] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = caseSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = projectType === "all" || record.category === projectType;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !featuredOnly || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [projectType, caseSearch, featuredOnly]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedCaseId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = themeMode === "portfolio-review" ? 1.18 : themeMode === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const portfolioImpact = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const deliveryWeeks = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const caseStudyCount = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const heroNarrative = Math.round(selectedRecord.primary * modeMultiplier + heroEmphasis);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(heroEmphasis / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { portfolioImpact, deliveryWeeks, caseStudyCount, heroNarrative, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, heroEmphasis]);

  const selectLeadRecord = () => setSelectedCaseId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setThemeMode((value) => value === "baseline" ? "portfolio-review" : value === "portfolio-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-portfolio task-019-portfolio-reference-rebuild" aria-label="Rebuild a portfolio reference page">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal portfolio handoff</p>
          <h1>Rebuild a portfolio reference page</h1>
          <p className="lead">A local-only portfolio case studies for projects with protected records, Project type, Theme mode, Project search, Featured only, and Hero emphasis.</p>
        </div>
        <span className="status-pill">Hero narrative</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local portfolio controls">
        <label>
          Project type
          <select value={projectType} onChange={(event) => setProjectType(event.target.value)} aria-label="Project type">
            <option value="all">All projects</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Theme mode
          <select value={themeMode} onChange={(event) => setThemeMode(event.target.value)} aria-label="Theme mode">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Project search
          <input value={caseSearch} onChange={(event) => setCaseSearch(event.target.value)} aria-label="Project search" placeholder="ID, owner, or name" />
        </label>
        <label>
          Hero emphasis
          <input type="range" min="0" max="100" value={heroEmphasis} onChange={(event) => setHeroEmphasis(Number(event.target.value))} aria-label="Hero emphasis" />
        </label>
        <button type="button" aria-pressed={featuredOnly} onClick={() => setFeaturedOnly((value) => !value)}>Featured only</button>
        <button type="button" onClick={selectLeadRecord}>Select lead project</button>
        <button type="button" onClick={cycleMode}>Cycle Theme mode</button>
      </section>

      <section className="metric-grid" aria-label="Derived portfolio metrics">
        <article className="metric-card"><span>Impact score</span><strong>{formatMetric(summaryMetrics.portfolioImpact)}</strong><small>{visibleRecords.length} visible projects</small></article>
        <article className="metric-card"><span>Delivery weeks</span><strong>{formatMetric(summaryMetrics.deliveryWeeks)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Case study count</span><strong>{formatMetric(summaryMetrics.caseStudyCount)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Hero narrative</span><strong>{formatMetric(summaryMetrics.heroNarrative)}</strong><small>{themeMode} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="project list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedCaseId ? "active" : ""}`} onClick={() => setSelectedCaseId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-portfolio" aria-label="portfolio case studies">
          <div className="surface-head">
            <p className="eyebrow">portfolio case studies</p>
            <h2>Hero</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-portfolio`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Hero narrative"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + heroEmphasis, 100)}%` }} /></div>
          <p className="muted">hero / story section / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected project inspector">
          <p className="eyebrow">Selected project</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Impact score</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Delivery weeks</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Theme mode</span><strong>{themeMode}</strong></div>
          </div>
          <p className="muted">Workflow note: Featured only and Hero emphasis are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
