import type { IntakeEdit } from "@/lib/live/intake";
import { itemEdit } from "@/lib/live/intake-edits";
import { pickedPlace, type AutofixChange, type ReviewPlace } from "@/lib/live/intake-review";

/** A previous place as the edit that puts it back: with coordinates it is sent as it was; a bare name is looked up again. */
export function restorePlace(target: { source_id: string; index: number }, place: ReviewPlace | null): IntakeEdit | null {
  if (!place) return null;
  const picked = pickedPlace({ ...place, address: null, category: null, ref: null });
  return picked ? itemEdit.placePicked(target, picked) : itemEdit.placeByName(target, place.name);
}

/**
 * The edits that put back what 「전체 자동 추천」 changed — or null when they cannot put ALL of it back.
 *
 * ★All or nothing. A stop that had no place before (`from.place` null) and was given one cannot be taken back (there is no
 *   edit for 「back to nothing」 other than 「no place」, which is a different thing), and a time that was null cannot be sent.
 *   Putting back only the times and telling the customer 「되돌렸어요」 would leave the new place in the plan — so then the
 *   toast offers no 「되돌리기」 at all.
 */
export function autofixUndo(changes: readonly AutofixChange[]): IntakeEdit[] | null {
  const edits: IntakeEdit[] = [];
  for (const change of changes) {
    const target = { source_id: change.source_id, index: change.index };
    const placeChanged = change.reason === "place" || change.reason === "place_and_time";
    const timeChanged = change.reason === "time" || change.reason === "place_and_time";
    if (placeChanged) {
      const back = restorePlace(target, change.from.place && { kind: null, content_id: null, ...change.from.place });
      if (!back) return null;
      edits.push(back);
    }
    if (timeChanged) {
      if (change.to.starts_at !== change.from.starts_at) {
        if (!change.from.starts_at) return null;
        edits.push(itemEdit.starts(target, change.from.starts_at));
      }
      if (change.to.ends_at !== change.from.ends_at) {
        if (!change.from.ends_at) return null;
        edits.push(itemEdit.ends(target, change.from.ends_at));
      }
    }
  }
  return edits.length ? edits : null;
}
