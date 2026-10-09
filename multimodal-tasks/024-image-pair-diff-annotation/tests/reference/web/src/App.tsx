import { useState } from "react";
import rawRecords from "./data/localRecords.json";
import { diffFacts, severityLegend, type DiffSide, type Severity } from "./utils/diffFacts";
import { cn } from "./utils/cn";

type DiffRecord = { id: string; label: string };
type Diff = DiffRecord & { side: DiffSide; severity: Severity; x: number; y: number };
type SideFilter = "all" | DiffSide;

const diffs: Diff[] = (rawRecords as DiffRecord[])
  .filter((record) => diffFacts[record.id])
  .map((record) => ({ ...record, ...diffFacts[record.id] }));

function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [markedIds, setMarkedIds] = useState<string[]>([]);
  const [sideFilter, setSideFilter] = useState<SideFilter>("all");
  const [hideMarks, setHideMarks] = useState(false);

  const selected = diffs.find((diff) => diff.id === selectedId) ?? null;
  const marked = markedIds.map((id) => diffs.find((diff) => diff.id === id)).filter(Boolean) as Diff[];
  const afterOnly = marked.filter((diff) => diff.side === "after").length;
  const visible = diffs.filter((diff) => sideFilter === "all" || diff.side === sideFilter);

  const markSelected = () => {
    if (!selectedId) return;
    setMarkedIds((current) => (current.includes(selectedId) ? current : [...current, selectedId]));
  };

  return (
    <main className="app-shell" aria-label="Before and after diff annotation workspace">
      <header className="topbar">
        <p className="eyebrow">Image pair diff</p>
        <h1>Checkout v12 before / v13 after review</h1>
        <p className="lead">Select a diff crosshair in the before or after window, filter by diff side, and mark diffs to track open review items.</p>
      </header>

      <section className="controls" aria-label="Review controls">
        <label>
          Diff side
          <select value={sideFilter} onChange={(event) => setSideFilter(event.target.value as SideFilter)}>
            <option value="all">all</option>
            <option value="before">before</option>
            <option value="after">after</option>
          </select>
        </label>
        <button type="button" onClick={markSelected} disabled={!selected}>
          Mark diff
        </button>
        <label className="check">
          <input type="checkbox" checked={hideMarks} onChange={(event) => setHideMarks(event.target.checked)} />
          Hide marks
        </label>
        <p className="status" aria-live="polite">Showing: {sideFilter}{hideMarks ? " / marks hidden" : ""}</p>
      </section>

      <section className="workspace">
        <figure className="board-panel" aria-label="Before and after pair">
          <div className="board diff-board" data-testid="diff-board">
            <img src="/before-after.png" alt="Checkout page before (v12) and after (v13) with four annotated diffs" draggable={false} />
            {!hideMarks && (
              <div className="overlay" aria-hidden="true">
                {marked.map((diff) => (
                  <span key={diff.id} className={cn("overlay-ring", `sev-${diff.severity}`)} style={{ left: `${diff.x}%`, top: `${diff.y}%` }} />
                ))}
              </div>
            )}
            {diffs.map((diff) => {
              const inSide = sideFilter === "all" || diff.side === sideFilter;
              return (
                <button
                  type="button"
                  key={diff.id}
                  data-diff-id={diff.id}
                  className={cn("marker", `sev-${diff.severity}`, diff.id === selectedId && "selected", !inSide && "muted")}
                  style={{ left: `${diff.x}%`, top: `${diff.y}%` }}
                  aria-pressed={diff.id === selectedId}
                  aria-label={`${diff.label} (${diff.id})`}
                  onClick={() => setSelectedId(diff.id)}
                >
                  <span className="marker-dot" aria-hidden="true" />
                  <span className="marker-id">{diff.id}</span>
                </button>
              );
            })}
          </div>
          <figcaption className="caption">
            <strong>severity</strong>
            {severityLegend.map((item) => (
              <span key={item.severity} className="caption-item">
                <i className="swatch" style={{ background: item.color }} aria-hidden="true" />
                {item.severity}
              </span>
            ))}
          </figcaption>
        </figure>

        <aside className="side">
          <section className="panel" aria-live="polite" aria-label="Selected diff details">
            <p className="eyebrow">Selected diff</p>
            {selected ? (
              <>
                <h2>{selected.label}</h2>
                <dl className="facts">
                  <div><dt>Diff id</dt><dd>{selected.id}</dd></div>
                  <div><dt>Side</dt><dd>{selected.side}</dd></div>
                  <div><dt>Severity</dt><dd className={cn("sev-tag", `sev-${selected.severity}`)}>{selected.severity}</dd></div>
                  <div><dt>Status</dt><dd>{markedIds.includes(selected.id) ? "Marked" : "Not marked"}</dd></div>
                </dl>
              </>
            ) : (
              <p className="empty">Choose a diff crosshair in the pair.</p>
            )}
          </section>

          <section className="panel" aria-label="Marked diff summary">
            <div className="metrics">
              <div className="metric"><span>Diff count</span><strong>{marked.length}</strong></div>
              <div className="metric"><span>After-only</span><strong>{afterOnly}</strong></div>
            </div>
            <p className="list-title">Open diffs</p>
            {marked.length ? (
              <ul className="item-list">
                {marked.map((diff) => (
                  <li key={diff.id}>{diff.id} {diff.label} / {diff.side} / {diff.severity}</li>
                ))}
              </ul>
            ) : (
              <p className="empty">No diffs marked.</p>
            )}
          </section>

          <section className="panel" aria-label="Diff list">
            <p className="eyebrow">Diffs shown: {sideFilter}</p>
            <ul className="pick-list">
              {visible.map((diff) => (
                <li key={diff.id}>
                  <button type="button" className={cn(diff.id === selectedId && "active")} onClick={() => setSelectedId(diff.id)}>
                    <span>{diff.label}</span>
                    <small>{diff.id} / {diff.side} / {diff.severity}</small>
                  </button>
                </li>
              ))}
            </ul>
          </section>
        </aside>
      </section>
    </main>
  );
}

export default App;
