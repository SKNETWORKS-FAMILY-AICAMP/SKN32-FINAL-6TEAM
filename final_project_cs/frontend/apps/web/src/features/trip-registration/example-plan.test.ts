import { describe, expect, it } from "vitest";
import { examplePlan } from "./example-plan";

describe("the registration page's example plan", () => {
  it("puts day 1 on the day it is pressed in Seoul and day 2 on the next day", () => {
    // 2026-10-03 23:30 UTC is already 2026-10-04 in Seoul.
    const now = new Date("2026-10-03T23:30:00Z");
    expect(examplePlan("ko", now)).toContain("1일차 · 2026-10-04");
    expect(examplePlan("ko", now)).toContain("2일차 · 2026-10-05");
    expect(examplePlan("en", now)).toContain("DAY 1 · 2026-10-04");
    expect(examplePlan("en", now)).toContain("DAY 2 · 2026-10-05");
  });

  it("carries month ends and year ends over", () => {
    expect(examplePlan("ko", new Date("2026-12-31T01:00:00Z"))).toContain("2일차 · 2027-01-01");
  });

  it("writes the plan the user gave (2026-10-26)", () => {
    expect(examplePlan("ko", new Date("2026-10-26T01:00:00Z"))).toBe(`1일차 · 2026-10-26
12:00 인사동 · 점심
15:00 국립현대미술관 서울
18:00 N서울타워

2일차 · 2026-10-27
09:30 국립중앙박물관
12:30 명동 · 점심
14:00 북촌한옥마을`);
  });

  it("writes every day with a date title and a time on every line, in both languages", () => {
    for (const language of ["ko", "en"] as const) {
      const lines = examplePlan(language, new Date("2026-10-03T01:00:00Z")).split("\n").filter(Boolean);
      const titles = lines.filter((line) => /\d{4}-\d{2}-\d{2}$/.test(line));
      expect(titles).toHaveLength(2);
      for (const line of lines.filter((entry) => !titles.includes(entry))) expect(line).toMatch(/^\d{2}:\d{2} /);
    }
  });

  it("puts three stops on each day and no palace (경복궁 · 창덕궁 close on a weekday)", () => {
    for (const language of ["ko", "en"] as const) {
      const days = examplePlan(language, new Date("2026-10-25T01:00:00Z")).split("\n\n").map((day) => day.split("\n").slice(1));
      expect(days.map((stops) => stops.length)).toEqual([3, 3]);
    }
    expect(examplePlan("ko")).not.toMatch(/경복궁|창덕궁|덕수궁|창경궁/);
  });
});
