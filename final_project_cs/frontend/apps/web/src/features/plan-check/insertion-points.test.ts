import { describe, expect, it } from "vitest";
import { insertionPoints } from "./insertion-points";
import { exampleDone } from "./test-views";

describe("inserting on the correct side of a travel row", () => {
  it("keeps departure and arrival seams distinct and uses arrival after travel", () => {
    const view = { ...exampleDone, moves: exampleDone.moves.map((move) => ({ ...move, arriveAt: "11:42" })) };
    const points = insertionPoints(view, { day: 1, date: "2026-10-01" });
    expect(points.find((point) => point.key === "1:move:a-b")).toMatchObject({ anchorId: "a", start: "11:30", side: "before-move" });
    expect(points.find((point) => point.key === "1:item:b")).toMatchObject({ anchorId: "b", start: "11:42", side: "before-stop" });
    expect(new Set(points.map((point) => point.key)).size).toBe(points.length);
  });
  it("never uses the previous day's last stop as the new day's anchor", () => {
    const view = { ...exampleDone, items: [...exampleDone.items.filter((item) => item.day === 1), { ...exampleDone.items[0], id: "next-day", day: 2, date: "2026-10-02", startsAt: "09:00" }] };
    expect(insertionPoints(view, { day: 2, date: "2026-10-02" })[0]).toMatchObject({ anchorId: "next-day", previous: null, date: "2026-10-02", start: "08:00", end: "09:00" });
  });
  it("does not invent a clock time when the neighbouring stop has no time", () => {
    const view = { ...exampleDone, items: [{ ...exampleDone.items[0], startsAt: "", endsAt: "" }], moves: [] };
    expect(insertionPoints(view, { day: 1, date: "2026-10-01" }).every((point) => point.start === "" && point.end === "")).toBe(true);
  });
  it("does not create a midnight wrap or a zero duration at the end of the day", () => {
    const view = { ...exampleDone, items: [{ ...exampleDone.items[0], startsAt: "23:30", endsAt: "23:59" }], moves: [] };
    expect(insertionPoints(view, { day: 1, date: "2026-10-01" }).at(-1)).toMatchObject({ start: "", end: "" });
  });
});
