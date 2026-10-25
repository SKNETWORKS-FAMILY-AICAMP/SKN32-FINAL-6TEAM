import { describe, expect, it } from "vitest";
import { examplePlan } from "./example-plan";

describe("the registration page's example plan", () => {
  it("starts tomorrow in Seoul, so it is never a past date", () => {
    // 2026-10-03 23:30 UTC is already 2026-10-04 in Seoul.
    const now = new Date("2026-10-03T23:30:00Z");
    expect(examplePlan("ko", now)).toContain("1일차 · 2026-10-05");
    expect(examplePlan("ko", now)).toContain("2일차 · 2026-10-06");
    expect(examplePlan("en", now)).toContain("DAY 1 · 2026-10-05");
  });

  it("carries month ends and year ends over", () => {
    expect(examplePlan("ko", new Date("2026-12-31T01:00:00Z"))).toContain("1일차 · 2027-01-01");
  });

  it("writes every day with a date title and a time on every line, in both languages", () => {
    for (const language of ["ko", "en"] as const) {
      const lines = examplePlan(language, new Date("2026-10-03T01:00:00Z")).split("\n").filter(Boolean);
      const titles = lines.filter((line) => /\d{4}-\d{2}-\d{2}$/.test(line));
      expect(titles).toHaveLength(2);
      for (const line of lines.filter((entry) => !titles.includes(entry))) expect(line).toMatch(/^\d{2}:\d{2} /);
    }
  });

  it("puts three stops on each day, each with an end time, and no palace (경복궁 · 창덕궁 close on a weekday)", () => {
    for (const language of ["ko", "en"] as const) {
      const days = examplePlan(language, new Date("2026-10-25T01:00:00Z")).split("\n\n").map((day) => day.split("\n").slice(1));
      expect(days.map((stops) => stops.length)).toEqual([3, 3]);
      for (const stop of days.flat()) expect(stop).toMatch(language === "ko" ? /, \d{2}:\d{2} 종료$/ : /, ends \d{2}:\d{2}$/);
    }
    expect(examplePlan("ko")).not.toMatch(/경복궁|창덕궁|덕수궁|창경궁/);
  });
});
