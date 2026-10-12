import type { RouteShape } from "@/lib/live/route-shapes";
import { railSpans, type RailRow } from "@/features/plan-check/time-rail";
import type { Trip, TripMove, TripStop } from "./model";

/**
 * `[2026-10-07 사용자 결정 — 목업 C안]` The registered trip as the plan check draws a plan: each day a timeline of its stops and, between two stops, the way from one to the next.
 * Pure: what the screen shows is read from the trip (and the route lines the server drew), nothing is made up.
 */

/** The days of the trip, in order ("YYYY-MM-DD"). */
export function tripDays(trip: Pick<Trip, "stops">): string[] {
  return [...new Set(trip.stops.map((stop) => stop.date))].sort();
}

/** Between two stops: the server's move (with its route line, when it drew one), or only the two stops when the server keeps no move (a plan registered from typed text). */
export interface TripLeg {
  /** The move's id, or `${fromId}>${toId}` when there is no move. */
  id: string;
  from: TripStop;
  to: TripStop;
  move: TripMove | null;
  shape: RouteShape | null;
  /** Minutes on the way (from the move's leave and arrive times); null when not known. */
  minutes: number | null;
  /** Minutes left before the next stop starts after arriving (negative = late); null when not known. */
  slack: number | null;
  /** The customer's map app, from the stop before to the stop after (`Trip.legs`). */
  directions: string | null;
}

export type TimelineEntry = { type: "stop"; stop: TripStop } | { type: "leg"; leg: TripLeg };

export const toMinutes = (hm: string): number | null => {
  const found = /^(\d{1,2}):(\d{2})$/.exec(hm);
  return found ? Number(found[1]) * 60 + Number(found[2]) : null;
};

/** The minutes from `a` to `b` ("HH:MM"); null when either is not a time. */
export function between(a: string | null | undefined, b: string | null | undefined): number | null {
  const from = a ? toMinutes(a) : null, to = b ? toMinutes(b) : null;
  return from === null || to === null ? null : to - from;
}

/** One day: its stops in time order, with the way between each two. */
export function dayTimeline(trip: Pick<Trip, "stops" | "moves" | "legs">, date: string, shapes: readonly RouteShape[] = []): TimelineEntry[] {
  const stops = trip.stops.filter((stop) => stop.date === date);
  const entries: TimelineEntry[] = [];
  stops.forEach((stop, index) => {
    entries.push({ type: "stop", stop });
    const next = stops[index + 1];
    if (next) entries.push({ type: "leg", leg: legOf(trip, stop, next, shapes) });
  });
  return entries;
}

function legOf(trip: Pick<Trip, "moves" | "legs">, from: TripStop, to: TripStop, shapes: readonly RouteShape[]): TripLeg {
  const move = trip.moves?.find((entry) => entry.fromId === from.id && entry.toId === to.id) ?? null;
  const shape = (move && shapes.find((entry) => entry.itemId === move.id)) ?? shapes.find((entry) => entry.fromItemId === from.id && entry.toItemId === to.id) ?? null;
  const minutes = move ? between(move.departAt, move.arriveAt) : null;
  return {
    id: move?.id ?? `${from.id}>${to.id}`, from, to, move, shape,
    minutes: minutes !== null && minutes >= 0 ? minutes : null,
    slack: move?.arriveAt ? between(move.arriveAt, to.time) : null,
    directions: trip.legs?.[`${from.id}>${to.id}`] ?? null,
  };
}

// ── `[2026-10-12 사용자 결정 — 목업 2026-10-12_타임라인_지금시각_목업.html B]` Now on the registered trip: what is over, what is going on, what opens by itself. ──

/** The Seoul wall clock: the date ("YYYY-MM-DD") and the minute of that day (the server keeps trips in Seoul time and sends no clock — the device's is used). */
export interface SeoulNow { date: string; minute: number }

/** Orders two Seoul times (a date and a minute): compared as text. */
export const seoulKey = (at: SeoulNow) => `${at.date}T${String(at.minute).padStart(4, "0")}`;

/** `past` = its end has passed (a past stop is locked and drawn small), `now` = going on, `next` = still to come. `started`: its start has passed (its dot is filled). */
export interface EntryTime { state: "past" | "now" | "next"; started: boolean; from: number; to: number }

