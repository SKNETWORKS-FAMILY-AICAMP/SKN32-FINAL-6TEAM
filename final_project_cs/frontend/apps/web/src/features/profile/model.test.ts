import { describe, expect, it } from "vitest";
import { checkDraft, recoveryEmailProblem } from "./model";

describe("recovery email rule (My page and onboarding)", () => {
  it("treats blank and spaces-only as not entered", () => {
    expect(recoveryEmailProblem("")).toBeUndefined();
    expect(recoveryEmailProblem("   ")).toBeUndefined();
  });

  it("trims only the ends and accepts any provider", () => {
    for (const email of [" name@example.com ", "name@example.com", "Name.Tag+1@example.co.kr", "traveler@sub.domain.travel"]) {
      expect(recoveryEmailProblem(email), email).toBeUndefined();
    }
  });

  it("rejects spaces inside and malformed addresses, not only a missing @", () => {
    for (const email of ["name example@site.com", "name@exa mple.com", "name@", "@example.com", "name@example", "name@@example.com", "name.example.com"]) {
      expect(recoveryEmailProblem(email), email).toBe("format");
    }
  });
});

describe("profile draft check", () => {
  it("requires a nickname that is not only spaces", () => {
    expect(checkDraft({ nickname: "", email: "" })).toEqual({ nickname: "required" });
    expect(checkDraft({ nickname: "   ", email: "" })).toEqual({ nickname: "required" });
    expect(checkDraft({ nickname: "여행자", email: "" })).toEqual({});
  });

  it("leaves the email optional but checks its format once written", () => {
    expect(checkDraft({ nickname: "여행자", email: "   " })).toEqual({});
    expect(checkDraft({ nickname: "여행자", email: "traveler@example.com" })).toEqual({});
    expect(checkDraft({ nickname: "여행자", email: " traveler@example.com " })).toEqual({});
    for (const email of ["traveler", "traveler@", "@example.com", "traveler@example", "a b@example.com"]) {
      expect(checkDraft({ nickname: "여행자", email }), email).toEqual({ email: "format" });
    }
  });

  it("reports both problems at once", () => {
    expect(checkDraft({ nickname: "", email: "nope" })).toEqual({ nickname: "required", email: "format" });
  });
});
