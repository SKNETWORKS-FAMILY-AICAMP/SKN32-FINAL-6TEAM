import { describe, expect, it } from "vitest";
import { initialAnswers, questions, skip, toggle } from "./model";
import { SURVEY_VERSION, toSurvey, tripSurveySchema } from "./payload";

describe("trip survey (backend constraints.survey)", () => {
  it("sends only the version when every question is skipped, so the backend applies its own defaults", () => {
    const allSkipped = questions.reduce((answers, _, index) => skip(answers, index), initialAnswers);
    expect(toSurvey(allSkipped)).toEqual({ version: SURVEY_VERSION });
  });

  it("maps each answer to its backend field", () => {
    const answers = {
      ...initialAnswers, theme: "food", party: "family", transport: ["public", "walk"], citizen: "foreign", priority: "transport",
      detailFood: "taste", detailActivity: "healing", detailTransport: "walk", indoorDining: "indoor", indoorActivity: "any", onDisruption: "ask_first", pace: "relaxed",
    };
    expect(toSurvey(answers)).toEqual({
      version: SURVEY_VERSION, theme: "food", party: "family", preferred_mobility: ["public", "walk"], domestic: false, priority: ["mobility"],
      priority_details: { food: ["taste"], activity: ["healing"], mobility: ["walk"] }, indoor_outdoor: { dining: "indoor", activity: "any" },
      on_disruption: "ask_first", pace: "relaxed",
    });
    expect(toSurvey({ ...answers, citizen: "domestic" }).domestic).toBe(true);
  });

  it("rejects what the backend rejects: unknown fields, values outside the contract and another version", () => {
    const survey = toSurvey(toggle(initialAnswers, "pace", "packed", false));
    expect(tripSurveySchema.safeParse(survey).success).toBe(true);
    expect(tripSurveySchema.safeParse({ ...survey, budget: "mid" }).success).toBe(false);
    expect(tripSurveySchema.safeParse({ ...survey, pace: "unselected" }).success).toBe(false);
    expect(tripSurveySchema.safeParse({ ...survey, version: "1" }).success).toBe(false);
  });
});
