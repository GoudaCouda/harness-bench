import { useMemo, useState } from "react";
import rawRecords from "./data/localRecords.json";

type Lane = "Backlog" | "In Progress" | "Review" | "Done";
type CardStatus = "blocked" | "active" | "ready" | "done";
type BuildCard = { id: string; title: string; lane: Lane; owner: string; status: CardStatus; estimate: number; blockers: number };

type MoveEvent = { id: string; from: Lane; to: Lane };

const initialCards = rawRecords as BuildCard[];
const lanes: Lane[] = ["Backlog", "In Progress", "Review", "Done"];

function App() {
  const [cards, setCards] = useState<BuildCard[]>(initialCards);
  const [selectedId, setSelectedId] = useState("KAN-101");
  const [history, setHistory] = useState<MoveEvent[]>([]);
  const selected = cards.find((card) => card.id === selectedId) ?? cards[0];

  const summaries = useMemo(() => {
    const blockedPoints = cards.filter((card) => card.status === "blocked").reduce((sum, card) => sum + card.estimate, 0);
    const reviewCount = cards.filter((card) => card.lane === "Review").length;
    const activeWip = cards.filter((card) => card.lane === "In Progress").reduce((sum, card) => sum + card.estimate, 0);
    const last = history[history.length - 1];
    return { blockedPoints, reviewCount, activeWip, lastMove: last ? `${last.id} ${last.from} to ${last.to}` : "No moves yet" };
  }, [cards, history]);

  const laneStats = (lane: Lane) => {
    const laneCards = cards.filter((card) => card.lane === lane);
    return { count: laneCards.length, estimate: laneCards.reduce((sum, card) => sum + card.estimate, 0), cards: laneCards };
  };

  const moveSelected = (to: Lane) => {
    const card = cards.find((item) => item.id === selectedId);
    if (!card || card.lane === to) return;
    setCards((current) => current.map((item) => item.id === selectedId ? { ...item, lane: to } : item));
    setHistory((current) => [...current, { id: selectedId, from: card.lane, to }]);
  };

  const undoLastMove = () => {
    const last = history[history.length - 1];
    if (!last) return;
    setCards((current) => current.map((item) => item.id === last.id ? { ...item, lane: last.from } : item));
    setSelectedId(last.id);
    setHistory((current) => current.slice(0, -1));
  };

  return (
    <main className="app-shell" aria-label="Kanban build repair board">
      <header className="topbar">
        <div>
          <p className="eyebrow">Build repair</p>
          <h1>Drag-aware Kanban build board</h1>
          <p className="lead">Move protected build cards through Backlog, In Progress, Review, and Done with deterministic fallback controls.</p>
        </div>
      </header>

      <section className="toolbar" aria-label="Selected card movement controls">
        <button type="button" className="primary-action" onClick={() => moveSelected("Review")}>Move selected to Review</button>
        <button type="button" onClick={() => moveSelected("Done")}>Move selected to Done</button>
        <button type="button" onClick={undoLastMove}>Undo last move</button>
        <label>Jump selected lane<select value={selected.lane} aria-label="Jump selected lane" onChange={(event) => moveSelected(event.target.value as Lane)}>{lanes.map((lane) => <option key={lane} value={lane}>{lane}</option>)}</select></label>
      </section>

      <section className="metrics" aria-label="Kanban movement metrics">
        <article className="metric"><span>Blocked points</span><strong>{summaries.blockedPoints}</strong><small>Blocked estimates remain visible</small></article>
        <article className="metric"><span>Review count</span><strong>{summaries.reviewCount}</strong><small>Cards currently in Review</small></article>
        <article className="metric"><span>Active WIP</span><strong>{summaries.activeWip}</strong><small>Estimate in In Progress</small></article>
        <article className="metric"><span>Last move</span><strong>{summaries.lastMove}</strong><small>{history.length} local moves</small></article>
      </section>

      <section className="workspace">
        <section className="board" aria-label="Kanban lanes">
          {lanes.map((lane) => {
            const stats = laneStats(lane);
            return (
              <section className="lane" aria-label={`${lane} lane`} key={lane}>
                <header><h2>{lane}</h2><span className="lane-count">{stats.count} cards / {stats.estimate} pts</span></header>
                <div className="card-list">
                  {stats.cards.map((card) => (
                    <button className={`card ${card.id === selectedId ? "active" : ""}`} type="button" key={card.id} onClick={() => setSelectedId(card.id)} draggable>
                      <strong>{card.id} - {card.title}</strong>
                      <small>{card.owner} / <span className={`status-${card.status}`}>{card.status}</span> / {card.estimate} pts / {card.blockers} blockers</small>
                    </button>
                  ))}
                </div>
              </section>
            );
          })}
        </section>

        <aside className="inspector" aria-live="polite" aria-label="Selected card detail">
          <p className="eyebrow">Selected card</p>
          <h2>{selected.id} - {selected.title}</h2>
          <div className="detail-grid">
            <div className="fact"><span>Owner</span><strong>{selected.owner}</strong></div>
            <div className="fact"><span>Status</span><strong>{selected.status}</strong></div>
            <div className="fact"><span>Lane</span><strong>{selected.lane}</strong></div>
            <div className="fact"><span>Estimate</span><strong>{selected.estimate}</strong></div>
            <div className="fact"><span>Blockers</span><strong>{selected.blockers}</strong></div>
            <div className="fact"><span>Card id</span><strong>{selected.id}</strong></div>
          </div>
          <ol className="history" aria-label="Action history">
            {history.length === 0 ? <li>No moves yet</li> : history.map((event, index) => <li key={`${event.id}-${index}`}>{event.id} moved from {event.from} to {event.to}</li>)}
          </ol>
        </aside>
      </section>
    </main>
  );
}

export default App;
