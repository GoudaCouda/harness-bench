export type NodeKind = "source" | "bridge" | "sink";

export type NodeFact = {
  /** Dot color matched against the node kind legend. */
  kind: NodeKind;
  /** Card center, as a percentage of the graph image width. */
  x: number;
  /** Card center, as a percentage of the graph image height. */
  y: number;
};

// Read from web/public/graph.png (1800 x 1120 px).
export const nodeFacts: Record<string, NodeFact> = {
  "NODE-A": { kind: "source", x: 18.0, y: 30.0 },
  "NODE-B": { kind: "bridge", x: 50.0, y: 48.0 },
  "NODE-C": { kind: "sink", x: 82.0, y: 28.0 },
  "NODE-D": { kind: "sink", x: 78.0, y: 72.0 },
};

// Arrows drawn between cards (from -> to).
export const edges: Array<[string, string]> = [
  ["NODE-A", "NODE-C"],
  ["NODE-A", "NODE-B"],
  ["NODE-B", "NODE-C"],
  ["NODE-B", "NODE-D"],
];

export const kindLegend: Array<{ kind: NodeKind; color: string }> = [
  { kind: "source", color: "#10b981" },
  { kind: "bridge", color: "#6366f1" },
  { kind: "sink", color: "#f43f5e" },
];

export function neighborsOf(id: string): string[] {
  const out = new Set<string>();
  for (const [from, to] of edges) {
    if (from === id) out.add(to);
    if (to === id) out.add(from);
  }
  return [...out].sort();
}
