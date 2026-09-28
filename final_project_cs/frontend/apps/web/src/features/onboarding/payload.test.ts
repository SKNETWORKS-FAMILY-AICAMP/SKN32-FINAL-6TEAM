import { describe, expect, it } from "vitest";
import { count, initialAnswers, questions, skip, toggle } from "./model";
import { preferencesPayloadSchema, questionKeys, skipDefaults, toPayload, UNSELECTED } from "./payload";

describe("preferences payload", () => {
  it("sends every skipped question as its default and lists it as skipped", () => {
    const allSkipped = questions.reduce((answers, _, index) => skip(answers, index), initialAnswers);
    const payload = toPayload(allSkipped, "ko");
    expect(payload.answers).toEqual(skipDefaults);
    expect(Object.values(payload.answers).every((value) => value === UNSELECTED)).toBe(true);
    expect(payload.skipped).toEqual([...questionKeys]);
    expect(preferencesPayloadSchema.safeParse(payload).success).toBe(true);
  });

  it("sends answers as option codes, with numbers for headcount and a custom budget", () => {
    let answers = toggle(initialAnswers, "themes", "food", true);
    answers = count(toggle(answers, "companions", "family", true), "children", 1);
    answers = { ...answers, foodNone: true };
    answers = toggle(answers, "transport", "walk", true);
    answers = { ...toggle(answers, "budget", "custom", false), budgetCustom: "800000" };
    answers = toggle(answers, "citizen", "foreign", false);
    answers = toggle(answers, "priority", "activity", false);
    answers = { ...answers, detailFood: "taste", detailActivity: "healing", detailTransport: "walk" };
    answers = skip(toggle(answers, "religion", "none", false), 8);

    const payload = toPayload(answers, "en");
    expect(payload).toEqual({
      version: 1,
      language: "en",
      answers: {
        themes: ["food"],
        companions: { types: ["family"], adults: 2, children: 1, infants: 0 },
        food: { none: true, allergies: [], diet: [], religious: [] },
        transport: ["walk"],
        budget: { range: "custom", amountKrw: 800000 },
        nationality: "foreign",
        priority: "activity",
        detailPriority: { food: "taste", activity: "healing", transport: "walk" },
        religion: UNSELECTED,
      },
      skipped: ["religion"],
    });
    expect(preferencesPayloadSchema.safeParse(payload).success).toBe(true);
  });

  it("treats “Prefer not to say” as an answer, not a skip, and rejects labels in place of codes", () => {
    const payload = toPayload(toggle(initialAnswers, "religion", "skip", false), "ko");
    expect(payload.answers.religion).toBe("skip");
    expect(payload.skipped).not.toContain("religion");
    expect(preferencesPayloadSchema.safeParse({ ...payload, answers: { ...payload.answers, themes: ["맛집 탐방"] } }).success).toBe(false);
  });
});
