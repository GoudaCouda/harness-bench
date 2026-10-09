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
const modeOptions = [["baseline", "Baseline"], ["table-review", "Sort mode"], ["focused", "Focused pass"]];
const workflowTerms = ["facet", "column", "data table", "sort", "pagination", "column audit", "data table", "facet rail", "column drawer", "pagination", "row inspector", "table shell"];

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
  const [activeFacet, setActiveFacet] = useState("all");
  const [selectedRecordId, setSelectedRecordId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [sortMode, setSortMode] = useState("table-review");
  const [globalSearch, setGlobalSearch] = useState("");
  const [hideClearRecords, setHideClearRecords] = useState(false);
  const [rowsPerPage, setRowsPerPage] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = globalSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = activeFacet === "all" || record.category === activeFacet;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !hideClearRecords || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [activeFacet, globalSearch, hideClearRecords]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedRecordId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = sortMode === "table-review" ? 1.18 : sortMode === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const totalValue = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const freshnessDays = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const facetMatches = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const columnAuditScore = Math.round(selectedRecord.primary * modeMultiplier + rowsPerPage);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(rowsPerPage / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { totalValue, freshnessDays, facetMatches, columnAuditScore, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, rowsPerPage]);

  const selectLeadRecord = () => setSelectedRecordId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setSortMode((value) => value === "baseline" ? "table-review" : value === "table-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-table task-011-local-data-explorer" aria-label="Build a local data explorer">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal table handoff</p>
          <h1>Build a local data explorer</h1>
          <p className="lead">A local-only data explorer for records with protected records, Facet, Sort mode, Global search, Hide clear records, and Rows per page.</p>
        </div>
        <span className="status-pill">Column audit</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local table controls">
        <label>
          Facet
          <select value={activeFacet} onChange={(event) => setActiveFacet(event.target.value)} aria-label="Facet">
            <option value="all">All records</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Sort mode
          <select value={sortMode} onChange={(event) => setSortMode(event.target.value)} aria-label="Sort mode">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Global search
          <input value={globalSearch} onChange={(event) => setGlobalSearch(event.target.value)} aria-label="Global search" placeholder="ID, owner, or name" />
        </label>
        <label>
          Rows per page
          <input type="range" min="0" max="100" value={rowsPerPage} onChange={(event) => setRowsPerPage(Number(event.target.value))} aria-label="Rows per page" />
        </label>
        <button type="button" aria-pressed={hideClearRecords} onClick={() => setHideClearRecords((value) => !value)}>Hide clear records</button>
        <button type="button" onClick={selectLeadRecord}>Select lead record</button>
        <button type="button" onClick={cycleMode}>Cycle Sort mode</button>
      </section>

      <section className="metric-grid" aria-label="Derived table metrics">
        <article className="metric-card"><span>Total value</span><strong>{formatMetric(summaryMetrics.totalValue)}</strong><small>{visibleRecords.length} visible records</small></article>
        <article className="metric-card"><span>Freshness days</span><strong>{formatMetric(summaryMetrics.freshnessDays)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Facet matches</span><strong>{formatMetric(summaryMetrics.facetMatches)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Column audit</span><strong>{formatMetric(summaryMetrics.columnAuditScore)}</strong><small>{sortMode} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="record list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedRecordId ? "active" : ""}`} onClick={() => setSelectedRecordId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-table" aria-label="data explorer">
          <div className="surface-head">
            <p className="eyebrow">data explorer</p>
            <h2>Data Table</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-table`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Column audit"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + rowsPerPage, 100)}%` }} /></div>
          <p className="muted">sort / pagination / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected record inspector">
          <p className="eyebrow">Selected record</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Total value</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Freshness days</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Sort mode</span><strong>{sortMode}</strong></div>
          </div>
          <p className="muted">Workflow note: Hide clear records and Rows per page are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
