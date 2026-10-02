import type { Translate } from "@/lib/i18n";
import type { CheckResult, ItemStatus, MoveStatus, Review, ReviewItem, ReviewMove } from "@/lib/live/intake-review";

/**
 * What the finished check screen shows, decided from the server's `review` (2026-10-02 mockup, screens ③④ and after).
 * Components only draw these values.
 *
 * ★The server decides every verdict. Nothing here judges whether a place is open or a leg is reachable; an unknown value
 *   keeps the grey 「–」 and is never drawn as a check mark.
 */

/** The little round mark in front of a check line or a card (mockup `.mk`). */
export type MarkTone = "ok" | "adj" | "warn" | "bad" | "none";

export const MARK_TONE: Record<CheckResult, MarkTone> = { ok: "ok", filled: "adj", warn: "warn", bad: "bad", unknown: "none" };
export const MARK_GLYPH: Record<MarkTone, string> = { ok: "✓", adj: "✎", warn: "!", bad: "✕", none: "–" };

export function markLabel(tone: MarkTone, t: Translate): string {
  return { ok: t("통과", "Pass"), adj: t("채움", "Filled in"), warn: t("주의", "Caution"), bad: t("고쳐야 함", "Needs fixing"), none: t("아직 모름", "Not known yet") }[tone];
}

/** A card's own mark follows its status: kept = check, adjusted = pencil, review = caution. */
export function statusTone(status: ItemStatus | MoveStatus | null): MarkTone {
  switch (status) {
    case "keep": return "ok";
    case "adjusted": return "adj";
    case "review": return "warn";
    default: return "none";
  }
}

export function statusWord(status: ItemStatus | null, t: Translate): string {
  switch (status) {
    case "keep": return t("유지", "Kept");
    case "adjusted": return t("조정", "Adjusted");
    case "review": return t("확인 필요", "Needs review");
    default: return t("확인 중", "Checking");
  }
}

export const ITEM_ROW_LABEL: Record<string, readonly [ko: string, en: string]> = {
  place: ["장소", "Place"], time: ["시간", "Time"], hours: ["운영시간", "Hours"], closed: ["휴무일", "Closed"],
  route: ["경로", "Route"], mode: ["수단", "Mode"], arrival: ["도착", "Arrival"],
};

const WEEKDAY: readonly [ko: string, en: string][] = [["일", "Sun"], ["월", "Mon"], ["화", "Tue"], ["수", "Wed"], ["목", "Thu"], ["금", "Fri"], ["토", "Sat"]];

/** 「1일차」 + 「10.01 목」 — the day heading. A day the server could not date has no date part. */
export function dayHeading(day: number | null, date: string | null, t: Translate): { title: string; sub: string } {
  const title = day ? t(`${day}일차`, `Day ${day}`) : t("날짜 미정", "Date not set");
  const parsed = date ? new Date(`${date}T00:00:00`) : null;
  if (!parsed || Number.isNaN(parsed.getTime())) return { title, sub: "" };
  const [ko, en] = WEEKDAY[parsed.getDay()];
  return { title, sub: `${String(parsed.getMonth() + 1).padStart(2, "0")}.${String(parsed.getDate()).padStart(2, "0")} ${t(ko, en)}` };
}

export type TimelineEntry =
  | { kind: "day"; key: string; day: number | null; date: string | null }
  | { kind: "item"; key: string; item: ReviewItem; last: boolean }
  | { kind: "move"; key: string; move: ReviewMove };

/**
 * The list in the sheet: a heading per day, the stops in order, and between two stops of the same day the leg the server
 * measured (if it measured one). `last` marks the day's last stop — the rail ends there.
 */
