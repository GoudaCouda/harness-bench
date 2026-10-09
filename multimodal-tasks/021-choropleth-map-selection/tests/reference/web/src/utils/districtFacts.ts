export type RateBand = "high" | "mid" | "low";

export type DistrictFact = {
  rate: number;
  band: RateBand;
  /** Labeled centroid dot, as a percentage of the map image width. */
  x: number;
  /** Labeled centroid dot, as a percentage of the map image height. */
  y: number;
};

// Read from web/public/districts.png (1800 x 1240 px). Positions are the
// centroid dots; rate is the printed value; band is the fill color matched
// against the map legend (high >= 14.0, mid 8.0 - 13.9, low < 8.0).
export const districtFacts: Record<string, DistrictFact> = {
  "REG-NORTH": { rate: 18.4, band: "high", x: 27.9, y: 24.0 },
  "REG-EAST": { rate: 9.1, band: "mid", x: 67.9, y: 29.9 },
  "REG-WEST": { rate: 6.2, band: "low", x: 21.9, y: 64.0 },
  "REG-SOUTH": { rate: 14.7, band: "high", x: 61.9, y: 69.9 },
};

export const bandLegend: Array<{ band: RateBand; label: string }> = [
  { band: "high", label: "high ≥ 14.0" },
  { band: "mid", label: "mid 8.0 – 13.9" },
  { band: "low", label: "low < 8.0" },
];
