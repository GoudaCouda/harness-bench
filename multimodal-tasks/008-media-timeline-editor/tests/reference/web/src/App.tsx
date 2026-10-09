import { useMemo, useState } from "react";
import rawClips from "./data/localRecords.json";

type Clip = { id: string; title: string; track: "Video" | "Audio" | "Graphics"; start: number; duration: number; owner: string; status: string };
const clips = rawClips as Clip[];
const tracks: Clip["track"][] = ["Video", "Audio", "Graphics"];
const duration = 100;

function App() {
  const [selectedId, setSelectedId] = useState("CLIP-BROLL");
  const [currentTime, setCurrentTime] = useState(20);
  const [trimIn, setTrimIn] = useState(18);
  const [trimOut, setTrimOut] = useState(46);
  const [playing, setPlaying] = useState(false);
  const selected = clips.find((clip) => clip.id === selectedId) ?? clips[0];
  const reviewClips = useMemo(() => clips.filter((clip) => clip.status !== "clear"), []);
  const selectedTrackSeconds = clips.filter((clip) => clip.track === selected.track).reduce((sum, clip) => sum + clip.duration, 0);
  const trimLength = Math.max(0, trimOut - trimIn);
  return (
    <main className="app-shell" aria-label="Timeline seek trim editor">
      <header className="topbar"><div><p className="eyebrow">Media timeline</p><h1>Timeline seek and trim editor</h1><p className="lead">Scrub the playhead, select clip blocks, and set trim in/out on protected local clip records.</p></div></header>
      <section className="controls" aria-label="Transport and trim controls">
        <button type="button" aria-pressed={playing} onClick={() => setPlaying((value) => !value)}>{playing ? "Pause" : "Play"}</button>
        <label>Current time<input aria-label="Current time" type="range" min="0" max="100" value={currentTime} onChange={(event) => setCurrentTime(Number(event.target.value))} /></label>
        <button type="button" onClick={() => setTrimIn(currentTime)}>Set trim in</button>
        <button type="button" onClick={() => setTrimOut(currentTime)}>Set trim out</button>
      </section>
      <section className="metrics" aria-label="Timeline metrics"><article className="metric"><span>Current time</span><strong>{currentTime}s</strong><small>Playhead position</small></article><article className="metric"><span>Trim range</span><strong>{trimIn}-{trimOut}s</strong><small>{trimLength}s selected</small></article><article className="metric"><span>Selected clip</span><strong>{selected.id}</strong><small>{selected.title}</small></article><article className="metric"><span>Review clips</span><strong>{reviewClips.length}</strong><small>Non-clear items</small></article></section>
      <section className="workspace"><section className="panel"><p className="eyebrow">Editable timeline</p><div className="timeline" data-testid="timeline-board">{tracks.map((track) => <div className="track" key={track} aria-label={`${track} track`}><span className="track-label">{track}</span>{clips.filter((clip) => clip.track === track).map((clip) => <button type="button" className={`clip ${clip.id === selectedId ? "active" : ""}`} data-clip-id={clip.id} key={clip.id} style={{ left: `${clip.start}%`, width: `${clip.duration}%` }} onClick={() => setSelectedId(clip.id)}><strong>{clip.id}</strong><small>{clip.title}</small></button>)}</div>)}<div className="trim-band" data-testid="trim-band" style={{ left: `${trimIn}%`, width: `${trimLength}%` }} /><div className="playhead" data-testid="playhead" style={{ left: `${currentTime}%` }} /></div></section><aside className="inspector" aria-live="polite" aria-label="Selected clip detail"><p className="eyebrow">Selected clip detail</p><h2>{selected.id} - {selected.title}</h2><div className="detail-grid"><div className="fact"><span>Track</span><strong>{selected.track}</strong></div><div className="fact"><span>Owner</span><strong>{selected.owner}</strong></div><div className="fact"><span>Start</span><strong>{selected.start}</strong></div><div className="fact"><span>Duration</span><strong>{selected.duration}</strong></div></div><pre>{selected.id} trim {trimIn} to {trimOut}; {selectedTrackSeconds} seconds on {selected.track}</pre></aside></section>
    </main>
  );
}
export default App;
