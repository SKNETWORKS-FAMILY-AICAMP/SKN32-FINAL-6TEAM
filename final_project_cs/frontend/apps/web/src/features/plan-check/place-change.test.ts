import { describe, expect, it } from "vitest";
import { kindNote } from "./place-change";
import type { PlanCandidate, PlanItem } from "./model";

const ko = (korean: string) => korean;
const item = (kind?: string | null) => ({ info: kind === undefined ? undefined : { category: null, address: null, photos: [], kind } }) as unknown as PlanItem;
const candidate = (kind?: string | null) => ({ info: kind === undefined ? null : { category: null, address: null, photos: [], kind } }) as unknown as PlanCandidate;

describe("what a place card says about the kind (the values the server gave, side by side)", () => {
  it("says nothing when both kinds are known and the same", () => {
    expect(kindNote(item("dining"), candidate("dining"), ko)).toBeNull();
  });

  it("puts the two kinds side by side, as a warning, when they differ", () => {
    expect(kindNote(item("dining"), candidate("activity"), ko)).toEqual({ text: "지금 일정은 식당, 이곳은 활동으로 분류돼 있어요", mismatch: true });
  });

  it("says plainly that the server named no kind for the place instead of guessing", () => {
    expect(kindNote(item("dining"), candidate(null), ko)).toEqual({ text: "이 장소의 종류 정보가 없어요", mismatch: false });
    expect(kindNote(item("dining"), candidate(undefined), ko)).toMatchObject({ mismatch: false });
  });

  it("makes no comparison when the stop itself has no kind (no place yet): nothing to put beside", () => {
    expect(kindNote(item(null), candidate("activity"), ko)).toBeNull();
    expect(kindNote(item(undefined), candidate("dining"), ko)).toBeNull();
  });
});
