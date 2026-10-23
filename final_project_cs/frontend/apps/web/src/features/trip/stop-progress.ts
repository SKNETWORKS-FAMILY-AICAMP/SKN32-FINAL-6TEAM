import type { BusToast } from "@/lib/toast-bus";
import type { Translate } from "@/lib/i18n";
import type { Notice, ProgressResult } from "@/lib/live/extras";
import type { TripStop } from "./model";
import type { EntryTime, TimelineEntry } from "./trip-timeline";

/**
 * `[2026-10-22 사용자 결정 — ST4F-716 · 목업 mockups/tripilot-trip-now-done.html]` The stop going on now: on its day's line, now is between its start and its end (the same reading
 * as the 「지금」 mark and the past rows — `entryTimes`). Not a stop paused for a disaster. Its card turns green and carries 「아직 진행 중 | 끝났어요」.
 * `next` is the day's first stop after it — the one the server's `advance_trip` moves (`journey_progress.py`: the next stop of the same day, a check-in too); with none,
 * 「끝났어요」 asks nothing and only records the end. `fixed`: that stop is booked or pinned — the server keeps its time, so 「바로 진행」 is not offered.
 */
export interface LiveStop { stop: TripStop; next: TripStop | null; fixed: boolean }

export function liveStop(entries: readonly TimelineEntry[], times: readonly EntryTime[]): LiveStop | null {
  const at = entries.findIndex((entry, index) => entry.type === "stop" && times[index]?.state === "now" && !entry.stop.paused);
  if (at < 0) return null;
  const stop = (entries[at] as Extract<TimelineEntry, { type: "stop" }>).stop;
  const next = entries.slice(at + 1).flatMap((entry) => entry.type === "stop" ? [entry.stop] : [])[0] ?? null;
  return { stop, next, fixed: Boolean(next && (next.booking === "booked" || next.pinned)) };
}

/**
 * What came of 「끝났어요」, in the notice bar: the server's own sentence. Moved → 「바뀜」; the end recorded but the next stop kept (fixed · hours · no route · …) → 「확인 필요」;
 * only the end recorded (「그대로 유지」) → the sentence alone.
 */
export function progressToast(result: ProgressResult, t: Translate): BusToast {
  if (result.navigation) return { text: result.text, chip: { text: t("확인 필요", "Check"), tone: "warn" } };
  if (result.state === "departing") return { text: result.text, chip: { text: t("바뀜", "Changed"), tone: "changed" } };
  return { text: result.text };
}

/**
 * `[2026-10-22 사용자 결정 — A]` The change notice of a report made on THIS device (its version is one this device wrote): not barred again — the result toast already said it with
 * the right chip, and the notice bar would cover it a moment later with 「바뀜」 even when nothing moved. The notice stays in the center and reaches the other devices.
 */
export function ownNotice(notice: Pick<Notice, "type" | "version">, own: ReadonlySet<number>): boolean {
  return notice.type === "change_notice" && notice.version !== null && own.has(notice.version);
}
