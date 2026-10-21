import { describe, expect, it } from "vitest";
import { backInside, clockText, crossesNoon, stayText, wheelAt, wheelMinutes } from "./time-wheel";

describe("the time wheel (오전/오후 · 시 · 분)", () => {
  it("stands on the half of the day, the hour of the clock face and the 5 minutes - and back", () => {
    expect(wheelAt(9 * 60 + 5)).toEqual({ half: 0, hour: 9, minute: 1 });
    expect(wheelAt(12 * 60 + 30)).toEqual({ half: 1, hour: 0, minute: 6 });       // 오후 12:30
    expect(wheelAt(0)).toEqual({ half: 0, hour: 0, minute: 0 });                  // 오전 12:00
    expect(wheelAt(23 * 60 + 55)).toEqual({ half: 1, hour: 11, minute: 11 });
    for (const minutes of [0, 5, 9 * 60 + 5, 12 * 60, 12 * 60 + 30, 23 * 60 + 55]) expect(wheelMinutes(wheelAt(minutes))).toBe(minutes);
  });

  it("shows a time typed between two steps on the step before it (09:07 → 09:05) instead of jumping to the next hour", () => {
    expect(wheelMinutes(wheelAt(9 * 60 + 7))).toBe(9 * 60 + 5);
    expect(wheelMinutes(wheelAt(9 * 60 + 58))).toBe(9 * 60 + 55);
  });

  it("turns the half of the day only when the hour goes across 11 ↔ 12, as a phone's clock does", () => {
    // Rows of the looping hour column: 12 · 1 … 11 in each copy of 12.
    expect(crossesNoon(48 + 11, 48 + 12)).toBe(true);                             // 11 → 12
    expect(crossesNoon(48 + 12, 48 + 11)).toBe(true);                             // 12 → 11
    expect(crossesNoon(48 + 3, 48 + 4)).toBe(false);
    expect(crossesNoon(48 + 11, 48 + 11 + 24)).toBe(false);                       // round twice: back in the same half
  });

  it("goes back to the nearest step it may take, and to the end itself when no step fits", () => {
    expect(backInside(8 * 60, 9 * 60 + 2, 18 * 60)).toBe(9 * 60 + 5);
    expect(backInside(19 * 60, 9 * 60, 17 * 60 + 58)).toBe(17 * 60 + 55);
    expect(backInside(10 * 60, 9 * 60, 18 * 60)).toBe(10 * 60);
    expect(backInside(8 * 60, 9 * 60 + 1, 9 * 60 + 3)).toBe(9 * 60 + 1);
  });

  it("says the time in the words of a phone's clock and the stay in hours and minutes", () => {
    expect(clockText(9 * 60 + 5, false)).toBe("오전 9:05");
    expect(clockText(12 * 60, false)).toBe("오후 12:00");
    expect(clockText(0, false)).toBe("오전 12:00");
    expect(clockText(21 * 60 + 30, true)).toBe("9:30 PM");
    expect(stayText(90, false)).toBe("1시간 30분");
    expect(stayText(120, false)).toBe("2시간");
    expect(stayText(45, true)).toBe("45 min");
  });
});
