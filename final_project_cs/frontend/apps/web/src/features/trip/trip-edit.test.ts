import { describe, expect, it } from "vitest";
import type { PlanCheckView, PlanItem, PlanMove } from "@/features/plan-check/model";
import type { TripStop } from "./model";
import { openingView, withTrip } from "./trip-edit";

const stop = (id: string, date: string, time: string, endTime?: string): TripStop => ({ id, date, time, endTime, title: id, booking: "unknown", notes: "", coordinates: { lat: 37.57, lng: 126.98 } });
const item = (id: string, day: number, date: string, startsAt: string): PlanItem => ({
  id, day, date, startsAt, endsAt: "", title: id, place: id, noPlace: false, coordinates: null, checks: [], verdict: "keep", locked: false, booked: null, info: null, suggestion: null,
});
const move = (fromId: string, toId: string, day: number): PlanMove => ({
  id: `${fromId}:${toId}`, fromId, toId, day, departAt: "", mode: "", summary: "", minutes: null, arriveAt: "", slackMin: null, estimated: false,
  modeKey: null, recommendedMode: null, modeChoice: null, checks: [], verdict: "keep",
});

// The server's edit holds only the stops still ahead, numbered by its own days: the trip's 2nd day is its 「1일차」.
const edit: PlanCheckView = {
  stage: "done", title: "접수 이름", lines: [], dirty: false, rechecking: null,
  days: [{ day: 1, date: "2026-10-15" }, { day: 2, date: "2026-10-16" }],
  items: [item("0-0", 1, "2026-10-15", "13:00"), item("0-1", 2, "2026-10-16", "10:00")],
  moves: [move("0-0", "0-1", 1)],
};
const trip = { title: "서울 사흘", stops: [stop("a", "2026-10-14", "10:00", "12:00"), stop("b", "2026-10-15", "09:00", "11:00"), stop("x", "2026-10-15", "13:00"), stop("y", "2026-10-16", "10:00")] };

describe("the edit of a registered trip", () => {
  it("shows saved stops immediately without claiming a check or edit permission before reopen finishes", () => {
    const view = openingView({ ...trip, id: "trip", messages: [], moves: [{ id: "m", fromId: "x", toId: "y", date: "2026-10-15", departAt: "14:00", arriveAt: "14:30", title: "saved" }] });
    expect(view.stage).toBe("done");
    expect(view.items.map((entry) => [entry.id, entry.day, entry.startsAt, entry.coordinates])).toEqual(trip.stops.map((entry) => [entry.id, [...new Set(trip.stops.map((s) => s.date))].indexOf(entry.date) + 1, entry.time, entry.coordinates]));
    expect(view.items.every((entry) => entry.verdict === null && entry.checks.length === 0)).toBe(true);
    expect(view.moves[0]).toMatchObject({ departAt: "14:00", arriveAt: "14:30", minutes: null, mode: "", verdict: null });
    expect(view.revision).toBeUndefined();
  });
  it("keeps the lodging icon for a saved hotel breakfast while editing is being prepared", () => {
    const view = openingView({ id: "trip", messages: [], stops: [{ ...stop("h", "2026-10-24", "09:00"), kind: "dining", placeInfo: { category: "숙소 안 식사", hours: [], hoursNotes: [], tags: [] } }] });
    expect(view.items[0]).toMatchObject({ kind: "dining", displayKind: "lodging", verdict: null });
  });
  it("numbers every stop by the trip's days and puts the stops that are over back in grey, in time order", () => {
    const view = withTrip(edit, trip, ["a", "b"]);
    expect(view.title).toBe("서울 사흘");
    expect(view.days).toEqual([{ day: 1, date: "2026-10-14" }, { day: 2, date: "2026-10-15" }, { day: 3, date: "2026-10-16" }]);
    expect(view.items.map((entry) => [entry.id, entry.day, entry.past ?? false])).toEqual([["a", 1, true], ["b", 2, true], ["0-0", 2, false], ["0-1", 3, false]]);
    expect(view.moves.map((entry) => entry.day)).toEqual([2]);
    // A stop that is over is not locked (「전체 잠금 해제」 is about the stops in the edit) and has nothing to check.
    expect(view.items[0]).toMatchObject({ locked: false, checks: [], verdict: "keep", startsAt: "10:00", endsAt: "12:00", coordinates: { lat: 37.57, lng: 126.98 } });
  });

  it("`[2026-10-15 ST4F-490]` puts a move beside a fixed stop after its grey line, and the morning move from a fixed stay on the day it goes to", () => {
    const stayTrip = { ...trip, stops: [...trip.stops, { ...stop("h", "2026-10-14", "15:00"), endDate: "2026-10-16" }] };
    const boundary = { ...edit, moves: [move("b", "0-0", 1), { ...move("h", "0-1", 2), fromStay: true }] };
    const view = withTrip(boundary, stayTrip, ["a", "b", "h"]);
    expect(view.moves.map((entry) => [entry.fromId, entry.day])).toEqual([["b", 2], ["h", 3]]);   // the stay is on day 1 (check-in) — its morning move is on day 3
  });

  it("`[2026-10-15 ST4F-490]` carries why each grey stop is kept out — only an over stop is called over", () => {
    const view = withTrip(edit, trip, ["a", "b"], { a: "past", b: "overnight" });
    expect(view.items.slice(0, 2).map((entry) => [entry.id, entry.past, entry.fixedReason])).toEqual([["a", true, "past"], ["b", true, "overnight"]]);
    expect(withTrip(edit, trip, ["a"]).items[0].fixedReason).toBeNull();               // an edit opened before the server said why
  });

  it("leaves a trip's stop out when the server did not say it is kept as it is (it is in the edit, under the intake's own id)", () => {
    const view = withTrip(edit, trip, []);
    expect(view.items.map((entry) => entry.id)).toEqual(["0-0", "0-1"]);
    expect(view.items.map((entry) => entry.day)).toEqual([2, 3]);
  });
});
