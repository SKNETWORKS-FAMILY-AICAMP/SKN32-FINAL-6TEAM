import { describe, expect, it } from "vitest";
import { candidateNoteText } from "./place-change";

const ko = (korean: string) => korean;

describe("why a stop has no candidates, in the server's terms", () => {
  it("says a booked stop is not offered other places and asks for the booked place's name", () => {
    expect(candidateNoteText(["booked_needs_name"], ko)).toContain("예약하신 곳이라 다른 후보를 권하지 않아요");
  });

  it("says each of the other reasons in its own words", () => {
    expect(candidateNoteText(["no_candidates_in_area"], ko)).toContain("지역 둘레에 같은 종류의 장소가 없어요");
    expect(candidateNoteText(["no_same_kind"], ko)).toContain("같은 종류의 후보가 없어요");
    expect(candidateNoteText(["no_reference_point"], ko)).toContain("기준이 될 위치를 정하지 못해");
  });

  it("puts the booking first when several notes come together", () => {
    expect(candidateNoteText(["no_same_kind", "booked_needs_name"], ko)).toContain("예약하신 곳이라");
  });

  it("returns null for notes it does not know, or none — the general line is shown, not an invented reason", () => {
    expect(candidateNoteText(["engine_budget_exhausted", "kakao:timeout"], ko)).toBeNull();
    expect(candidateNoteText([], ko)).toBeNull();
    expect(candidateNoteText(undefined, ko)).toBeNull();
  });
});
