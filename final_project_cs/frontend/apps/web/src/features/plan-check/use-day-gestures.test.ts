import { describe, expect, it } from "vitest";
import { COMMIT_FRACTION, swipeStep, turnsDay } from "./use-day-gestures";

describe("the sideways drag of the day list", () => {
  it("follows the finger one to one while there is a day on that side, and says when letting go would turn the day", () => {
    expect(swipeStep(-40, 360, true)).toEqual({ shift: -40, armed: false });
    const line = Math.ceil(360 * COMMIT_FRACTION);
    expect(swipeStep(-line, 360, true)).toEqual({ shift: -line, armed: true });
    expect(swipeStep(500, 360, true).shift).toBe(360);                    // never further than the list is wide
  });

  it("gives way like a rubber band at the first and the last day: a part of the finger's way, no further than the cap", () => {
    const small = swipeStep(-100, 360, false);
    expect(small.armed).toBe(false);
    expect(small.shift).toBeLessThan(0);
    expect(Math.abs(small.shift)).toBeLessThan(100);                      // less than the finger moved
    expect(Math.abs(swipeStep(-900, 360, false).shift)).toBeLessThanOrEqual(88);
    expect(swipeStep(100, 360, false).shift).toBeGreaterThan(0);          // the other way too
  });

  it("turns the day when let go past the line or with a flick toward it, never without a day on that side", () => {
    expect(turnsDay(-60, 360, 0, true)).toBe(false);                      // a short, slow drag springs back
    expect(turnsDay(-120, 360, 0, true)).toBe(true);                      // past the line
    expect(turnsDay(-40, 360, -0.8, true)).toBe(true);                    // a flick toward the next day
    expect(turnsDay(-40, 360, 0.8, true)).toBe(false);                    // a flick the other way is not a turn
    expect(turnsDay(-5, 360, -0.9, true)).toBe(false);                    // a flick that hardly moved
    expect(turnsDay(-300, 360, -1, false)).toBe(false);                  // no day on that side
  });
});
