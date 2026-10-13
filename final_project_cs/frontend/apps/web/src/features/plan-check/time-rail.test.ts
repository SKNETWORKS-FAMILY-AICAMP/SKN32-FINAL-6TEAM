import { describe, expect, it } from "vitest";
import { railSpans, railY, type RailRow } from "./time-rail";

const stay = (start: number | null, end: number | null): RailRow => ({ kind: "stay", start, end });
const move = (depart: number | null, arrive: number | null): RailRow => ({ kind: "move", depart, arrive });

describe("railSpans — the minutes each row of a day stands for", () => {
  it("a stop runs from its start to its end, a way from the end before to the next start", () => {
    // 10:00–11:30, leave 11:30 arrive 11:45, 12:30–13:40
    expect(railSpans([stay(600, 690), move(690, 705), stay(750, 820)])).toEqual([
      { from: 600, to: 690 }, { from: 690, to: 750 }, { from: 750, to: 820 },
    ]);
  });

  it("a stop with no end lasts until the way after it leaves, else until the next stop starts", () => {
    expect(railSpans([stay(600, null), move(700, 720), stay(750, 800)])[0]).toEqual({ from: 600, to: 700 });
    expect(railSpans([stay(600, null), move(null, null), stay(750, 800)])[0]).toEqual({ from: 600, to: 750 });
  });

  it("the last stop of a day with no end stays open", () => {
    expect(railSpans([stay(600, 690), move(690, 705), stay(1020, null)]).at(-1)).toEqual({ from: 1020, to: null });
  });

  it("a way starts where the stop before ends — also when that end came from the way (planner plans leave later)", () => {
    // 09:30–11:00, leave 11:08 arrive 11:20, 11:30–12:50: the 8 minutes before leaving are the way's
    expect(railSpans([stay(570, 660), move(668, 680), stay(690, 770)])[1]).toEqual({ from: 660, to: 690 });
  });

  it("a time that runs back is not drawn to scale", () => {
    expect(railSpans([stay(1380, 30)])[0]).toEqual({ from: 1380, to: null });
  });

  it("unknown starts stay unknown", () => {
    expect(railSpans([stay(null, null), move(null, null), stay(null, 700)])).toEqual([
      { from: null, to: null }, { from: null, to: null }, { from: null, to: 700 },
    ]);
  });
});

describe("railY — where a minute stands on a drawn day", () => {
  const points = [{ minute: 600, y: 27.5 }, { minute: 690, y: 135.5 }, { minute: 690, y: 160 }, { minute: 750, y: 232 }];

  it("in proportion between the two pairs around it", () => {
    expect(railY(points, 600)).toBe(27.5);
    expect(railY(points, 645)).toBeCloseTo(81.5);
    expect(railY(points, 720)).toBeCloseTo(196);
  });

  it("steps over space that stands for no time", () => {
    expect(railY(points, 690)).toBe(160);
  });

  it("is null past the last pair", () => {
    expect(railY(points, 750)).toBeNull();
    expect(railY([], 600)).toBeNull();
  });
});
