import { useMemo, useState } from "react";
import rawRecords from "./data/localRecords.json";
import { bandLegend, districtFacts, type RateBand } from "./utils/districtFacts";
import { cn } from "./utils/cn";

type DistrictRecord = { id: string; name: string };
type District = DistrictRecord & { rate: number; band: RateBand; x: number; y: number };
type BandFilter = "all" | RateBand;

const districts: District[] = (rawRecords as DistrictRecord[])
  .filter((record) => districtFacts[record.id])
  .map((record) => ({ ...record, ...districtFacts[record.id] }));

function App() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [pinnedIds, setPinnedIds] = useState<string[]>([]);
  const [bandFilter, setBandFilter] = useState<BandFilter>("all");

  const selected = districts.find((district) => district.id === selectedId) ?? null;
  const pinned = pinnedIds.map((id) => districts.find((district) => district.id === id)).filter(Boolean) as District[];
  const visible = districts.filter((district) => bandFilter === "all" || district.band === bandFilter);
  // Rates are printed with one decimal, so average in integer tenths to avoid float drift (16.55 -> 16.6).
  const meanRate = useMemo(() => {
    if (!pinned.length) return "--";
    const tenths = pinned.reduce((sum, district) => sum + Math.round(district.rate * 10), 0);
    return (Math.round(tenths / pinned.length) / 10).toFixed(1);
  }, [pinned]);

  const pinSelected = () => {
    if (!selectedId) return;
    setPinnedIds((current) => (current.includes(selectedId) ? current : [...current, selectedId]));
  };

  return (
    <main className="app-shell" aria-label="Choropleth district map workspace">
      <header className="topbar">
        <p className="eyebrow">Choropleth map</p>
        <h1>Harborline district rate survey</h1>
        <p className="lead">Select a surveyed district on the map, filter by rate band, and pin districts to compare their mean rate.</p>
      </header>

      <section className="controls" aria-label="Map controls">
        <label>
          Rate band
          <select value={bandFilter} onChange={(event) => setBandFilter(event.target.value as BandFilter)}>
            <option value="all">all</option>
            <option value="high">high</option>
            <option value="mid">mid</option>
            <option value="low">low</option>
          </select>
        </label>
        <button type="button" onClick={pinSelected} disabled={!selected}>
          Pin district
        </button>
        <button type="button" onClick={() => setPinnedIds([])} disabled={!pinnedIds.length}>
          Clear pins
        </button>
      </section>

      <section className="workspace">
        <figure className="map-panel" aria-label="District map">
          <div className="map-board" data-testid="map-board">
            <img src="/districts.png" alt="Choropleth map of Harborline districts shaded by rate band" draggable={false} />
            {districts.map((district) => {
              const isPinned = pinnedIds.includes(district.id);
              const inBand = bandFilter === "all" || district.band === bandFilter;
              return (
                <button
                  type="button"
                  key={district.id}
                  data-region-id={district.id}
                  className={cn("marker", `band-${district.band}`, district.id === selectedId && "selected", isPinned && "pinned", !inBand && "muted")}
                  style={{ left: `${district.x}%`, top: `${district.y}%` }}
                  aria-pressed={district.id === selectedId}
                  aria-label={`${district.name} (${district.id})`}
                  onClick={() => setSelectedId(district.id)}
                >
                  <span className="marker-dot" aria-hidden="true" />
                  <span className="marker-id">{district.id}</span>
                </button>
              );
            })}
          </div>
          <figcaption className="legend" aria-label="Map legend">
            <strong>Legend</strong>
            {bandLegend.map((item) => (
              <span key={item.band} className="legend-item">
                <i className={cn("swatch", `band-${item.band}`)} aria-hidden="true" />
                {item.label}
              </span>
            ))}
          </figcaption>
        </figure>

        <aside className="side">
          <section className="panel detail" aria-live="polite" aria-label="Selected district details">
            <p className="eyebrow">Selected district</p>
            {selected ? (
              <>
                <h2>{selected.name}</h2>
                <dl className="facts">
                  <div><dt>District id</dt><dd>{selected.id}</dd></div>
                  <div><dt>Rate</dt><dd>{selected.rate.toFixed(1)}</dd></div>
                  <div><dt>Band</dt><dd className={cn("band-tag", `band-${selected.band}`)}>{selected.band}</dd></div>
                  <div><dt>Status</dt><dd>{pinnedIds.includes(selected.id) ? "Pinned" : "Not pinned"}</dd></div>
                </dl>
              </>
            ) : (
              <p className="empty">Choose a district marker on the map.</p>
            )}
          </section>

          <section className="panel" aria-label="Pinned district summary">
            <div className="metrics">
              <div className="metric"><span>Pinned count</span><strong>{pinned.length}</strong></div>
              <div className="metric"><span>Mean rate</span><strong>{meanRate}</strong></div>
            </div>
            <p className="eyebrow">Pinned districts</p>
            {pinned.length ? (
              <ul className="pin-list">
                {pinned.map((district) => (
                  <li key={district.id}>{district.id} {district.name} {district.rate.toFixed(1)}</li>
                ))}
              </ul>
            ) : (
              <p className="empty">No districts pinned.</p>
            )}
          </section>

          <section className="panel" aria-label="District list">
            <p className="eyebrow">Districts in band: {bandFilter}</p>
            <ul className="district-list">
              {visible.map((district) => (
                <li key={district.id}>
                  <button type="button" className={cn(district.id === selectedId && "active")} onClick={() => setSelectedId(district.id)}>
                    <span>{district.name}</span>
                    <small>{district.id} / rate {district.rate.toFixed(1)} / {district.band}</small>
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
