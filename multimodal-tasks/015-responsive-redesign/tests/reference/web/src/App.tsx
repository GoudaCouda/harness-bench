import { useMemo, useState } from "react";
import rawIssues from "./data/localRecords.json";

type Issue = { id: string; label: string; area: string; x: number; y: number; w: number; h: number; severity: string };
const issues = rawIssues as Issue[];
const presets = { desktop: 900, tablet: 680, mobile: 390 };

function App() {
  const [device, setDevice] = useState<keyof typeof presets>("desktop");
  const [width, setWidth] = useState(900);
  const [showOverflow, setShowOverflow] = useState(true);
  const [selectedId, setSelectedId] = useState("RESP-NAV");
  const selected = issues.find((issue) => issue.id === selectedId) ?? issues[0];
  const activeWidth = device === "desktop" ? width : presets[device];
  const visible = showOverflow ? issues : issues.filter((issue) => issue.severity === "review");
  const reviewCount = visible.filter((issue) => issue.severity === "review").length;
  const markerArea = Math.round(visible.reduce((sum, issue) => sum + issue.w * issue.h, 0));
  return <main className="app-shell" aria-label="Responsive visual inspector"><header className="topbar"><div><p className="eyebrow">Responsive review</p><h1>Viewport overflow inspector</h1><p className="lead">Resize a local page preview and inspect protected overflow markers tied to exact visual regions.</p></div></header><section className="controls" aria-label="Responsive inspector controls"><label>Device preset<select aria-label="Device preset" value={device} onChange={(event) => setDevice(event.target.value as keyof typeof presets)}><option value="desktop">Desktop</option><option value="tablet">Tablet</option><option value="mobile">Mobile</option></select></label><label>Viewport width<input aria-label="Viewport width" type="range" min="320" max="900" value={width} onChange={(event) => setWidth(Number(event.target.value))}/></label><button type="button" aria-pressed={showOverflow} onClick={() => setShowOverflow((value) => !value)}>Show overflow markers</button><button type="button" onClick={() => setWidth(390)}>Snap to 390</button></section><section className="metrics" aria-label="Responsive metrics"><article className="metric"><span>Viewport width</span><strong>{activeWidth}</strong><small>{device}</small></article><article className="metric"><span>Overflow markers</span><strong>{visible.length}</strong><small>Visible issues</small></article><article className="metric"><span>Review breakpoints</span><strong>{reviewCount}</strong><small>Review severity</small></article><article className="metric"><span>Marked area</span><strong>{markerArea}</strong><small>Percent grid units</small></article></section><section className="workspace"><section className="panel"><p className="eyebrow">Device frame</p><div className="frame-wrap"><figure className="device-frame" data-testid="responsive-frame" style={{ width: `${activeWidth}px` }}><img src="/responsive-target.svg" alt="Synthetic responsive product page" />{visible.map((issue) => <button type="button" key={issue.id} className={`marker ${issue.id === selectedId ? "active" : ""}`} data-issue-id={issue.id} style={{ left: `${issue.x}%`, top: `${issue.y}%`, width: `${issue.w}%`, height: `${issue.h}%` }} onClick={() => setSelectedId(issue.id)}><strong>{issue.id}</strong></button>)}</figure></div></section><aside className="inspector" aria-live="polite" aria-label="Responsive issue detail"><p className="eyebrow">Issue detail</p><h2>{selected.id} - {selected.label}</h2><div className="detail-grid"><div className="fact"><span>Area</span><strong>{selected.area}</strong></div><div className="fact"><span>Severity</span><strong>{selected.severity}</strong></div><div className="fact"><span>Coordinates</span><strong>{selected.x}, {selected.y}</strong></div><div className="fact"><span>Frame</span><strong>{activeWidth}</strong></div></div><code>{selected.id} breakpoint marker at {selected.x}/{selected.y}</code></aside></section></main>;
}
export default App;
