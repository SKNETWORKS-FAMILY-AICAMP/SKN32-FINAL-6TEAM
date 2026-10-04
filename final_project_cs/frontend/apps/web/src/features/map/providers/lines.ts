import type { MapLine } from "../model";

/**
 * How a route line looks, for the three providers alike. A line whose road is not known (`dashed`) is paler and dashed, so it never
 * reads as a real road. The colour is the theme's (`--color-primary`), read where the map is drawn — an SDK paints its own lines and
 * cannot take a CSS variable.
 */
export interface LineStyle { color: string; weight: number; opacity: number; dash: [number, number] | null }

/** The theme's primary colour as the browser resolves it; a closed-form fallback when the page has none (a test double). */
function themeColor(container: HTMLElement): string {
  try { return getComputedStyle(container).getPropertyValue("--color-primary").trim() || "#2f6f4f"; }
  catch { return "#2f6f4f"; }
}

export function lineStyle(container: HTMLElement, line: MapLine): LineStyle {
  const color = themeColor(container);
  return line.dashed ? { color, weight: 4, opacity: 0.55, dash: [8, 10] } : { color, weight: 5, opacity: 0.85, dash: null };
}

/** Presentation-only updates must not redraw the lines. */
export function linesKey(lines: MapLine[]): string {
  return JSON.stringify(lines.map(({ id, points, dashed }) => [id, dashed, points.map(({ lat, lng }) => [lat, lng])]));
}
