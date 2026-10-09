import { useState } from "react";
import rawRecords from "./data/localRecords.json";
import { pageFacts, paperSizes, publicationTitle, type PaperSize } from "./utils/pageFacts";
import { cn } from "./utils/cn";

type PageRecord = { id: string; title: string };
type PrintPage = PageRecord & { page: number; words: number; x: number; y: number };

const pages: PrintPage[] = (rawRecords as PageRecord[])
  .filter((record) => pageFacts[record.id])
  .map((record) => ({ ...record, ...pageFacts[record.id] }));

function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pinnedIds, setPinnedIds] = useState<string[]>([]);
  const [paper, setPaper] = useState<PaperSize>("letter");

  const selected = pages.find((page) => page.id === selectedId) ?? null;
  const pinned = pinnedIds
    .map((id) => pages.find((page) => page.id === id))
    .filter(Boolean)
    .sort((a, b) => a!.page - b!.page) as PrintPage[];
  const wordTotal = pinned.reduce((sum, page) => sum + page.words, 0);

  const pinSelected = () => {
    if (!selectedId) return;
    setPinnedIds((current) => (current.includes(selectedId) ? current : [...current, selectedId]));
  };

  return (
    <main className="app-shell" aria-label="Print preview workspace">
      <header className="topbar">
        <p className="eyebrow">WYSIWYG print preview</p>
        <h1>{publicationTitle} print spread</h1>
        <p className="lead">Select a page in the protected print preview, choose a paper size, and pin pages to total their word counts.</p>
      </header>

      <section className="controls" aria-label="Print controls">
        <label>
          Paper size
          <select value={paper} onChange={(event) => setPaper(event.target.value as PaperSize)}>
            {paperSizes.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <button type="button" onClick={pinSelected} disabled={!selected}>
          Pin page
        </button>
        <button type="button" onClick={() => setPinnedIds([])} disabled={!pinnedIds.length}>
          Clear pins
        </button>
        <p className="status" aria-live="polite">Paper: {paper} / 100%</p>
      </section>

      <div className="running-header" data-testid="running-header" role="status">
        <span>{publicationTitle}{selected ? ` / ${selected.page}` : ""}</span>
        <span>{selected ? selected.title : `${pages.length} pages`} · {paper}</span>
      </div>

      <section className="workspace">
        <figure className="board-panel" aria-label="Print spread">
          <div className="board print-board" data-testid="print-board">
            <img src="/print-pages.png" alt="Print preview spread of four pages: Abstract, Methods, Results, Notes" draggable={false} />
            {pages.map((page) => (
              <button
                type="button"
                key={page.id}
                data-page-id={page.id}
                className={cn("marker", page.id === selectedId && "selected", pinnedIds.includes(page.id) && "flagged")}
                style={{ left: `${page.x}%`, top: `${page.y}%` }}
                aria-pressed={page.id === selectedId}
                aria-label={`${page.title} (${page.id})`}
                onClick={() => setSelectedId(page.id)}
              >
                <span className="marker-dot" aria-hidden="true" />
                <span className="marker-id">{page.id}</span>
              </button>
            ))}
          </div>
          <figcaption className="caption">Dashed rings mark pinned pages; the running header follows the selected page.</figcaption>
        </figure>

        <aside className="side">
          <section className="panel" aria-live="polite" aria-label="Selected page details">
            <p className="eyebrow">Selected page</p>
            {selected ? (
              <>
                <h2>{selected.title}</h2>
                <dl className="facts">
                  <div><dt>Page id</dt><dd>{selected.id}</dd></div>
                  <div><dt>Page number</dt><dd>{selected.page}</dd></div>
                  <div><dt>Word count</dt><dd>{selected.words}</dd></div>
                  <div><dt>Status</dt><dd>{pinnedIds.includes(selected.id) ? "Pinned" : "Not pinned"}</dd></div>
                </dl>
              </>
            ) : (
              <p className="empty">Choose a page in the print spread.</p>
            )}
          </section>

          <section className="panel" aria-label="Pinned page summary">
            <div className="metrics">
              <div className="metric"><span>Pinned count</span><strong>{pinned.length}</strong></div>
              <div className="metric"><span>Word total</span><strong>{wordTotal}</strong></div>
            </div>
            <p className="eyebrow">Pinned pages</p>
            {pinned.length ? (
              <ul className="item-list">
                {pinned.map((page) => (
                  <li key={page.id}>{page.id} {page.title} / page {page.page} / {page.words} words</li>
                ))}
              </ul>
            ) : (
              <p className="empty">No pages pinned.</p>
            )}
          </section>

          <section className="panel" aria-label="Page list">
            <p className="eyebrow">Pages</p>
            <ul className="pick-list">
              {pages.map((page) => (
                <li key={page.id}>
                  <button type="button" className={cn(page.id === selectedId && "active")} onClick={() => setSelectedId(page.id)}>
                    <span>{page.title}</span>
                    <small>{page.id} / page {page.page} / {page.words} words</small>
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
