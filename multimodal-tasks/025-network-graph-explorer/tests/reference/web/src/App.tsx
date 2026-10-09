import { useState } from "react";
import rawRecords from "./data/localRecords.json";
import { kindLegend, neighborsOf, nodeFacts, type NodeKind } from "./utils/graphFacts";
import { cn } from "./utils/cn";

type NodeRecord = { id: string; label: string };
type GraphNode = NodeRecord & { kind: NodeKind; x: number; y: number; neighbors: string[] };
type KindFilter = "all" | NodeKind;

const nodes: GraphNode[] = (rawRecords as NodeRecord[])
  .filter((record) => nodeFacts[record.id])
  .map((record) => ({ ...record, ...nodeFacts[record.id], neighbors: neighborsOf(record.id) }));

function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pinnedIds, setPinnedIds] = useState<string[]>([]);
  const [kindFilter, setKindFilter] = useState<KindFilter>("all");

  const selected = nodes.find((node) => node.id === selectedId) ?? null;
  const pinned = pinnedIds.map((id) => nodes.find((node) => node.id === id)).filter(Boolean) as GraphNode[];
  // Distinct nodes adjacent to the pinned set, not counting the pinned nodes themselves.
  const neighborIds = [...new Set(pinned.flatMap((node) => node.neighbors))].filter((id) => !pinnedIds.includes(id)).sort();
  const visible = nodes.filter((node) => kindFilter === "all" || node.kind === kindFilter);
  const labelOf = (id: string) => nodes.find((node) => node.id === id)?.label ?? id;

  const pinSelected = () => {
    if (!selectedId) return;
    setPinnedIds((current) => (current.includes(selectedId) ? current : [...current, selectedId]));
  };

  return (
    <main className="app-shell" aria-label="Network graph explorer workspace">
      <header className="topbar">
        <p className="eyebrow">Network graph</p>
        <h1>Pipeline node explorer</h1>
        <p className="lead">Select a node card on the graph, filter by node kind, and pin nodes to highlight every neighbor connected by an edge.</p>
      </header>

      <section className="controls" aria-label="Graph controls">
        <label>
          Node kind
          <select value={kindFilter} onChange={(event) => setKindFilter(event.target.value as KindFilter)}>
            <option value="all">all</option>
            <option value="source">source</option>
            <option value="bridge">bridge</option>
            <option value="sink">sink</option>
          </select>
        </label>
        <button type="button" onClick={pinSelected} disabled={!selected}>
          Pin node
        </button>
        <button type="button" onClick={() => setPinnedIds([])} disabled={!pinnedIds.length}>
          Clear pins
        </button>
        <p className="status" aria-live="polite">Kind shown: {kindFilter}</p>
      </section>

      <section className="workspace">
        <figure className="board-panel" aria-label="Node graph">
          <div className="board graph-board" data-testid="graph-board">
            <img src="/graph.png" alt="Directed graph of four pipeline node cards connected by arrows" draggable={false} />
            {nodes.map((node) => {
              const inKind = kindFilter === "all" || node.kind === kindFilter;
              return (
                <button
                  type="button"
                  key={node.id}
                  data-node-id={node.id}
                  className={cn(
                    "marker",
                    `kind-${node.kind}`,
                    node.id === selectedId && "selected",
                    pinnedIds.includes(node.id) && "flagged",
                    neighborIds.includes(node.id) && "neighbor",
                    !inKind && "muted",
                  )}
                  style={{ left: `${node.x}%`, top: `${node.y}%` }}
                  aria-pressed={node.id === selectedId}
                  aria-label={`${node.label} (${node.id})`}
                  onClick={() => setSelectedId(node.id)}
                >
                  <span className="marker-dot" aria-hidden="true" />
                  <span className="marker-id">{node.id}</span>
                </button>
              );
            })}
          </div>
          <figcaption className="caption">
            <strong>node kind</strong>
            {kindLegend.map((item) => (
              <span key={item.kind} className="caption-item">
                <i className="swatch" style={{ background: item.color }} aria-hidden="true" />
                {item.kind}
              </span>
            ))}
            <span className="caption-item"><i className="swatch neighbor-swatch" aria-hidden="true" />neighbor of a pinned node</span>
          </figcaption>
        </figure>

        <aside className="side">
          <section className="panel" aria-live="polite" aria-label="Selected node details">
            <p className="eyebrow">Selected node</p>
            {selected ? (
              <>
                <h2>{selected.label}</h2>
                <dl className="facts">
                  <div><dt>Node id</dt><dd>{selected.id}</dd></div>
                  <div><dt>Kind</dt><dd>{selected.kind}</dd></div>
                  <div><dt>Degree</dt><dd>{selected.neighbors.length}</dd></div>
                  <div><dt>Neighbors</dt><dd>{selected.neighbors.map((id) => `${id} ${labelOf(id)}`).join(", ")}</dd></div>
                </dl>
              </>
            ) : (
              <p className="empty">Choose a node card on the graph.</p>
            )}
          </section>

          <section className="panel" aria-label="Pinned node summary">
            <div className="metrics">
              <div className="metric"><span>Pinned count</span><strong>{pinned.length}</strong></div>
              <div className="metric"><span>Neighbor count</span><strong>{neighborIds.length}</strong></div>
            </div>
            <p className="eyebrow">Pinned nodes</p>
            {pinned.length ? (
              <ul className="item-list">
                {pinned.map((node) => (
                  <li key={node.id}>{node.id} {node.label} / {node.kind}</li>
                ))}
              </ul>
            ) : (
              <p className="empty">No nodes pinned.</p>
            )}
            {neighborIds.length > 0 && <p className="empty">Neighbors: {neighborIds.join(", ")}</p>}
          </section>

          <section className="panel" aria-label="Node list">
            <p className="eyebrow">Nodes shown: {kindFilter}</p>
            <ul className="pick-list">
              {visible.map((node) => (
                <li key={node.id}>
                  <button type="button" className={cn(node.id === selectedId && "active")} onClick={() => setSelectedId(node.id)}>
                    <span>{node.label}</span>
                    <small>{node.id} / {node.kind} / {node.neighbors.length} edges</small>
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
