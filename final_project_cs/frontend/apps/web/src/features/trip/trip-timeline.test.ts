import { describe, expect, it } from "vitest";
import type { RouteShape } from "@/lib/live/route-shapes";
import type { Trip, TripStop } from "./model";
import { between, dayTimeline, distanceText, tripDays } from "./trip-timeline";

const stop = (id: string, date: string, time: string, endTime?: string): TripStop => ({ id, date, time, endTime, title: id, booking: "unknown", notes: "" });
const shape = (itemId: string, from: string, to: string): RouteShape => ({ itemId, fromItemId: from, toItemId: to, from, to, mode: "subway", source: "stations", grade: "추정", distanceM: 2100, note: null, points: [], rides: [] });

const trip: Pick<Trip, "stops" | "moves" | "legs"> = {
  stops: [stop("a", "2026-10-14", "10:00", "11:30"), stop("b", "2026-10-14", "12:30", "13:40"), stop("c", "2026-10-14", "15:00"), stop("d", "2026-10-15", "09:30")],
  moves: [{ id: "m1", fromId: "a", toId: "b", date: "2026-10-14", departAt: "11:30", arriveAt: "11:45", title: "a → b" }],
  legs: { "b>c": "https://www.google.com/maps/dir/?api=1&origin=b&destination=c" },
};

describe("trip timeline", () => {
  it("lists the trip's days in order", () => {
    expect(tripDays({ stops: [stop("x", "2026-10-15", "09:00"), stop("y", "2026-10-14", "09:00"), stop("z", "2026-10-15", "10:00")] })).toEqual(["2026-10-14", "2026-10-15"]);
  });

  it("puts a leg between each two stops of the day: the server's move when it keeps one, else the two stops and their directions", () => {
    const entries = dayTimeline(trip, "2026-10-14", [shape("m1", "a", "b")]);
    expect(entries.map((entry) => entry.type === "stop" ? entry.stop.id : entry.leg.id)).toEqual(["a", "m1", "b", "b>c", "c"]);
    const [, first, , second] = entries;
    expect(first.type === "leg" && first.leg).toMatchObject({ minutes: 15, slack: 45, directions: null, shape: { itemId: "m1" } });
    expect(second.type === "leg" && second.leg).toMatchObject({ move: null, minutes: null, slack: null, shape: null, directions: "https://www.google.com/maps/dir/?api=1&origin=b&destination=c" });
  });

  it("finds a route line by its two stops when it is not keyed by a move, and says a late arrival as negative slack", () => {
    const late = { ...trip, moves: [{ id: "m1", fromId: "a", toId: "b", date: "2026-10-14", departAt: "11:30", arriveAt: "12:40", title: "a → b" }] };
    const [, leg, , other] = dayTimeline(late, "2026-10-14", [shape("s-bc", "b", "c")]);
    expect(leg.type === "leg" && leg.leg.slack).toBe(-10);
    expect(other.type === "leg" && other.leg.shape?.itemId).toBe("s-bc");
  });

  it("reads minutes and distances only from what the server gave", () => {
    expect(between("11:30", "12:05")).toBe(35);
    expect(between("11:30", null)).toBeNull();
    expect(between("오전", "12:00")).toBeNull();
    expect(distanceText(850)).toBe("850m");
    expect(distanceText(2140)).toBe("2.1km");
    expect(distanceText(null)).toBeNull();
    expect(distanceText(0)).toBeNull();
  });
});
