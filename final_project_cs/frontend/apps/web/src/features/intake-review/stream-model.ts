import type { StreamState } from "@/lib/live/intake-events";
import type { ReviewItem, ReviewMove, ItemRow, CheckLine } from "@/lib/live/intake-review";

/**
 * The check screen while the server is still checking (mockup screen ③): what has come in so far, shaped like the finished
 * `review` so the same cards and the same legs draw it. Nothing is invented — a stop with no check line yet has none.
 */

export interface StreamedReview {
  items: ReviewItem[];
  moves: ReviewMove[];
  /** Stops whose check lines are still coming in (they show a spinner instead of a status). Empty once the check is done. */
  checking: ReadonlySet<string>;
  /** Places and legs checked so far / expected — for the progress line. `expectedMoves` is the legs the day order allows. */
  progress: { checked: number; total: number };
}

const dayKey = (item: Pick<ReviewItem, "day" | "date">) => `${item.day ?? 9_999}|${item.date ?? ""}`;

/** Day, then time, then the order the server numbered them — the order the finished screen lists them in. */
export function compareItems(a: ReviewItem, b: ReviewItem): number {
  if (a.day !== b.day) return (a.day ?? 9_999) - (b.day ?? 9_999);
  const date = (a.date ?? "").localeCompare(b.date ?? "");
  if (date) return date;
  const time = (a.starts_at ?? "99:99").localeCompare(b.starts_at ?? "99:99");
  if (time) return time;
  return a.id.localeCompare(b.id, undefined, { numeric: true });
}

/** `check:<item>:<row>` → the item (ids hold no colon, rows hold none either). */
function itemOfCheckKey(key: string): string {
  const rest = key.slice("check:".length);
  return rest.slice(0, rest.lastIndexOf(":"));
}

export function streamedReview(stream: StreamState): StreamedReview {
  const rowsOf = new Map<string, CheckLine<ItemRow>[]>();
  const complete = new Set<string>();
  let running: string | null = null;
  for (const entry of stream.order) {
    if (entry.startsWith("check:")) {
      const id = itemOfCheckKey(entry);
      if (running && running !== id) complete.add(running);       // the server sends every line of a stop together
      running = id;
      const line = stream.checks[entry.slice("check:".length)];
      if (line) rowsOf.set(id, [...(rowsOf.get(id) ?? []), line]);
    } else if (entry.startsWith("move:") && running) {
      complete.add(running);                                       // a leg comes after the lines of the stop it leads to
      running = null;
    }
  }
  if (stream.done && running) complete.add(running);

  const items = Object.values(stream.items).sort(compareItems).map((item) => ({ ...item, rows: rowsOf.get(item.id) ?? [] }));
  const moves = Object.values(stream.moves).sort((a, b) => compareItems(items.find((item) => item.id === a.from) ?? items[0], items.find((item) => item.id === b.from) ?? items[0]));
  const checking = new Set(stream.done ? [] : items.filter((item) => !complete.has(item.id)).map((item) => item.id));

  const sameDayPairs = items.slice(1).filter((item, index) => dayKey(item) === dayKey(items[index])).length;
  const total = items.length + Math.max(sameDayPairs, moves.length);
  const checked = (items.length - checking.size) + moves.length;
  return { items, moves, checking, progress: { checked: stream.done ? total : checked, total } };
}
