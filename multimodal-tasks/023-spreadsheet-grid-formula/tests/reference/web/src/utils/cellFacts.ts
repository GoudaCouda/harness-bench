export type CellFact = {
  /** Number printed in the cell; 0 for the pending formula cell. */
  value: number;
  kind: "input" | "formula";
  /** Cell center, as a percentage of the grid image width. */
  x: number;
  /** Cell center, as a percentage of the grid image height. */
  y: number;
};

// Read from web/public/grid-frame.png (1800 x 1120 px, Sheet1).
export const cellFacts: Record<string, CellFact> = {
  "CELL-A1": { value: 4, kind: "input", x: 22.0, y: 28.0 },
  "CELL-B1": { value: 11, kind: "input", x: 48.0, y: 28.0 },
  "CELL-A2": { value: 7, kind: "input", x: 22.0, y: 58.0 },
  "CELL-B2": { value: 0, kind: "formula", x: 48.0, y: 58.0 },
};

// The formula bar and cell B2 both show the pending formula =SUM(A1:A2).
export const pendingFormula = { cellId: "CELL-B2", fn: "SUM", range: ["A1", "A2"] as [string, string] };

export const formulaFunctions = ["SUM", "AVERAGE", "MIN", "MAX"] as const;
export type FormulaFn = (typeof formulaFunctions)[number];

export function evaluate(fn: FormulaFn, values: number[]): number {
  if (!values.length) return 0;
  if (fn === "SUM") return values.reduce((sum, value) => sum + value, 0);
  if (fn === "AVERAGE") return values.reduce((sum, value) => sum + value, 0) / values.length;
  if (fn === "MIN") return Math.min(...values);
  return Math.max(...values);
}

/** Expand an A1-style rectangular range such as A1:A2 into addresses. */
export function expandRange([start, end]: [string, string]): string[] {
  const parse = (address: string) => ({ col: address.charCodeAt(0), row: Number(address.slice(1)) });
  const a = parse(start);
  const b = parse(end);
  const out: string[] = [];
  for (let col = Math.min(a.col, b.col); col <= Math.max(a.col, b.col); col += 1) {
    for (let row = Math.min(a.row, b.row); row <= Math.max(a.row, b.row); row += 1) {
      out.push(`${String.fromCharCode(col)}${row}`);
    }
  }
  return out;
}
