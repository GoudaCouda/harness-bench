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
const modeOptions = [["baseline", "Baseline"], ["dashboard-review", "Forecast mode"], ["focused", "Focused pass"]];
const workflowTerms = ["cohort", "channel mix", "revenue desk", "risk queue", "sponsorship review", "forecast review", "dashboard", "command desk", "revenue console", "cohort rail", "risk queue", "sponsor panel"];

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
  const [activeCohort, setActiveCohort] = useState("all");
  const [selectedCampaignId, setSelectedCampaignId] = useState(localRecords[1]?.id ?? localRecords[0].id);
  const [forecastMode, setForecastMode] = useState("dashboard-review");
  const [creatorSearch, setCreatorSearch] = useState("");
  const [reviewQueueOnly, setReviewQueueOnly] = useState(false);
  const [sponsorPressure, setSponsorPressure] = useState(50);

  const visibleRecords = useMemo(() => {
    const normalizedQuery = creatorSearch.trim().toLowerCase();
    return localRecords.filter((record) => {
      const categoryMatch = activeCohort === "all" || record.category === activeCohort;
      const queryMatch = !normalizedQuery || `${record.id} ${record.name} ${record.owner} ${record.category}`.toLowerCase().includes(normalizedQuery);
      const toggleMatch = !reviewQueueOnly || record.status !== "clear";
      return categoryMatch && queryMatch && toggleMatch;
    });
  }, [activeCohort, creatorSearch, reviewQueueOnly]);

  const rankedRecords = useMemo(() => [...visibleRecords].sort((a, b) => b.primary - a.primary), [visibleRecords]);
  const selectedRecord = localRecords.find((record) => record.id === selectedCampaignId) ?? rankedRecords[0] ?? localRecords[0];
  const modeMultiplier = forecastMode === "dashboard-review" ? 1.18 : forecastMode === "focused" ? 0.9 : 1;

  const summaryMetrics = useMemo(() => {
    const channelRevenue = visibleRecords.reduce((sum, record) => sum + record.primary, 0);
    const growthAverage = Math.round(visibleRecords.reduce((sum, record) => sum + record.secondary, 0) / Math.max(visibleRecords.length, 1));
    const sponsorshipRisk = visibleRecords.filter((record) => record.status === "review").length + new Set(visibleRecords.map((record) => record.owner)).size;
    const pressureAdjustedRevenue = Math.round(selectedRecord.primary * modeMultiplier + sponsorPressure);
    const ownerSpread = new Set(visibleRecords.map((record) => record.owner)).size;
    const anyWatch = visibleRecords.some((record) => record.status === "watch");
    const allNamed = visibleRecords.every((record) => record.name.length > 0);
    const previewSample = rankedRecords.slice(0, 3).map((record) => record.id).join(" / ");
    const syntheticCurve = Math.round(Math.sin(sponsorPressure / 20) * 10 + 50);
    const redlinePreview = selectedRecord.name.replace(/ /g, " + ");
    return { channelRevenue, growthAverage, sponsorshipRisk, pressureAdjustedRevenue, ownerSpread, anyWatch, allNamed, previewSample, syntheticCurve, redlinePreview };
  }, [visibleRecords, rankedRecords, selectedRecord, modeMultiplier, sponsorPressure]);

  const selectLeadRecord = () => setSelectedCampaignId(rankedRecords[0]?.id ?? selectedRecord.id);
  const cycleMode = () => setForecastMode((value) => value === "baseline" ? "dashboard-review" : value === "dashboard-review" ? "focused" : "baseline");

  return (
    <main className="app-shell shell-dashboard task-001-creator-revenue-dashboard" aria-label="Build a creator revenue command desk">
      <header className="topbar">
        <div>
          <p className="eyebrow">HarnessBench multimodal dashboard handoff</p>
          <h1>Build a creator revenue command desk</h1>
          <p className="lead">A local-only revenue console for campaigns with protected records, Channel cohort, Forecast mode, Creator search, Review queue only, and Sponsor pressure.</p>
        </div>
        <span className="status-pill">Sponsorship risk review</span>
      </header>

      <section className="term-rail" aria-label="Workflow terms">
        {workflowTerms.map((term) => <span className="tool-chip" key={term}>{term}</span>)}
      </section>

      <section className="control-strip" aria-label="Local dashboard controls">
        <label>
          Channel cohort
          <select value={activeCohort} onChange={(event) => setActiveCohort(event.target.value)} aria-label="Channel cohort">
            <option value="all">All campaigns</option>
            {categories.map((category) => <option key={category} value={category}>{category}</option>)}
          </select>
        </label>
        <label>
          Forecast mode
          <select value={forecastMode} onChange={(event) => setForecastMode(event.target.value)} aria-label="Forecast mode">
            {modeOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label>
          Creator search
          <input value={creatorSearch} onChange={(event) => setCreatorSearch(event.target.value)} aria-label="Creator search" placeholder="ID, owner, or name" />
        </label>
        <label>
          Sponsor pressure
          <input type="range" min="0" max="100" value={sponsorPressure} onChange={(event) => setSponsorPressure(Number(event.target.value))} aria-label="Sponsor pressure" />
        </label>
        <button type="button" aria-pressed={reviewQueueOnly} onClick={() => setReviewQueueOnly((value) => !value)}>Review queue only</button>
        <button type="button" onClick={selectLeadRecord}>Select lead campaign</button>
        <button type="button" onClick={cycleMode}>Cycle Forecast mode</button>
      </section>

      <section className="metric-grid" aria-label="Derived dashboard metrics">
        <article className="metric-card"><span>Net revenue</span><strong>{formatMetric(summaryMetrics.channelRevenue)}</strong><small>{visibleRecords.length} visible campaigns</small></article>
        <article className="metric-card"><span>Audience growth</span><strong>{formatMetric(summaryMetrics.growthAverage)}</strong><small>Average from current evidence</small></article>
        <article className="metric-card"><span>Review backlog</span><strong>{formatMetric(summaryMetrics.sponsorshipRisk)}</strong><small>{summaryMetrics.ownerSpread} owners represented</small></article>
        <article className="metric-card"><span>Sponsorship risk review</span><strong>{formatMetric(summaryMetrics.pressureAdjustedRevenue)}</strong><small>{forecastMode} with {summaryMetrics.syntheticCurve} signal</small></article>
      </section>

      <section className="workflow-grid">
        <section className="record-panel" aria-label="campaign list">
          {rankedRecords.map((record) => (
            <button key={record.id} type="button" className={`record-button ${record.id === selectedCampaignId ? "active" : ""}`} onClick={() => setSelectedCampaignId(record.id)}>
              <strong>{record.id} - {record.name}</strong>
              <small>{record.category} / {record.owner} / {record.status}</small>
            </button>
          ))}
        </section>

        <section className="surface surface-dashboard" aria-label="revenue console">
          <div className="surface-head">
            <p className="eyebrow">revenue console</p>
            <h2>Dashboard</h2>
            <p>{summaryMetrics.previewSample || "No visible records"}</p>
          </div>
          <div className="surface-board">
            {rankedRecords.slice(0, 4).map((record, index) => (
              <article className={`surface-card card-dashboard`} key={record.id}>
                <span>{index + 1}</span>
                <strong>{record.name}</strong>
                <small>{record.category} / {record.secondary}</small>
              </article>
            ))}
          </div>
          <div className="meter" aria-label="Sponsorship risk review"><span style={{ width: `${Math.min(Math.abs(selectedRecord.secondary) + sponsorPressure, 100)}%` }} /></div>
          <p className="muted">risk queue / sponsorship review / {summaryMetrics.redlinePreview}</p>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected campaign inspector">
          <p className="eyebrow">Selected campaign</p>
          <h2>{selectedRecord.name}</h2>
          <p className={statusClass(selectedRecord.status)}>{selectedRecord.id} is {selectedRecord.status} for {selectedRecord.owner}.</p>
          <div className="detail-grid">
            <div className="fact"><span>Category</span><strong>{selectedRecord.category}</strong></div>
            <div className="fact"><span>Net revenue</span><strong>{formatMetric(selectedRecord.primary)}</strong></div>
            <div className="fact"><span>Audience growth</span><strong>{formatMetric(selectedRecord.secondary)}</strong></div>
            <div className="fact"><span>Forecast mode</span><strong>{forecastMode}</strong></div>
          </div>
          <p className="muted">Workflow note: Review queue only and Sponsor pressure are local reversible staging controls.</p>
        </aside>
      </section>
    </main>
  );
}

export default App;
