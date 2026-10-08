import { describe, expect, it } from "vitest";
import { checkDraft } from "./model";

describe("profile draft check", () => {
  it("requires a nickname that is not only spaces", () => {
    expect(checkDraft({ nickname: "" })).toEqual({ nickname: "required" });
    expect(checkDraft({ nickname: "   " })).toEqual({ nickname: "required" });
    expect(checkDraft({ nickname: "여행자" })).toEqual({});
  });
});
