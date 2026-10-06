import { describe, expect, it } from "vitest";
import { criteriaOf, DEFAULT_PACE, disruptionOf, isPace, PACES } from "./model";
import { tripSurveySchema, SURVEY_VERSION } from "@/features/onboarding/payload";

describe("what the plan screen sends", () => {
  it("starts on 「적당히」 and shows the three in order", () => {
    expect(DEFAULT_PACE).toBe("moderate");
    expect(PACES.map((pace) => pace.ko)).toEqual(["여유롭게", "적당히", "꽉 차게"]);
    expect(PACES.every((pace) => isPace(pace.value))).toBe(true);
  });

  it("sends 「replace」 for 켜고 진행 and says 「ask_first」 out loud for 끄고 진행 (never nothing)", () => {
    expect(disruptionOf("on")).toBe("replace");
    expect(disruptionOf("off")).toBe("ask_first");
  });

  it("is what the backend's survey schema takes", () => {
    for (const guardian of ["on", "off"] as const) for (const pace of PACES.map((entry) => entry.value)) {
      const survey = tripSurveySchema.parse({ version: SURVEY_VERSION, ...criteriaOf(pace, guardian) });
      expect(survey.pace).toBe(pace);
      expect(survey.on_disruption).toBe(guardian === "on" ? "replace" : "ask_first");
    }
  });

  it("knows a pace from any other value", () => {
    expect(isPace("moderate")).toBe(true);
    expect(isPace("fast")).toBe(false);
    expect(isPace(null)).toBe(false);
  });
});
