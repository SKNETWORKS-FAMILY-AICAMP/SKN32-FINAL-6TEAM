import { toPixels } from "./map-geometry";
import type { MapLine, MapPoint, MapView } from "./model";

type Pixel = { x: number; y: number };

/** Clip a segment to the visible map, including routes whose two ends are off screen. */
function clip(a: Pixel, b: Pixel, box: { left: number; right: number; top: number; bottom: number }) {
  const dx = b.x - a.x, dy = b.y - a.y;
  let start = 0, end = 1;
  const edges = [[-dx, a.x - box.left], [dx, box.right - a.x], [-dy, a.y - box.top], [dy, box.bottom - a.y]];
  for (const [p, q] of edges) {
    if (p === 0) { if (q < 0) return null; continue; }
    const at = q / p;
    if (p < 0) start = Math.max(start, at); else end = Math.min(end, at);
    if (start > end) return null;
  }
  return { a: { x: a.x + dx * start, y: a.y + dy * start }, b: { x: a.x + dx * end, y: a.y + dy * end }, length: Math.hypot(dx, dy) * (end - start) };
}

/** Names sit on a visible part of the real path at street zoom, clear of pins, chrome and other names. */
export function routeLabels(view: MapView | null, lines: readonly MapLine[], points: readonly MapPoint[], top = 0, bottom = 0) {
  if (!view || view.zoom < 15 || view.width < 144 || view.height < top + bottom + 48) return [];
  const box = { left: 68, right: view.width - 68, top: top + 20, bottom: view.height - bottom - 24 };
  const pins = points.map((point) => toPixels(view, point.coordinates));
  const labels: { id: string; mode: MapLine["mode"]; dashed: boolean; x: number; y: number }[] = [];
  for (const line of lines) {
    const path = line.points.map((point) => toPixels(view, point));
    const segments = path.slice(1).flatMap((point, index) => {
      const part = clip(path[index], point, box);
      return part && part.length > 0 ? [part] : [];
    });
    if (segments.reduce((sum, segment) => sum + segment.length, 0) < 80) continue;
    // The middle can be covered by a pin when just one end is visible. Try both quarters of the clipped path too.
    const candidates = segments.sort((a, b) => b.length - a.length).flatMap(({ a, b }) =>
      [0.5, 0.25, 0.75].map((part) => ({ x: a.x + (b.x - a.x) * part, y: a.y + (b.y - a.y) * part })));
    const spot = candidates.find((at) =>
      !pins.some((pin) => Math.abs(pin.x - at.x) < 96 && Math.abs(pin.y - at.y) < 48)
      && !labels.some((label) => Math.abs(label.x - at.x) < 136 && Math.abs(label.y - at.y) < 36));
    if (spot) labels.push({ id: line.id, mode: line.mode, dashed: line.dashed, x: spot.x, y: spot.y });
  }
  return labels;
}
