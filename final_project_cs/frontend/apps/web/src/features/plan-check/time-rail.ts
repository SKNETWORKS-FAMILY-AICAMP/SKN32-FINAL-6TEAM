/**
 * `[2026-10-12 사용자 결정 — 멘토링 코멘트 「줄 길이에 실제 시간을 반영」]` The time each row of a day's timeline stands for, so the line at the left can be drawn to scale
 * (1 minute = `RAIL_PX_PER_MIN` px): a stop from its start to its end, the way to the next stop from the end of the stop before to the start of the next one.
 * Pure (no DOM): the screen measures the rows and draws the line from these spans (`rail-list.tsx`).
 */

/**
 * How long a minute is on the line. `[2026-10-13 사용자 결정 — 줄 간격 ④]` 0.8 px (90 minutes = 72 px; it was 1.2 px): a stop's card is as tall as its time (`rail-list.tsx`),
 * so the empty room under a short card stays inside its frame.
 */
export const RAIL_PX_PER_MIN = 0.8;
/** `[2026-10-13 ④]` Free time longer than this (waiting to leave, after arriving, or between two stops with no way known) is folded: drawn this short, with a break mark — its length is said in words. */
export const RAIL_FOLD_OVER_MIN = 60;
export const RAIL_FOLD_PX = 30;

/** The length of free time on the line: to scale, or folded when it is long. */
export function freePx(minutes: number): number {
  return minutes > RAIL_FOLD_OVER_MIN ? RAIL_FOLD_PX : Math.max(0, minutes) * RAIL_PX_PER_MIN;
}

/** One row as the line reads it: a stop (start and end) or the way after it (when it leaves and arrives). Minutes since midnight; null = not known. */
export type RailRow =
  | { kind: "stay"; start: number | null; end: number | null }
  | { kind: "move"; depart: number | null; arrive: number | null };

/** The minutes a row stands for (`from` to `to`); null where it is not known. */
export interface RailSpan { from: number | null; to: number | null }

/**
 * A stop ends at its end time. With no end it lasts until it is left: the way after it leaves, else the next stop starts — the last stop of a day with no end stays open (null).
 * A way lasts from the end of the stop before to the start of the next stop (waiting to leave, travelling and the free time after arriving are all in it).
 */
export function railSpans(rows: readonly RailRow[]): RailSpan[] {
  const spans: RailSpan[] = [];
  let lastStayTo: number | null = null;
  rows.forEach((row, index) => {
    const after = rows.slice(index + 1);
    const nextStart = (after.find((other) => other.kind === "stay") as Extract<RailRow, { kind: "stay" }> | undefined)?.start ?? null;
    if (row.kind === "move") {
      spans.push({ from: lastStayTo, to: nextStart });
      return;
    }
    let to = row.end;
    if (to === null) {
      const leave = after[0]?.kind === "move" ? after[0].depart : null;
      to = leave ?? nextStart;
    }
    // A time that runs back (past midnight, or typed wrong) cannot be drawn to scale: it is not known here.
    if (row.start !== null && to !== null && to < row.start) to = null;
    spans.push({ from: row.start, to });
    lastStayTo = to;
  });
  return spans;
}

/** The time → height pairs of a drawn day, in order. */
export interface RailPoint { minute: number; y: number }

/** Where a minute stands on a drawn day: between the two pairs around it, in proportion (space that stands for no time — a long card — is stepped over). Null past the last pair. */
export function railY(points: readonly RailPoint[], minute: number): number | null {
  for (let index = 0; index < points.length - 1; index++) {
    const a = points[index], b = points[index + 1];
    if (b.minute > a.minute && minute >= a.minute && minute < b.minute) return a.y + ((minute - a.minute) / (b.minute - a.minute)) * (b.y - a.y);
  }
  return null;
}
