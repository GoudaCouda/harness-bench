export type DiffSide = "before" | "after";
export type Severity = "review" | "watch" | "info";

export type DiffFact = {
  /** Window the crosshair is drawn in. */
  side: DiffSide;
  /** Badge color matched against the severity legend. */
  severity: Severity;
  /** Crosshair center, as a percentage of the pair image width. */
  x: number;
  /** Crosshair center, as a percentage of the pair image height. */
  y: number;
};

// Read from web/public/before-after.png (1800 x 1040 px; BEFORE checkout v12 left, AFTER checkout v13 right).
export const diffFacts: Record<string, DiffFact> = {
  "DIFF-NAV": { side: "before", severity: "review", x: 17.0, y: 23.9 },
  "DIFF-BTN": { side: "after", severity: "review", x: 68.9, y: 30.0 },
  "DIFF-PRICE": { side: "after", severity: "watch", x: 73.0, y: 62.0 },
  "DIFF-GAP": { side: "after", severity: "info", x: 73.0, y: 83.9 },
};

export const severityLegend: Array<{ severity: Severity; color: string }> = [
  { severity: "review", color: "#dc2626" },
  { severity: "watch", color: "#d97706" },
  { severity: "info", color: "#0369a1" },
];
