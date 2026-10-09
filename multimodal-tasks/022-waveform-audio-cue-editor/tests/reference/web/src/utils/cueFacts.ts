export type CueFact = {
  /** Time printed next to the crosshair. */
  ms: number;
  /** Envelope height at the crosshair, read against the 0 - 1.0 amplitude axis. */
  amplitude: number;
  /** Crosshair center, as a percentage of the waveform image width. */
  x: number;
  /** Crosshair center, as a percentage of the waveform image height. */
  y: number;
};

// Read from web/public/waveform.png (1800 x 640 px, lane A, 2.6 s mono mix).
export const cueFacts: Record<string, CueFact> = {
  "CUE-INTRO": { ms: 0, amplitude: 0.12, x: 12.0, y: 45.0 },
  "CUE-VOX": { ms: 840, amplitude: 0.66, x: 37.0, y: 25.0 },
  "CUE-BRK": { ms: 1620, amplitude: 0.21, x: 60.0, y: 41.9 },
  "CUE-OUT": { ms: 2410, amplitude: 0.08, x: 84.0, y: 46.9 },
};

export const cueLanes = ["mix", "vocal", "fx"] as const;
export type CueLane = (typeof cueLanes)[number];
