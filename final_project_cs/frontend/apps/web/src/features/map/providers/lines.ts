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

/** The theme colour each kind of route is drawn in (`[2026-10-06 사용자 지시]` 지하철은 파랑 …). Shared with the legend over the map, which reads the same names. */
export const LINE_TONE_VARIABLE: Record<NonNullable<MapLine["mode"]>, string> = {
  subway: "--color-adjusted", mixed: "--color-adjusted", bus: "--color-success", taxi: "--color-warning", walk: "--color-muted", bike: "--color-muted", unknown: "--color-primary",
};

function toneColor(container: HTMLElement, mode: MapLine["mode"]): string {
  if (!mode) return themeColor(container);
  try { return getComputedStyle(container).getPropertyValue(LINE_TONE_VARIABLE[mode]).trim() || themeColor(container); }
  catch { return themeColor(container); }
}

export function lineStyle(container: HTMLElement, line: MapLine): LineStyle {
  const color = toneColor(container, line.mode);
  return line.dashed ? { color, weight: 4, opacity: 0.55, dash: [8, 10] } : { color, weight: 5, opacity: 0.85, dash: null };
}

/** Presentation-only updates must not redraw the lines. */
export function linesKey(lines: MapLine[]): string {
  return JSON.stringify(lines.map(({ id, points, dashed, mode }) => [id, dashed, mode ?? null, points.map(({ lat, lng }) => [lat, lng])]));
}
