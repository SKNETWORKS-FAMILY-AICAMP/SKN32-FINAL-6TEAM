import type { IntakeEdit } from "@/lib/live/intake";
import { itemEdit } from "@/lib/live/intake-edits";
import type { ReviewItem } from "@/lib/live/intake-review";

/** One stop's new times, "HH:MM". `end` "" = no end time. */
export interface Retime { id: string; start: string; end: string }

/**
 * `[2026-10-04]` The edits that move one stop to its new start/end — only the times that actually change, so a stop
 * whose times stay is nothing to send. An empty `end` clears the end time (sent as "", the way the stop editor does).
 * ★An empty `start` leaves the start alone: a stop always has a start in the plan, retiming never takes it away.
 */
export function retimeEdits(item: Pick<ReviewItem, "source_id" | "index" | "starts_at" | "ends_at">, change: Pick<Retime, "start" | "end">): IntakeEdit[] {
  const edits: IntakeEdit[] = [];
  const start = change.start.trim(), end = change.end.trim();
  if (start && start !== (item.starts_at ?? "")) edits.push(itemEdit.starts(item, start));
  if (end !== (item.ends_at ?? "")) edits.push(itemEdit.ends(item, end));
  return edits;
}
