import { describe, expect, it } from "vitest";
import { dayTimes, freeText, moveSlack, withTimes } from "./day-times";
import { exampleDone } from "./test-views";

describe("the screen's day as the time maths wants it", () => {
  it("lists the stops that have a start time in time order, with the travel minutes between them", () => {
    const times = dayTimes(exampleDone, 1);
    expect(times.stops.map((stop) => [stop.id, stop.start, stop.end])).toEqual([["a", 600, 690], ["b", 660, 720], ["c", 750, 810]]);
    expect(times.legs).toEqual([{ fromId: "a", toId: "b", minutes: 12 }, { fromId: "b", toId: "c", minutes: 18 }]);
    expect(times.indexOf.get("c")).toBe(2);
  });

  it("leaves out a stop with no usable start, and reads an end that is not after the start as no end", () => {
    const view = { ...exampleDone, items: exampleDone.items.map((item) => item.id === "a" ? { ...item, startsAt: "" } : item.id === "b" ? { ...item, endsAt: "10:00" } : item) };
    const times = dayTimes(view, 1);
    expect(times.stops.map((stop) => stop.id)).toEqual(["b", "c"]);
    expect(times.stops[0].end).toBeNull();
    expect(times.legs).toEqual([{ fromId: "b", toId: "c", minutes: 18 }]);          // the leg to a stop that is not in the day is not one of its legs
  });

  it("treats a locked or booked stop as fixed", () => {
    const view = { ...exampleDone, items: exampleDone.items.map((item) => item.id === "a" ? { ...item, locked: true } : item.id === "c" ? { ...item, booked: true } : item) };
    expect(dayTimes(view, 1).stops.map((stop) => stop.fixed)).toEqual([true, false, true]);
  });

  it("works out the free minutes after a leg - negative when already late", () => {
    const times = dayTimes(exampleDone, 1);
    expect(moveSlack(times, exampleDone.moves[1])).toBe(750 - (660 + 60 + 18));        // b ends at 720: 750 - (720 + 18)... b is 11:00-12:00
    expect(moveSlack(times, exampleDone.moves[0])).toBe(660 - (600 + 90 + 12));        // a runs 10:00-11:30, then 12 minutes: 42 minutes late
    expect(moveSlack(times, { fromId: "x", toId: "y", minutes: 3 })).toBeNull();
  });

  it("words only the free time that is worth a word", () => {
    expect(freeText(null)).toBeNull();
    expect(freeText(14)).toBeNull();
    expect(freeText(15)).toBe("15분");
    expect(freeText(60)).toBe("1시간");
    expect(freeText(102)).toBe("1시간 42분");
    expect(freeText(-30)).toBeNull();
  });
});

describe("the plan with some stops at other times", () => {
  it("changes only the stops named, and recomputes the legs around them", () => {
    const view = withTimes(exampleDone, [{ id: "c", start: 780, end: 840 }]);        // 13:00-14:00
    expect(view.items.find((item) => item.id === "c")).toMatchObject({ startsAt: "13:00", endsAt: "14:00" });
    expect(view.items.find((item) => item.id === "a")).toBe(exampleDone.items.find((item) => item.id === "a"));
    const leg = view.moves.find((move) => move.id === "b-c")!;
    expect(leg).toMatchObject({ departAt: "12:00", arriveAt: "12:18", slackMin: 42 });
    expect(view.moves.find((move) => move.id === "a-b")).toBe(exampleDone.moves.find((move) => move.id === "a-b"));
  });

  it("returns the very same plan when nothing changes", () => {
    expect(withTimes(exampleDone, [])).toBe(exampleDone);
  });

  it("keeps a stop's end when the change does not know it", () => {
    const view = withTimes(exampleDone, [{ id: "c", start: 780, end: null }]);
    expect(view.items.find((item) => item.id === "c")).toMatchObject({ startsAt: "13:00", endsAt: "13:30" });
  });
});
