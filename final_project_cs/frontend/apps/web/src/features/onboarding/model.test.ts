import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import {
  answeredCount, done, initialAnswers, partyLabel, priorityLines, questions, skip, toggle, toggleArea, toggleDetail, unskip, valid, type Answers,
} from "./model";

const ko = translator("ko");
/** Every question answered, with a picked "other" draft kept aside. */
const full: Answers = {
  ...initialAnswers, theme: "food", party: "family", partyOther: "직장 동료", priority: ["food", "mobility"],
  details: { food: ["clean", "taste"], activity: [], mobility: ["taxi"] }, indoorDining: "indoor", indoorActivity: "any", onDisruption: "ask_first", pace: "relaxed",
};

describe("onboarding preferences", () => {
  it("asks six questions in order, without the separate transport or nationality question", () => {
    expect(questions.map((question) => question.id)).toEqual(["theme", "party", "priority", "indoor", "onDisruption", "pace"]);
    expect(questions.map((question) => question.title[0])).not.toContain("어떻게 이동하고 싶나요?");
    expect(questions.map((question) => question.title[0])).not.toContain("한국 국적이신가요?");
    expect(questions[2].title[0]).toBe("어떤 것을 더 중요하게 생각하나요?");
    expect(questions[2].helper[0]).toBe("중요한 순서대로 분야와 세부 항목을 선택해 주세요.");
    expect(questions.every((_, index) => valid(index, full))).toBe(true);
  });

  it("skipping one question clears only its own fields, whichever position it has", () => {
    questions.forEach((question, index) => {
      const skipped = skip(full, index);
      for (const field of Object.keys(full) as (keyof Answers)[]) {
        if (field === "skipped") continue;
        if (question.fields.includes(field)) expect(skipped[field], `${question.id}.${field}`).toEqual(initialAnswers[field]);
        else expect(skipped[field], `${question.id} must keep ${field}`).toEqual(full[field]);
      }
      expect(valid(index, skipped)).toBe(false);
      expect(done(index, skipped)).toBe(true);
      expect(answeredCount(skipped)).toBe(questions.length);
    });
    expect(answeredCount(unskip(skip(initialAnswers, 4), 4))).toBe(0);
  });

  it("companions: `other` needs typed words (not spaces); another choice hides it but keeps the draft; skipping clears both", () => {
    const other = toggle(initialAnswers, "party", "other");
    expect(valid(1, other)).toBe(false);
    expect(valid(1, { ...other, partyOther: "   " })).toBe(false);
    const typed = { ...other, partyOther: "  직장 동료 " };
    expect(valid(1, typed)).toBe(true);
    expect(partyLabel(typed, ko)).toBe("직장 동료");
    const family = toggle(typed, "party", "family");
    expect(valid(1, family)).toBe(true);
    expect(partyLabel(family, ko)).toBe("가족");
    expect(toggle(family, "party", "other").partyOther).toBe("  직장 동료 ");
    expect(skip(typed, 1)).toMatchObject({ party: "", partyOther: "" });
  });

  it("areas rank in tapping order; un-picking pulls the ones behind up and clears its details; picking again goes last", () => {
    let a = toggleArea(toggleArea(toggleArea(initialAnswers, "food"), "mobility"), "activity");
    expect(a.priority).toEqual(["food", "mobility", "activity"]);
    a = toggleDetail(toggleDetail(a, "mobility", "taxi"), "mobility", "public");
    a = toggleDetail(a, "food", "clean");
    a = toggleArea(a, "mobility");
    expect(a.priority).toEqual(["food", "activity"]);
    expect(a.details).toEqual({ food: ["clean"], activity: [], mobility: [] });
    expect(toggleArea(a, "mobility").priority).toEqual(["food", "activity", "mobility"]);
  });

  it("details rank per area the same way and never change the area pick", () => {
    let a = toggleArea(toggleArea(initialAnswers, "food"), "activity");
    a = toggleDetail(toggleDetail(toggleDetail(a, "food", "taste"), "food", "kindness"), "food", "clean");
    a = toggleDetail(a, "activity", "diy");
    expect(a.details.food).toEqual(["taste", "kindness", "clean"]);
    a = toggleDetail(a, "food", "taste");
    expect(a.details.food).toEqual(["kindness", "clean"]);
    expect(toggleDetail(a, "food", "taste").details.food).toEqual(["kindness", "clean", "taste"]);
    expect(a.details.activity).toEqual(["diy"]);
    expect(a.priority).toEqual(["food", "activity"]);
  });

  it("priorities are answered with at least one area and at least one detail in every picked area", () => {
    const food = toggleArea(initialAnswers, "food");
    expect(valid(2, initialAnswers)).toBe(false);
    expect(valid(2, food)).toBe(false);
    expect(valid(2, toggleDetail(food, "food", "taste"))).toBe(true);
    const both = toggleArea(toggleDetail(food, "food", "taste"), "mobility");
    expect(valid(2, both)).toBe(false);
    expect(valid(2, toggleDetail(both, "mobility", "car"))).toBe(true);
    expect(skip(both, 2)).toMatchObject({ priority: [], details: { food: [], activity: [], mobility: [] } });
  });

  it("the summary lines follow the picking order and name mobility's four details", () => {
    let a = toggleArea(toggleArea(initialAnswers, "mobility"), "food");
    for (const value of ["taxi", "public", "walk", "car"]) a = toggleDetail(a, "mobility", value);
    a = toggleDetail(toggleDetail(a, "food", "clean"), "food", "taste");
    expect(priorityLines(a, ko)).toEqual(["1. 이동 — 택시 → 대중교통 → 도보 → 렌트카", "2. 음식 — 청결 → 맛"]);
    expect(priorityLines(a, translator("en"))[0]).toBe("1. Getting around — Taxi → Public transit → Walking → Rental car");
  });
});
