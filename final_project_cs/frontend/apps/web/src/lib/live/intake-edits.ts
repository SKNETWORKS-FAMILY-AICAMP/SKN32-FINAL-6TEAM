import type { IntakeEdit } from "./intake";
import type { PickedPlace, ReviewItem } from "./intake-review";

/**
 * The `POST …/edits` values for the check screen's actions. An item is pointed at by its source and its position in
 * the read values (`items[n]`), not by the screen's own `id`.
 *
 * ★Rules the server enforces and the screen must not work around: a locked stop cannot be changed (409 `item_locked`),
 *   only a settled stop that needs no review can be locked (422 `lock_needs_confirmed_item`), and a lock is sent alone
 *   (422 `lock_with_changes`). A picked place is taken by its coordinates (inside Seoul) and is not looked up again.
 */
type Target = Pick<ReviewItem, "source_id" | "index">;
const field = (item: Target, name: string) => `items[${item.index}].${name}`;
const edit = (item: Target, name: string, value: unknown): IntakeEdit => ({ source_id: item.source_id, field: field(item, name), value });

export const itemEdit = {
  /** 「꼭 넣을 일정」 — on / off. Send it as the only edit of its request. */
  lock: (item: Target, locked: boolean) => edit(item, "locked", locked),
  /** Take the stop out (`true`) or bring it back (`false` — the undo of a delete). */
  remove: (item: Target, removed: boolean) => edit(item, "removed", removed),
  /** The server looks the name up again; it answers 422 `place_not_found` when it cannot. */
  placeByName: (item: Target, name: string) => edit(item, "place", { name }),
  /** The customer picked it from a list — coordinates and all. */
  placePicked: (item: Target, place: PickedPlace) => edit(item, "place", place),
  /** 「장소 없음」 — free time; its legs stay `waiting` and do not block registering. */
  placeNone: (item: Target) => edit(item, "place", { none: true }),
  date: (item: Target, isoDate: string) => edit(item, "date", isoDate),
  starts: (item: Target, hhmm: string) => edit(item, "starts_at", hhmm),
  ends: (item: Target, hhmm: string) => edit(item, "ends_at", hhmm),
};
