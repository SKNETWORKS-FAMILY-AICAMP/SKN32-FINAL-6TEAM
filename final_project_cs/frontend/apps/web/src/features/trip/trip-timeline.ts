import type { RouteShape } from "@/lib/live/route-shapes";
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

/** The leg's distance as people say it (「850m」 · 「2.1km」); null when the server gave none. */
export function distanceText(meters: number | null | undefined): string | null {
  if (meters === null || meters === undefined || !Number.isFinite(meters) || meters <= 0) return null;
  return meters >= 1000 ? `${(meters / 1000).toFixed(1)}km` : `${Math.round(meters)}m`;
}
