import { describe, expect, it } from "vitest";
import { initialAnswers, questions, skip, toggle, toggleArea, toggleDetail } from "./model";
import { SURVEY_VERSION, toSurvey, tripSurveySchema } from "./payload";

describe("trip survey (backend constraints.survey)", () => {
  it("sends only the version when every question is skipped, so the backend applies its own defaults", () => {
    const allSkipped = questions.reduce((answers, _, index) => skip(answers, index), initialAnswers);
    expect(toSurvey(allSkipped)).toEqual({ version: SURVEY_VERSION });
  });

  it("sends the rankings as array order, mobility as `mobility`, and no transport question", () => {
    // Food → mobility; food: clean → taste; mobility: taxi → public. Activity was picked, then dropped.
    let a = toggleArea(toggleArea(toggleArea(initialAnswers, "food"), "activity"), "mobility");
    a = toggleDetail(a, "activity", "diy");
    a = toggleArea(a, "activity");
    a = toggleDetail(toggleDetail(a, "food", "clean"), "food", "taste");
    a = toggleDetail(toggleDetail(a, "mobility", "taxi"), "mobility", "public");
    const answers = { ...a, theme: "food", party: "family", citizen: "foreign", indoorDining: "indoor", indoorActivity: "any", onDisruption: "ask_first", pace: "relaxed" };
    const survey = toSurvey(answers);
    expect(survey).toEqual({
      version: SURVEY_VERSION, theme: "food", party: "family", domestic: false,
      priority: ["food", "mobility"], priority_details: { food: ["clean", "taste"], mobility: ["taxi", "public"] },
      indoor_outdoor: { dining: "indoor", activity: "any" }, on_disruption: "ask_first", pace: "relaxed",
    });
    expect(survey).not.toHaveProperty("preferred_mobility");
    expect(toSurvey({ ...answers, citizen: "domestic" }).domestic).toBe(true);
  });

  it("sends mobility's four detail codes, a rental car still being `car`", () => {
    let a = toggleArea(initialAnswers, "mobility");
    for (const value of ["public", "walk", "car", "taxi"]) a = toggleDetail(a, "mobility", value);
    expect(toSurvey(a).priority_details).toEqual({ mobility: ["public", "walk", "car", "taxi"] });
  });

  it("sends typed companions for `other` (trimmed) in `party`, and never once another choice is picked", () => {
    const other = { ...toggle(initialAnswers, "party", "other"), partyOther: "  직장 동료  " };
    expect(toSurvey(other).party).toBe("직장 동료");
    expect(toSurvey(toggle(other, "party", "friends")).party).toBe("friends");
    expect(toSurvey({ ...other, partyOther: "   " })).not.toHaveProperty("party");
  });

  it("rejects what the backend rejects: unknown fields, values outside the contract and another version", () => {
    const survey = toSurvey(toggle(initialAnswers, "pace", "packed"));
    expect(tripSurveySchema.safeParse(survey).success).toBe(true);
    expect(tripSurveySchema.safeParse({ ...survey, budget: "mid" }).success).toBe(false);
    expect(tripSurveySchema.safeParse({ ...survey, pace: "unselected" }).success).toBe(false);
    expect(tripSurveySchema.safeParse({ ...survey, priority: ["transport"] }).success).toBe(false);
    expect(tripSurveySchema.safeParse({ ...survey, version: "1" }).success).toBe(false);
  });
});
