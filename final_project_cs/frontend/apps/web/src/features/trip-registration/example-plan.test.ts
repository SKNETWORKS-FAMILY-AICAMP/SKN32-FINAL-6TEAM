import { describe, expect, it } from "vitest";
import { examplePlan } from "./example-plan";

describe("the registration page's example plan", () => {
  it("starts a week after today in Seoul, so it is never a past date", () => {
    // 2026-10-03 23:30 UTC is already 2026-10-04 in Seoul.
    const now = new Date("2026-10-03T23:30:00Z");
    expect(examplePlan("ko", now)).toContain("1일차 · 2026-10-11");
    expect(examplePlan("ko", now)).toContain("2일차 · 2026-10-12");
    expect(examplePlan("en", now)).toContain("DAY 1 · 2026-10-11");
  });

  it("carries month ends and year ends over", () => {
    expect(examplePlan("ko", new Date("2026-12-28T01:00:00Z"))).toContain("1일차 · 2027-01-04");
  });

  it("writes every day with a date title and a time on every line, in both languages", () => {
    for (const language of ["ko", "en"] as const) {
      const lines = examplePlan(language, new Date("2026-10-03T01:00:00Z")).split("\n").filter(Boolean);
      const titles = lines.filter((line) => /\d{4}-\d{2}-\d{2}$/.test(line));
      expect(titles).toHaveLength(2);
      for (const line of lines.filter((entry) => !titles.includes(entry))) expect(line).toMatch(/^\d{2}:\d{2} /);
    }
  });
});
