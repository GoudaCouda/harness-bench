import { useMemo, useState } from "react";
import rawRecords from "./data/localRecords.json";

type Finding = { id: string; label: string; category: string; owner: string; severity: "watch" | "review"; x: number; y: number; w: number; h: number; fix: string };
const findings = rawRecords as Finding[];

function App() {
  const categories = useMemo(() => ["all", ...Array.from(new Set(findings.map((finding) => finding.category)))], []);
  const [category, setCategory] = useState("all");
  const [severity, setSeverity] = useState("all");
  const [showRemediations, setShowRemediations] = useState(false);
  const [selectedId, setSelectedId] = useState("A11Y-FORM");

  const visibleFindings = findings.filter((finding) => {
    const categoryMatch = category === "all" || finding.category === category;
    const severityMatch = severity === "all" || finding.severity === severity;
    return categoryMatch && severityMatch;
  });
  const selected = visibleFindings.find((finding) => finding.id === selectedId) ?? visibleFindings[0] ?? findings[0];
  const keyboardBlockers = visibleFindings.filter((finding) => finding.category === "keyboard" || finding.category === "focus" || finding.severity === "review").length;
  const annotatedArea = Math.round(visibleFindings.reduce((sum, finding) => sum + finding.w * finding.h, 0));
  const reviewSeverity = visibleFindings.filter((finding) => finding.severity === "review").length;

  return (
    <main className="app-shell" aria-label="Accessibility screenshot annotation workspace">
      <header className="topbar">
        <div>
          <p className="eyebrow">Accessibility annotation</p>
          <h1>Product page issue map</h1>
          <p className="lead">Overlay protected accessibility findings on the local target image, then filter by category or severity without moving the image.</p>
        </div>
      </header>

      <section className="controls" aria-label="Annotation controls">
        <label>Issue category<select aria-label="Issue category" value={category} onChange={(event) => setCategory(event.target.value)}>{categories.map((item) => <option key={item} value={item}>{item === "all" ? "All categories" : item}</option>)}</select></label>
        <label>Severity filter<select aria-label="Severity filter" value={severity} onChange={(event) => setSeverity(event.target.value)}><option value="all">All severities</option><option value="watch">watch</option><option value="review">review</option></select></label>
        <button type="button" aria-pressed={showRemediations} onClick={() => setShowRemediations((value) => !value)}>Show remediations</button>
      </section>

      <section className="metrics" aria-label="Annotation metrics">
        <article className="metric"><span>Visible findings</span><strong>{visibleFindings.length}</strong><small>{category} / {severity}</small></article>
        <article className="metric"><span>Review severity</span><strong>{reviewSeverity}</strong><small>Review markers visible</small></article>
        <article className="metric"><span>Keyboard blockers</span><strong>{keyboardBlockers}</strong><small>Focus and keyboard risks</small></article>
        <article className="metric"><span>Annotated area</span><strong>{annotatedArea}</strong><small>{showRemediations ? "Remediations shown" : "Markers only"}</small></article>
      </section>

      <section className="workspace">
        <section className="panel" aria-label="Annotated target image">
          <p className="eyebrow">Target image</p>
          <figure className="annotation-board" data-testid="annotation-board">
            <img src="/audit-target.svg" alt="Synthetic product checkout page accessibility target" />
            {visibleFindings.map((finding) => (
              <button
                key={finding.id}
                type="button"
                className={`marker ${finding.category} ${finding.id === selectedId ? "active" : ""}`}
                data-issue-id={finding.id}
                style={{ left: `${finding.x}%`, top: `${finding.y}%`, width: `${finding.w}%`, height: `${finding.h}%` }}
                onClick={() => setSelectedId(finding.id)}
                aria-label={`${finding.id} ${finding.label}`}
              >
                <strong>{finding.id}</strong>
              </button>
            ))}
          </figure>
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected finding detail">
          <p className="eyebrow">Selected finding</p>
          <h2>{selected.id} - {selected.label}</h2>
          <div className="detail-grid">
            <div className="fact"><span>Owner</span><strong>{selected.owner}</strong></div>
            <div className="fact"><span>Severity</span><strong>{selected.severity}</strong></div>
            <div className="fact"><span>Category</span><strong>{selected.category}</strong></div>
            <div className="fact"><span>Coordinates</span><strong>{selected.x}, {selected.y}</strong></div>
          </div>
          {showRemediations && <p className="remediation">Remediation: {selected.fix}</p>}
          <div className="finding-list" aria-label="Visible finding list">
            {visibleFindings.map((finding) => <button type="button" key={finding.id} onClick={() => setSelectedId(finding.id)}>{finding.id} - {finding.label}<small>{finding.category} / {finding.severity}</small></button>)}
          </div>
        </aside>
      </section>
    </main>
  );
}

export default App;