export function timeline(review: Pick<Review, "items" | "moves">): TimelineEntry[] {
  const moveOf = new Map(review.moves.map((move) => [`${move.from}:${move.to}`, move]));
  const out: TimelineEntry[] = [];
  let lastDay: string | null = null;
  review.items.forEach((item, index) => {
    const dayKey = `${item.day ?? "none"}|${item.date ?? ""}`;
    if (dayKey !== lastDay) { out.push({ kind: "day", key: `day:${dayKey}`, day: item.day, date: item.date }); lastDay = dayKey; }
    const next = review.items[index + 1];
    const sameDayNext = next && `${next.day ?? "none"}|${next.date ?? ""}` === dayKey ? next : null;
    out.push({ kind: "item", key: `item:${item.id}`, item, last: !sameDayNext });
    const move = sameDayNext ? moveOf.get(`${item.id}:${sameDayNext.id}`) : undefined;
    if (move) out.push({ kind: "move", key: `move:${move.from}:${move.to}`, move });
  });
  return out;
}

/** The sheet's one-line summary: what is left for the customer, or that nothing is. */
export function headSummary(review: Pick<Review, "needs" | "ready">, t: Translate): { tone: MarkTone; text: string } {
  const { items, moves } = review.needs;
  if (items || moves) {
    const parts = [items ? t(`장소 ${items}곳`, `${items} ${items === 1 ? "place" : "places"}`) : "", moves ? t(`이동 ${moves}구간`, `${moves} ${moves === 1 ? "leg" : "legs"}`) : ""].filter(Boolean);
    return { tone: "warn", text: t(`${parts.join(" · ")} 확인 필요`, `${parts.join(" · ")} to review`) };
  }
  return { tone: "ok", text: t("고칠 곳이 없어요", "Nothing to fix") };
}

// ── the concept map ─────────────────────────────────────────────────

export interface PinSpot { id: string; x: number; y: number; located: boolean }

const KLAT = 111.32;
const KLON_AT_SEOUL = 88.22;

export interface GeoPoint { id: string; lat: number; lng: number }

/**
 * Real coordinates → percent of the concept map's area: north up, the same scale both ways, the points filling about 70% of it.
 * One point (or points on one spot) sit in the middle instead of blowing up.
 */
export function projectPoints(points: readonly GeoPoint[]): Map<string, { x: number; y: number }> {
  const out = new Map<string, { x: number; y: number }>();
  if (!points.length) return out;
  const px = (point: GeoPoint) => point.lng * KLON_AT_SEOUL;
  const py = (point: GeoPoint) => -point.lat * KLAT;
  const xs = points.map(px), ys = points.map(py);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const scale = 70 / Math.max(x1 - x0, y1 - y0, 0.6);
  const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2;
  for (const point of points) out.set(point.id, { x: 50 + (px(point) - cx) * scale, y: 50 + (py(point) - cy) * scale });
  return out;
}

const hasCoordinates = (item: ReviewItem) => typeof item.place?.latitude === "number" && typeof item.place?.longitude === "number";

/**
 * Where each stop of one day sits on the concept map (percent of the map area). Located stops are drawn from their real
 * coordinates; a stop without coordinates sits between its neighbours (or beside the only one) and is marked `located: false` —
 * the screen draws it as 「위치 미정」, not as a pin.
 */
export function projectDay(items: readonly ReviewItem[]): PinSpot[] {
  const placed = projectPoints(items.filter(hasCoordinates).map((item) => ({ id: item.id, lat: item.place!.latitude as number, lng: item.place!.longitude as number })));
  const spots = new Map<string, PinSpot>(items.filter((item) => placed.has(item.id)).map((item) => [item.id, { id: item.id, ...placed.get(item.id)!, located: true }]));
  items.forEach((item, index) => {
    if (spots.has(item.id)) return;
    const before = items.slice(0, index).reverse().find((other) => spots.get(other.id)?.located);
    const after = items.slice(index + 1).find((other) => spots.get(other.id)?.located);
    const a = before && spots.get(before.id), b = after && spots.get(after.id);
    const at = a && b ? { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 }
      : a ? { x: Math.min(88, a.x + 14), y: Math.min(86, a.y + 12) }
      : b ? { x: Math.max(12, b.x - 14), y: Math.max(14, b.y - 12) }
      : { x: 50, y: 50 };
    spots.set(item.id, { id: item.id, ...at, located: false });
  });
  return items.map((item) => spots.get(item.id)!);
}
