import { timeline, type PlanCheckView, type PlanDay } from "./model";
import { formatHm, parseHm } from "./time-plan";

export interface InsertionPoint {
  key: string;
  anchorId: string;
  date: string;
  start: string;
  end: string;
  previous: string | null;
  next: string | null;
  side: "before-stop" | "before-move" | "after-stop";
}

const DEFAULT_STAY_MIN = 60;
const LAST_MINUTE = 23 * 60 + 59;

type Entry = ReturnType<typeof timeline>[number];

/**
 * Each visible seam belongs to one day, including both sides of a travel row.
 * ★`[2026-10-22 사용자 결정 — ST4F-720]` Stops marked for deletion (`removed`: the grey cards, and the legs into and out of them) no longer take every ＋ away. The seam right above a grey entry
 *   has none (null); the one right under a grey run is that gap's only ＋, named and timed from the stops around it as if the grey ones were gone.
 */
export function insertionPoints(view: PlanCheckView, day: PlanDay): InsertionPoint[];
export function insertionPoints(view: PlanCheckView, day: PlanDay, removed: ReadonlySet<string>): (InsertionPoint | null)[];
export function insertionPoints(view: PlanCheckView, day: PlanDay, removed: ReadonlySet<string> = new Set()): (InsertionPoint | null)[] {
  const all = timeline(view, day.day);
  const grey = (entry: Entry) => entry.type === "item" ? removed.has(entry.item.id) : removed.has(entry.move.fromId) || removed.has(entry.move.toId);
  const points = seams(all.filter((entry) => !grey(entry)), day);
  let at = 0;
  return all.length ? [...all.map((entry) => grey(entry) ? null : points[at++]), points.at(-1) ?? null] : [];
}

function seams(entries: Entry[], day: PlanDay): InsertionPoint[] {
  if (!entries.length) return [];
  return [...entries, null].map((entry, index) => {
    const previous = entries.slice(0, index).reverse().find((row) => row.type === "item")?.item ?? null;
    const next = entries.slice(index).find((row) => row.type === "item")?.item ?? null;
    const move = entries[index - 1];
    const anchor = entry?.type === "item" ? entry.item : previous ?? next!;
    const arrival = move?.type === "move" ? parseHm(move.move.arriveAt) : null;
    const nextStart = parseHm(next?.startsAt ?? "");
    const start = arrival ?? parseHm(previous?.endsAt ?? "") ?? (nextStart === null ? null : Math.max(0, nextStart - DEFAULT_STAY_MIN));
    const end = start === null ? null : Math.min(LAST_MINUTE, nextStart !== null && nextStart > start ? Math.min(start + DEFAULT_STAY_MIN, nextStart) : start + DEFAULT_STAY_MIN);
    return {
      key: `${day.day}:${entry ? entry.type === "item" ? `item:${entry.item.id}` : `move:${entry.move.id}` : "end"}`,
      anchorId: anchor.id,
      date: anchor.date || day.date,
      start: start !== null && end !== null && start < end ? formatHm(start) : "",
      end: start !== null && end !== null && start < end ? formatHm(end) : "",
      previous: previous?.title ?? null,
      next: next?.title ?? null,
      side: entry ? entry.type === "move" ? "before-move" : "before-stop" : "after-stop",
    };
  });
}