/** The day's last minute (24:00): a last stop with no end lasts until then. */
const DAY_END = 1440;

/**
 * The time each entry of a day stands for and where now stands against it. A stop runs from its start to its end — with no end, until the way after it leaves, else until the next stop
 * starts, else to the end of the day; a way runs from the end of the stop before to the start of the next. The same spans draw the line (`railSpans`), so what is filled and what is over agree.
 */
export function entryTimes(entries: readonly TimelineEntry[], date: string, now: SeoulNow): EntryTime[] {
  const spans = railSpans(entries.map((entry): RailRow => entry.type === "stop"
    ? { kind: "stay", start: toMinutes(entry.stop.time), end: entry.stop.endTime ? toMinutes(entry.stop.endTime) : null }
    : { kind: "move", depart: entry.leg.move?.departAt ? toMinutes(entry.leg.move.departAt) : null, arrive: entry.leg.move?.arriveAt ? toMinutes(entry.leg.move.arriveAt) : null }));
  return spans.map(({ from, to }) => {
    const start = from ?? 0, end = to ?? DAY_END;
    const at = date < now.date ? DAY_END + 1 : date > now.date ? -1 : now.minute;
    return { state: at >= end ? "past" : at >= start ? "now" : "next", started: at >= start, from: start, to: end };
  });
}

/** The entry to keep open at `now`: the stop going on, else the way being waited for, travelled or arrived from — only when the server keeps that way (a way with no move says nothing more). */
export function currentEntry(trip: Pick<Trip, "stops" | "moves" | "legs">, now: SeoulNow): string | null {
  const entries = dayTimeline(trip, now.date);
  const times = entryTimes(entries, now.date, now);
  const index = times.findIndex((time) => time.state === "now");
  if (index < 0) return null;
  const entry = entries[index];
  return entry.type === "stop" ? entry.stop.id : entry.leg.move ? entry.leg.id : null;
}

/** When an entry (a stop, or a way by its id) is over. */
function entryEnd(trip: Pick<Trip, "stops" | "moves" | "legs">, id: string): SeoulNow | null {
  for (const date of tripDays(trip)) {
    const entries = dayTimeline(trip, date);
    const index = entries.findIndex((entry) => (entry.type === "stop" ? entry.stop.id : entry.leg.id) === id);
    if (index >= 0) return { date, minute: entryTimes(entries, date, { date, minute: 0 })[index].to };
  }
  return null;
}

/**
 * `[2026-10-12 사용자 지시]` While the screen stays open and time passes, the open card follows now: a stop opens when it starts (the one before closes), the way after it opens when
 * the stop ends (waiting, travelling, the free time — the next stop opens only when it starts), and when the day's last stop ends everything folds. Left alone: a card the customer
 * opened themselves (until it is over). Returns the new open entry, or `undefined` when nothing changes.
 */
export function followNow(trip: Pick<Trip, "stops" | "moves" | "legs">, before: SeoulNow, after: SeoulNow, open: string | null, auto: boolean): { open: string | null; auto: boolean } | undefined {
  const from = seoulKey(before), to = seoulKey(after);
  if (!(to > from)) return undefined;
  const passes = (at: SeoulNow | null) => at !== null && from < seoulKey(at) && seoulKey(at) <= to;
  const was = currentEntry(trip, before), next = currentEntry(trip, after);
  const openEnded = open !== null && passes(entryEnd(trip, open));
  const dayOver = tripDays(trip).some((date) => {
    const entries = dayTimeline(trip, date);
    return entries.length > 0 && passes({ date, minute: entryTimes(entries, date, { date, minute: 0 }).at(-1)!.to });
  });
  if (dayOver && next === null) return open === null ? undefined : { open: null, auto: false };
  if (next === null || (was === next && !openEnded)) return undefined;
  if (open !== null && !auto && open !== was && !openEnded) return undefined;
  return open === next ? undefined : { open: next, auto: true };
}

/** The leg's distance as people say it (「850m」 · 「2.1km」); null when the server gave none. */
export function distanceText(meters: number | null | undefined): string | null {
  if (meters === null || meters === undefined || !Number.isFinite(meters) || meters <= 0) return null;
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)}km` : `${Math.round(meters)}m`;
}
