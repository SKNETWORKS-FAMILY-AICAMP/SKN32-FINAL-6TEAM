import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import { answeredCount, count, initialAnswers, questions, toggle, valid, validationHint } from "./model";

describe("onboarding preferences", () => {
  it("keeps solo travel at one adult and moves group travel to at least two", () => {
    const solo = toggle({ ...initialAnswers, adults: 3, children: 1 }, "companions", "alone", true);
    expect(solo).toMatchObject({ companions: ["alone"], adults: 1, children: 0, infants: 0 });
    expect(valid(1, solo)).toBe(true);
    const friends = toggle(solo, "companions", "friends", true);
    expect(friends).toMatchObject({ companions: ["friends"], adults: 2 });
    expect(valid(1, friends)).toBe(true);
    expect(count(solo, "children", 1).companions).toEqual([]);
    expect(count(initialAnswers, "adults", -1).adults).toBe(1);
    expect(count({ ...initialAnswers, adults: 20 }, "adults", 1).adults).toBe(20);
  });

  it("explains a group trip with fewer than two travelers", () => {
    const t = translator("en");
    const alone = { ...initialAnswers, companions: ["family"], adults: 1 };
    expect(valid(1, alone)).toBe(false);
    expect(validationHint(1, alone, t)).toBe("Set at least two travelers when traveling with others.");
    expect(validationHint(1, initialAnswers, t)).toBe("");
  });

  it("clears food restrictions with “none apply” and counts only answered questions", () => {
    const allergic = toggle(initialAnswers, "allergies", "nuts", true);
    expect(answeredCount(allergic)).toBe(1);
    expect(toggle({ ...allergic, foodNone: true }, "diet", "vegan", true)).toMatchObject({ foodNone: false, diet: ["vegan"] });
    expect(answeredCount(initialAnswers)).toBe(0);
  });

  it("requires a positive amount for a custom budget and one choice per detail group", () => {
    const custom = toggle(initialAnswers, "budget", "custom", false);
    expect(valid(4, custom)).toBe(false);
    expect(valid(4, { ...custom, budgetCustom: "0" })).toBe(false);
    expect(valid(4, { ...custom, budgetCustom: "800000" })).toBe(true);
    expect(toggle(custom, "budget", "custom", false).budget).toBe("");
    expect(valid(7, { ...initialAnswers, detailFood: "taste", detailActivity: "diy" })).toBe(false);
    expect(valid(7, { ...initialAnswers, detailFood: "taste", detailActivity: "diy", detailTransport: "walk" })).toBe(true);
    expect(questions).toHaveLength(9);
  });
});
