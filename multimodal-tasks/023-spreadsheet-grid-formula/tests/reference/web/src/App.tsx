import { useState } from "react";
import rawRecords from "./data/localRecords.json";
import { cellFacts, evaluate, expandRange, formulaFunctions, pendingFormula, type FormulaFn } from "./utils/cellFacts";
import { cn } from "./utils/cn";

type CellRecord = { id: string; label: string };
type Cell = CellRecord & { value: number; kind: "input" | "formula"; x: number; y: number };

const cells: Cell[] = (rawRecords as CellRecord[])
  .filter((record) => cellFacts[record.id])
  .map((record) => ({ ...record, ...cellFacts[record.id] }));

const rangeText = pendingFormula.range.join(":");
const rangeValues = expandRange(pendingFormula.range)
  .map((address) => cells.find((cell) => cell.label === address))
  .filter((cell): cell is Cell => Boolean(cell) && cell!.kind === "input")
  .map((cell) => cell.value);

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}

function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [fn, setFn] = useState<FormulaFn>(pendingFormula.fn as FormulaFn);
  const [committed, setCommitted] = useState<{ fn: FormulaFn; result: number } | null>(null);

  const selected = cells.find((cell) => cell.id === selectedId) ?? null;
  const preview = evaluate(fn, rangeValues);
  const formulaText = `=${fn}(${rangeText})`;
  const cellValue = (cell: Cell) => (cell.kind === "formula" ? (committed ? committed.result : 0) : cell.value);
  const sheetTotal = cells.reduce((sum, cell) => sum + cellValue(cell), 0);
  const formulaCell = cells.find((cell) => cell.id === pendingFormula.cellId);

  const cellContent = (cell: Cell) =>
    cell.kind === "formula" ? `${committed ? `=${committed.fn}(${rangeText})` : formulaText}` : String(cell.value);

  return (
    <main className="app-shell" aria-label="Spreadsheet grid workspace">
      <header className="topbar">
        <p className="eyebrow">Spreadsheet grid</p>
        <h1>Sheet1 formula workbench</h1>
        <p className="lead">Select a cell in the protected grid, preview the pending function over its range, and commit it to update the sheet total.</p>
      </header>

      <section className="controls" aria-label="Sheet controls">
        <label>
          Formula
          <select value={fn} onChange={(event) => setFn(event.target.value as FormulaFn)}>
            {formulaFunctions.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <button type="button" onClick={() => setCommitted({ fn, result: preview })}>
          Commit formula
        </button>
        <button type="button" onClick={() => setCommitted(null)} disabled={!committed}>
          Clear sheet
        </button>
        <p className="status" aria-live="polite">Function: {fn} over {rangeText}</p>
      </section>

      <div className="formula-bar" data-testid="formula-bar" role="status">
        <span className="fx">fx</span>
        <code>{selected ? cellContent(selected) : formulaText}</code>
        <span className="address">{selected ? selected.label : formulaCell?.label}</span>
      </div>

      <section className="workspace">
        <figure className="board-panel" aria-label="Sheet grid">
          <div className="board grid-board" data-testid="grid-board">
            <img src="/grid-frame.png" alt="Sheet1 grid with cells A1, B1, A2 and a pending function in B2" draggable={false} />
            {cells.map((cell) => (
              <button
                type="button"
                key={cell.id}
                data-cell-id={cell.id}
                className={cn("marker", cell.id === selectedId && "selected", cell.kind === "formula" && committed && "flagged")}
                style={{ left: `${cell.x}%`, top: `${cell.y}%` }}
                aria-pressed={cell.id === selectedId}
                aria-label={`Cell ${cell.label} (${cell.id})`}
                onClick={() => setSelectedId(cell.id)}
              >
                <span className="marker-dot" aria-hidden="true" />
                <span className="marker-id">{cell.id}</span>
              </button>
            ))}
          </div>
          <figcaption className="caption">
            {formulaCell?.label} holds {committed ? `committed ${committed.fn}` : "a pending"} function over {rangeText}.
          </figcaption>
        </figure>

        <aside className="side">
          <section className="panel" aria-live="polite" aria-label="Selected cell details">
            <p className="eyebrow">Selected cell</p>
            {selected ? (
              <>
                <h2>{selected.label}</h2>
                <dl className="facts">
                  <div><dt>Cell id</dt><dd>{selected.id}</dd></div>
                  <div><dt>Address</dt><dd>{selected.label}</dd></div>
                  <div><dt>Current value</dt><dd>{formatNumber(cellValue(selected))}</dd></div>
                  <div><dt>Content</dt><dd>{selected.kind === "formula" && !committed ? `${cellContent(selected)} (pending)` : cellContent(selected)}</dd></div>
                </dl>
              </>
            ) : (
              <p className="empty">Choose a cell in the grid.</p>
            )}
          </section>

          <section className="panel" aria-label="Sheet summary">
            <div className="metrics">
              <div className="metric"><span>Preview</span><strong>{formatNumber(preview)}</strong></div>
              <div className="metric"><span>Sheet total</span><strong>{formatNumber(sheetTotal)}</strong></div>
            </div>
            <p className="empty">Preview {formulaText} = {formatNumber(preview)}. {committed ? `Committed ${committed.fn} = ${formatNumber(committed.result)}.` : "Not committed; the pending cell counts as 0."}</p>
          </section>

          <section className="panel" aria-label="All cells">
            <p className="eyebrow">Cells</p>
            <ul className="pick-list">
              {cells.map((cell) => (
                <li key={cell.id}>
                  <button type="button" className={cn(cell.id === selectedId && "active")} onClick={() => setSelectedId(cell.id)}>
                    <span>{cell.label}</span>
                    <small>{cell.id} / {cell.kind} / {cellContent(cell)}</small>
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
