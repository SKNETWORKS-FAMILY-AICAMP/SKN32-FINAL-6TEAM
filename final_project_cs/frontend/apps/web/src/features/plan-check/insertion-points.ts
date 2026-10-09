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

/** Each visible seam belongs to one day, including both sides of a travel row. */
export function insertionPoints(view: PlanCheckView, day: PlanDay): InsertionPoint[] {
  const entries = timeline(view, day.day);
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
