import type { Coordinates, MapPoint, MapView } from "./model";

/**
 * `[2026-10-05 사용자 선택 — 지도 단추 · 가장자리 마커 안 B]` The maths the map's own buttons need, kept apart from any map SDK: every provider (Leaflet, Google, Naver) says what it shows as a `MapView`
 * (the corners of the view and its size in px), and the scale ruler and the chips for stops out of view are worked out from that alone. All three draw Web Mercator, so the corners are enough.
 * Pure - tested without a browser.
 */
const EARTH_RADIUS_M = 6_371_000;
const rad = (degrees: number) => (degrees * Math.PI) / 180;
const mercatorY = (lat: number) => Math.log(Math.tan(Math.PI / 4 + rad(lat) / 2));

/** Where a coordinate stands in the view, in px from its top-left corner (outside 0..width / 0..height when it is out of view). */
export function toPixels(view: MapView, at: Coordinates): { x: number; y: number } {
  const x = ((at.lng - view.west) / (view.east - view.west)) * view.width;
  const top = mercatorY(view.north), bottom = mercatorY(view.south);
  const y = ((top - mercatorY(at.lat)) / (top - bottom)) * view.height;
  return { x, y };
}

/** Metres on the ground that one px of the view covers (at its middle). */
export function metersPerPixel(view: MapView): number {
  const middle = (view.north + view.south) / 2;
  return (Math.abs(view.east - view.west) * 111_320 * Math.cos(rad(middle))) / view.width;
}

export function distanceM(a: Coordinates, b: Coordinates): number {
  const dLat = rad(b.lat - a.lat), dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
}

/** 「850m」 · 「1.2km」 · 「12km」 */
export function formatDistance(meters: number): string {
  if (meters < 1000) return `${Math.max(10, Math.round(meters / 10) * 10)}m`;
  const km = meters / 1000;
  return `${km < 10 ? km.toFixed(1).replace(/\.0$/, "") : Math.round(km)}km`;
}

/** The ruler: the longest round distance (1 · 2 · 5 × a power of ten) whose bar is at most `maxPx` wide; `px` is the bar's length. */
export function niceScale(view: MapView, maxPx = 34): { meters: number; px: number; label: string } | null {
  const perPx = metersPerPixel(view);
  if (!Number.isFinite(perPx) || perPx <= 0) return null;
  const limit = perPx * maxPx;
  const power = 10 ** Math.floor(Math.log10(limit));
  const meters = [5, 2, 1].map((step) => step * power).find((candidate) => candidate <= limit) ?? power;
  return { meters, px: Math.round(meters / perPx), label: formatDistance(meters).replace(/^(\d+)(m|km)$/, "$1$2") };
}

/** A stop that is out of view, drawn as a chip at the edge of the visible map pointing at it (stops close together share one). */
export interface EdgeChip {
  ids: string[];
  /** What the pins say (the order number, or the letter of a candidate), in the order of the day. */
  labels: string[];
  /** Where the chip stands, in px from the view's top-left corner. */
  x: number;
  y: number;
  /** Degrees, 0 = to the right, 90 = down. */
  angle: number;
  /** Metres from the middle of the visible map to the nearest stop of the chip. */
  distanceM: number;
}

export interface EdgeArea {
  /** Px at the top that a bar floats over (no stop is "visible" there, and no chip stands there). */
  top?: number;
  /** Px at the bottom that something floats over (the rounded top of the sheet): no stop is "visible" there and no chip stands there. */
  bottom?: number;
  /** Px at the right kept free for the map's own buttons (a chip never stands over them). */
  rightKeep?: number;
}

/** A chip stands this far inside the edge (px): its own half-width sideways (a chip like 「3 · 2.3km」 is about 80 px wide) and its half-height up and down, and a little air. */
const CHIP_INSET_X = 46;
const CHIP_INSET_Y = 18;
/** Chips closer than this (px) become one. */
const GROUP_PX = 52;
const MAX_CHIPS = 5;

/**
 * Which stops are out of the visible map (below the bar at the top, inside the view), where their chips stand and how far away they are. A stop is out of view when its pin could not be seen:
 * the coordinate is outside the view, or under the top bar. Stops shown muted (the context of the change screen) have no chip.
 */
export function edgeChips(view: MapView, points: readonly MapPoint[], area: EdgeArea = {}): EdgeChip[] {
  if (!(view.width > 0 && view.height > 0) || view.east === view.west || view.north === view.south) return [];
  const top = area.top ?? 0;
  const rect = { left: 0, top, right: view.width, bottom: view.height - (area.bottom ?? 0) };
  const centre = { x: (rect.left + rect.right) / 2, y: (rect.top + rect.bottom) / 2 };
  const middle: Coordinates = { lat: (view.north + view.south) / 2, lng: (view.east + view.west) / 2 };
  const found = points.flatMap((point) => {
    if (point.tone === "muted") return [];
    const at = toPixels(view, point.coordinates);
    if (at.x >= rect.left && at.x <= rect.right && at.y >= rect.top && at.y <= rect.bottom) return [];
    const dx = at.x - centre.x, dy = at.y - centre.y;
    const halfW = (rect.right - rect.left) / 2 - CHIP_INSET_X, halfH = (rect.bottom - rect.top) / 2 - CHIP_INSET_Y;
    const t = Math.min(dx === 0 ? Infinity : halfW / Math.abs(dx), dy === 0 ? Infinity : halfH / Math.abs(dy));
    let x = centre.x + dx * t;
    const y = centre.y + dy * t;
    if (area.rightKeep && y < top + 140) x = Math.min(x, view.width - area.rightKeep - CHIP_INSET_X);   // the buttons stand at the top right
    return [{ id: point.id, label: point.label ?? String(point.order), x, y, angle: (Math.atan2(dy, dx) * 180) / Math.PI, distance: distanceM(middle, point.coordinates), order: point.order }];
  }).sort((a, b) => a.order - b.order);
  const groups: EdgeChip[] = [];
  for (const entry of found) {
    const near = groups.find((group) => Math.hypot(group.x - entry.x, group.y - entry.y) < GROUP_PX);
    if (near) { near.ids.push(entry.id); near.labels.push(entry.label); near.distanceM = Math.min(near.distanceM, entry.distance); }
    else groups.push({ ids: [entry.id], labels: [entry.label], x: entry.x, y: entry.y, angle: entry.angle, distanceM: entry.distance });
  }
  return groups.sort((a, b) => a.distanceM - b.distanceM).slice(0, MAX_CHIPS);
}
