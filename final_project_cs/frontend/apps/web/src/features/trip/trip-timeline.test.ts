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
  // `[2026-10-13 사용자 결정 — 숙소 항목 B안]` One stay (kind lodging) from its check-in day to its check-out day.
  const hotel: TripStop = { ...stop("h", "2026-11-06", "15:00", "11:00"), kind: "lodging", endDate: "2026-11-09", title: "롯데호텔 서울" };
  const stayTrip: Pick<Trip, "stops" | "moves" | "legs"> = {
    stops: [stop("lunch", "2026-11-06", "12:30", "13:30"), hotel, stop("dinner", "2026-11-06", "18:00", "19:00"),
      stop("tower", "2026-11-07", "10:00", "12:00"), stop("market", "2026-11-09", "09:30", "10:30"), stop("palace", "2026-11-09", "13:00", "15:00")],
    moves: [], legs: {},
  };
  const ids = (date: string) => dayTimeline(stayTrip, date).map((entry) => entry.type === "stop" ? entry.stop.id : entry.type === "leg" ? "leg" : `${entry.stay.phase}:${entry.stay.night}/${entry.stay.nights}`);

  it("lists every day a stay runs over, even a day with nothing else", () => {
    expect(tripDays(stayTrip)).toEqual(["2026-11-06", "2026-11-07", "2026-11-08", "2026-11-09"]);
  });

  it("draws the stay as a stop on its check-in day, a band on the days after, and the check-out at its time on the last day", () => {
    expect(ids("2026-11-06")).toEqual(["lunch", "leg", "h", "leg", "dinner"]);
    expect(ids("2026-11-07")).toEqual(["from:2/3", "tower"]);
    expect(ids("2026-11-08")).toEqual(["from:3/3"]);
    expect(ids("2026-11-09")).toEqual(["from:4/3", "market", "leg", "checkout:4/3", "palace"]);
  });

  it("lists the trip's days in order", () => {
    expect(tripDays({ stops: [stop("x", "2026-10-15", "09:00"), stop("y", "2026-10-14", "09:00"), stop("z", "2026-10-15", "10:00")] })).toEqual(["2026-10-14", "2026-10-15"]);
  });

  it("puts a leg between each two stops of the day: the server's move when it keeps one, else the two stops and their directions", () => {
    const entries = dayTimeline(trip, "2026-10-14", [shape("m1", "a", "b")]);
    expect(entries.map((entry) => entry.type === "stop" ? entry.stop.id : entry.type === "leg" ? entry.leg.id : entry.stay.phase)).toEqual(["a", "m1", "b", "b>c", "c"]);
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
