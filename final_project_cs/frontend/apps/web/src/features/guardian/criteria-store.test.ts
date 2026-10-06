import { describe, expect, it } from "vitest";
import { SURVEY_VERSION, type TripSurvey } from "@/features/onboarding/payload";
import { paceOf, withCriteria, type Criteria } from "./criteria-store";

const base: Criteria = { pace: "moderate", paceChosen: false, guardian: null, decided: false };

describe("what the plan screen lays over the survey", () => {
  it("sends nothing before the card was answered (the survey stays as it was, possibly none)", () => {
    expect(withCriteria(undefined, base)).toBeUndefined();
    const survey: TripSurvey = { version: SURVEY_VERSION, pace: "packed" };
    expect(withCriteria(survey, { ...base, guardian: "on", decided: false })).toBe(survey);
  });

  it("「켜고 진행」 sends replace and 「건너뛰기 — 끄고 진행」 says ask_first out loud; 「적당히」 stands when nothing else was chosen", () => {
    expect(withCriteria(undefined, { ...base, guardian: "on", decided: true })).toEqual({ version: SURVEY_VERSION, pace: "moderate", on_disruption: "replace" });
    expect(withCriteria(undefined, { ...base, guardian: "off", decided: true })).toEqual({ version: SURVEY_VERSION, pace: "moderate", on_disruption: "ask_first" });
  });

  it("an untouched 「적당히」 does not overwrite the survey's own pace, but a chosen one does", () => {
    const survey: TripSurvey = { version: SURVEY_VERSION, pace: "relaxed", theme: "history" };
    expect(paceOf(survey, base)).toBe("relaxed");
    expect(withCriteria(survey, { ...base, guardian: "on", decided: true })).toEqual({ ...survey, on_disruption: "replace" });
    expect(paceOf(survey, { ...base, pace: "packed", paceChosen: true })).toBe("packed");
    expect(withCriteria(survey, { ...base, pace: "packed", paceChosen: true, guardian: "on", decided: true })).toMatchObject({ pace: "packed", theme: "history", on_disruption: "replace" });
  });

  it("the card's choice wins over the survey's on_disruption (the latest choice)", () => {
    const survey: TripSurvey = { version: SURVEY_VERSION, on_disruption: "replace" };
    expect(withCriteria(survey, { ...base, guardian: "off", decided: true })?.on_disruption).toBe("ask_first");
  });
});
