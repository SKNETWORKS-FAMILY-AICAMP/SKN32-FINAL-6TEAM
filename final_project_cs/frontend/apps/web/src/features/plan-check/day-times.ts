import type { PlanCheckView, PlanMove } from "./model";
import { formatHm, occupancy, parseHm, type Retime, type TimedLeg, type TimedStop } from "./time-plan";

/**
 * `[2026-10-04 사용자 지시]` The screen's day as the time maths (`time-plan.ts`) wants it: the stops that have a start time, in time order, and the travel minutes between them.
 * A stop with no usable start time cannot be placed in time, so it is left out (it is neither moved nor in anyone's way). A stop that is locked or booked is `fixed`.
 */
export interface DayTimes { stops: TimedStop[]; legs: TimedLeg[]; indexOf: ReadonlyMap<string, number> }

export function dayTimes(view: Pick<PlanCheckView, "items" | "moves">, day: number): DayTimes {
  const stops = view.items.filter((item) => item.day === day).flatMap((item): TimedStop[] => {
    const start = parseHm(item.startsAt);
    if (start === null) return [];
    const end = parseHm(item.endsAt);
    return [{ id: item.id, start, end: end !== null && end > start ? end : null, fixed: item.locked || item.booked === true }];
  }).sort((a, b) => a.start - b.start);
  const ids = new Set(stops.map((stop) => stop.id));
  const legs = view.moves.filter((move) => ids.has(move.fromId) && ids.has(move.toId)).map((move) => ({ fromId: move.fromId, toId: move.toId, minutes: move.minutes ?? 0 }));
  return { stops, legs, indexOf: new Map(stops.map((stop, at) => [stop.id, at])) };
}

/** Free minutes after a leg: the next stop's start minus (the stop before it ends + the travel). Null when either end has no time. */
export function moveSlack(times: DayTimes, move: Pick<PlanMove, "fromId" | "toId" | "minutes">): number | null {
  const from = times.stops[times.indexOf.get(move.fromId) ?? -1];
  const to = times.stops[times.indexOf.get(move.toId) ?? -1];
  if (!from || !to) return null;
  return to.start - (from.start + occupancy(from) + (move.minutes ?? 0));
}

/** 「여유 1시간 42분」 style wording of free minutes (whole hours and minutes), for gaps of 15 minutes or more; null below that — a short gap is only space. */
export function freeText(slack: number | null): string | null {
  if (slack === null || slack < 15) return null;
  const hours = Math.floor(slack / 60), minutes = slack % 60;
  return `${hours ? `${hours}시간` : ""}${hours && minutes ? " " : ""}${minutes ? `${minutes}분` : ""}`;
}

/**
 * The view with some stops at other times (the live picture while a time is being changed, nothing saved): their start and end, and for the legs around them the
 * time of leaving, the time of arriving and the free minutes left. Everything else is the very same object.
 */
export function withTimes(view: PlanCheckView, changes: readonly Retime[]): PlanCheckView {
  if (!changes.length) return view;
  const byId = new Map(changes.map((change) => [change.id, change]));
  const items = view.items.map((item) => {
    const change = byId.get(item.id);
    return change ? { ...item, startsAt: formatHm(change.start), endsAt: change.end === null ? item.endsAt : formatHm(change.end) } : item;
  });
  const days = [...new Set(items.filter((item) => byId.has(item.id)).map((item) => item.day))];
  const times = new Map(days.map((day) => [day, dayTimes({ items, moves: view.moves }, day)]));
  const moves = view.moves.map((move) => {
    if (!byId.has(move.fromId) && !byId.has(move.toId)) return move;
    const from = items.find((item) => item.id === move.fromId);
    const day = times.get(from?.day ?? -1);
    const stop = day?.stops[day.indexOf.get(move.fromId) ?? -1];
    if (!from || !day || !stop) return move;
    const leave = stop.start + occupancy(stop);
    return { ...move, departAt: formatHm(leave), arriveAt: move.minutes === null ? "" : formatHm(leave + move.minutes), slackMin: moveSlack(day, move) };
  });
  return { ...view, items, moves };
}
