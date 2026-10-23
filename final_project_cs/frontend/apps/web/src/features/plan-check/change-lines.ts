import type { RouteShapes } from "@/lib/live/route-shapes";
import type { PlanCandidate, PlanCheckView, PlanItem } from "./model";

/**
 * `[2026-10-19 사용자 지시]` The card being looked at, joined on the map to the stop before and the stop after it with a dashed straight line (the road
 * is not known on the change screen: dashed always means 「a straight join, not the road」 — `route-lines.ts`). None for the stop as it is (index 0).
 */
export function changeLines(view: PlanCheckView, item: PlanItem, list: PlanCandidate[], index: number): RouteShapes | null {
  const card = index > 0 ? list[index - 1] : null;
  if (!card?.coordinates) return null;
  const day = view.items.filter((entry) => entry.day === item.day);
  const at = day.findIndex((entry) => entry.id === item.id);
  const before = [...day.slice(0, Math.max(0, at))].reverse().find((entry) => entry.coordinates);
  const after = day.slice(at + 1).find((entry) => entry.coordinates);
  const id = `cand-${index}`;
  const join = (fromId: string, toId: string, points: { lat: number; lng: number }[]): RouteShapes["shapes"][number] => ({
    itemId: `${fromId}~${toId}`, fromItemId: fromId, toItemId: toId, from: null, to: null, mode: "unknown", source: "straight_line",
    grade: "추정", distanceM: null, note: null, points, rides: [], walks: null,
  });
  const shapes: RouteShapes["shapes"] = [];
  if (before?.coordinates && card.legs?.before) shapes.push(join(before.id, id, [before.coordinates, card.coordinates]));
  if (after?.coordinates && card.legs?.after) shapes.push(join(id, after.id, [card.coordinates, after.coordinates]));
  return shapes.length ? { attribution: "", shapes } : null;
}
