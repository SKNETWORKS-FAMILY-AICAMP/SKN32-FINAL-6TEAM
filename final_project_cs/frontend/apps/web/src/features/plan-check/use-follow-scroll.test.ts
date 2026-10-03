import { describe, expect, it } from "vitest";
import { nearBottom, scrollDelta } from "./use-follow-scroll";

const box = { top: 100, bottom: 400 };

describe("following the newest row of the list", () => {
  it("does not move while the row is in view", () => {
    expect(scrollDelta(box, { top: 150, bottom: 250 })).toBe(0);
  });

  it("scrolls down just enough to show a row that is below, with room left under it", () => {
    expect(scrollDelta(box, { top: 380, bottom: 480 })).toBe(480 - 400 + 12);
  });

  it("scrolls up when the row is above", () => {
    expect(scrollDelta(box, { top: 60, bottom: 160 })).toBe(60 - 100 - 12);
  });

  it("brings the top of a row taller than the list into view instead of chasing its bottom", () => {
    expect(scrollDelta(box, { top: 300, bottom: 900 })).toBe(300 - 100 - 12);
  });

  it("counts a few pixels from the end as the end", () => {
    expect(nearBottom({ scrollTop: 560, clientHeight: 300, scrollHeight: 900 })).toBe(true);
    expect(nearBottom({ scrollTop: 400, clientHeight: 300, scrollHeight: 900 })).toBe(false);
  });
});
