import { describe, expect, it } from "vitest";
import { answeredCount, done, initialAnswers, questions, skip, toggle, unskip, valid } from "./model";

describe("onboarding preferences", () => {
  it("follows the backend survey: nine questions, one theme, one companion group, several transports", () => {
    expect(questions).toHaveLength(9);
    const theme = toggle(toggle(initialAnswers, "theme", "food", false), "theme", "nature", false);
    expect(theme.theme).toBe("nature");
    expect(toggle(theme, "theme", "nature", false).theme).toBe("");
    expect(valid(1, toggle(initialAnswers, "party", "family", false))).toBe(true);
    const transport = toggle(toggle(initialAnswers, "transport", "walk", true), "transport", "taxi", true);
    expect(transport.transport).toEqual(["walk", "taxi"]);
    expect(toggle(transport, "transport", "walk", true).transport).toEqual(["taxi"]);
  });

  it("needs a choice on every card before Next, with one choice in each group", () => {
    expect(questions.every((_, index) => !valid(index, initialAnswers))).toBe(true);
    expect(valid(5, { ...initialAnswers, detailFood: "taste", detailActivity: "diy" })).toBe(false);
    expect(valid(5, { ...initialAnswers, detailFood: "taste", detailActivity: "diy", detailTransport: "walk" })).toBe(true);
    expect(valid(6, { ...initialAnswers, indoorDining: "indoor" })).toBe(false);
    expect(valid(6, { ...initialAnswers, indoorDining: "indoor", indoorActivity: "any" })).toBe(true);
    expect(valid(7, toggle(initialAnswers, "onDisruption", "ask_first", false))).toBe(true);
    expect(valid(8, toggle(initialAnswers, "pace", "relaxed", false))).toBe(true);
  });

  it("skips any question: clears its answer, counts it toward progress, and answering takes the skip back", () => {
    const skipped = skip({ ...initialAnswers, indoorDining: "indoor", indoorActivity: "outdoor" }, 6);
    expect(skipped).toMatchObject({ indoorDining: "", indoorActivity: "", skipped: [6] });
    expect(valid(6, skipped)).toBe(false);
    expect(done(6, skipped)).toBe(true);
    expect(answeredCount(skipped)).toBe(1);
    expect(skip(skipped, 6).skipped).toEqual([6]);
    expect(answeredCount(questions.reduce((answers, _, index) => skip(answers, index), initialAnswers))).toBe(questions.length);
    expect(answeredCount(unskip(skipped, 6))).toBe(0);
  });
});
