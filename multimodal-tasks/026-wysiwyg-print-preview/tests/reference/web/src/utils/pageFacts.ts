export type PageFact = {
  /** Folio printed at the foot of the page. */
  page: number;
  /** Word count printed under the page title. */
  words: number;
  /** Page center, as a percentage of the spread image width. */
  x: number;
  /** Page center, as a percentage of the spread image height. */
  y: number;
};

// Read from web/public/print-pages.png (1800 x 1280 px, "Harbor Review · print preview", letter · 100%).
export const pageFacts: Record<string, PageFact> = {
  "PAGE-1": { page: 1, words: 180, x: 26.0, y: 40.0 },
  "PAGE-2": { page: 2, words: 420, x: 74.0, y: 40.0 },
  "PAGE-3": { page: 3, words: 360, x: 26.0, y: 78.0 },
  "PAGE-4": { page: 4, words: 90, x: 74.0, y: 78.0 },
};

export const publicationTitle = "Harbor Review";

export const paperSizes = ["letter", "a4", "legal"] as const;
export type PaperSize = (typeof paperSizes)[number];
