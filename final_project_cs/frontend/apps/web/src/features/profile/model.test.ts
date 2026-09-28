import { describe, expect, it } from "vitest";
import { checkDraft } from "./model";

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
