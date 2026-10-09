import { useState } from "react";
import rawRecords from "./data/localRecords.json";
import { cueFacts, cueLanes, type CueLane } from "./utils/cueFacts";
import { cn } from "./utils/cn";

type CueRecord = { id: string; label: string };
type Cue = CueRecord & { ms: number; amplitude: number; x: number; y: number };
type DroppedCue = { id: string; lane: CueLane };

const cues: Cue[] = (rawRecords as CueRecord[])
  .filter((record) => cueFacts[record.id])
  .map((record) => ({ ...record, ...cueFacts[record.id] }));

function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [lane, setLane] = useState<CueLane>("mix");
  const [dropped, setDropped] = useState<DroppedCue[]>([]);

  const selected = cues.find((cue) => cue.id === selectedId) ?? null;
  const droppedCues = dropped
    .map((entry) => ({ entry, cue: cues.find((cue) => cue.id === entry.id) }))
    .filter((item): item is { entry: DroppedCue; cue: Cue } => Boolean(item.cue))
    .sort((a, b) => a.cue.ms - b.cue.ms);
  const spanMs = droppedCues.length ? droppedCues[droppedCues.length - 1].cue.ms - droppedCues[0].cue.ms : 0;
  const playheadX = selected ? selected.x : cues[0]?.x ?? 0;

  const dropSelected = () => {
    if (!selectedId) return;
    setDropped((current) => [...current.filter((entry) => entry.id !== selectedId), { id: selectedId, lane }]);
  };

  return (
    <main className="app-shell" aria-label="Waveform cue editor workspace">
      <header className="topbar">
        <p className="eyebrow">Waveform cue editor</p>
        <h1>Lane A synthetic mix cue sheet</h1>
        <p className="lead">Select a cue crosshair on the waveform, choose a cue lane, and drop cues to build the cue list and its time span.</p>
      </header>

      <section className="controls" aria-label="Cue controls">
        <label>
          Cue lane
          <select value={lane} onChange={(event) => setLane(event.target.value as CueLane)}>
            {cueLanes.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </select>
        </label>
        <button type="button" onClick={dropSelected} disabled={!selected}>
          Drop cue
        </button>
        <button type="button" onClick={() => setDropped([])} disabled={!dropped.length}>
          Clear cues
        </button>
        <p className="status" aria-live="polite">Active lane: {lane}</p>
      </section>

      <section className="workspace">
        <figure className="board-panel" aria-label="Waveform">
          <div className="board wave-board" data-testid="wave-board">
            <img src="/waveform.png" alt="Waveform of the lane A mix with four cue crosshairs" draggable={false} />
            <div className="playhead" data-testid="playhead" style={{ left: `${playheadX}%` }} aria-hidden="true" />
            {cues.map((cue) => (
              <button
                type="button"
                key={cue.id}
                data-cue-id={cue.id}
                className={cn("marker", cue.id === selectedId && "selected", dropped.some((entry) => entry.id === cue.id) && "flagged")}
                style={{ left: `${cue.x}%`, top: `${cue.y}%` }}
                aria-pressed={cue.id === selectedId}
                aria-label={`${cue.label} (${cue.id}) at ${cue.ms} ms`}
                onClick={() => setSelectedId(cue.id)}
              >
                <span className="marker-dot" aria-hidden="true" />
                <span className="marker-id">{cue.id}</span>
              </button>
            ))}
          </div>
          <figcaption className="caption">
            Playhead at {selected ? `${selected.ms} ms (${selected.id})` : "start"}; marker rings show dropped cues.
          </figcaption>
        </figure>

        <aside className="side">
          <section className="panel" aria-live="polite" aria-label="Selected cue details">
            <p className="eyebrow">Selected cue</p>
            {selected ? (
              <>
                <h2>{selected.label}</h2>
                <dl className="facts">
                  <div><dt>Cue id</dt><dd>{selected.id}</dd></div>
                  <div><dt>Time</dt><dd>{selected.ms} ms</dd></div>
                  <div><dt>Envelope amplitude</dt><dd>{selected.amplitude.toFixed(2)}</dd></div>
                  <div><dt>Status</dt><dd>{dropped.some((entry) => entry.id === selected.id) ? "Dropped" : "Not dropped"}</dd></div>
                </dl>
              </>
            ) : (
              <p className="empty">Choose a cue crosshair on the waveform.</p>
            )}
          </section>

          <section className="panel" aria-label="Dropped cue summary">
            <div className="metrics">
              <div className="metric"><span>Cue count</span><strong>{droppedCues.length}</strong></div>
              <div className="metric"><span>Span ms</span><strong>{spanMs}</strong></div>
            </div>
            <p className="eyebrow">Cue list</p>
            {droppedCues.length ? (
              <ol className="item-list">
                {droppedCues.map(({ entry, cue }) => (
                  <li key={cue.id}>{cue.id} {cue.label} {cue.ms} ms / {entry.lane}</li>
                ))}
              </ol>
            ) : (
              <p className="empty">No cues dropped.</p>
            )}
          </section>

          <section className="panel" aria-label="All cues">
            <p className="eyebrow">Cues on the waveform</p>
            <ul className="pick-list">
              {cues.map((cue) => (
                <li key={cue.id}>
                  <button type="button" className={cn(cue.id === selectedId && "active")} onClick={() => setSelectedId(cue.id)}>
                    <span>{cue.label}</span>
                    <small>{cue.id} / {cue.ms} ms / amplitude {cue.amplitude.toFixed(2)}</small>
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
