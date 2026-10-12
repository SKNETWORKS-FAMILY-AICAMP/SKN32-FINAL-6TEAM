import { describe, expect, it } from "vitest";
import type { ReviewedIntakeView } from "@/lib/live/intake-review";
import { ReviewUndo } from "./review-undo";

function plan(revision: number, a = "경복궁", b = "광장시장", start = "09:00"): ReviewedIntakeView {
  return { intake_id: "intake-a", revision, status: "review", sources: [{ source_id: "s1", trip: {}, items: [
    { index: 0, fields: { title: { value: a }, starts_at: { value: start } } },
    { index: 1, fields: { title: { value: b } } },
  ] }], review: { revision, items: [{ id: "0-0", source_id: "s1", index: 0 }, { id: "0-1", source_id: "s1", index: 1 }] } } as ReviewedIntakeView;
}

describe("일정별 변경 원판", () => {
  it("다른 일정도 바뀐 뒤 각각의 최초 완료 판을 유지한다", () => {
    const undo = new ReviewUndo("intake-a");
    undo.remember(plan(1), plan(2, "창덕궁"));
    undo.remember(plan(2, "창덕궁"), plan(3, "창덕궁", "인사동"));
    expect(undo.itemTarget(plan(3, "창덕궁", "인사동"), "0-0")).toEqual({ revision: 1, source_id: "s1", index: 0 });
    expect(undo.itemTarget(plan(3, "창덕궁", "인사동"), "0-1")?.revision).toBe(2);
    undo.advance(plan(4, "경복궁", "인사동"));
    expect(undo.itemTarget(plan(4, "경복궁", "인사동"), "0-0")).toBeNull();
    expect(undo.itemTarget(plan(4, "경복궁", "인사동"), "0-1")?.revision).toBe(2);
  });
  it("반복 수정도 최초 원값을 유지하며 재조회 결과의 근거 변화만으로 버튼을 만들지 않는다", () => {
    const undo = new ReviewUndo("intake-a");
    undo.remember(plan(1), plan(2, "창덕궁"));
    undo.remember(plan(2, "창덕궁"), plan(3, "인사동"));
    expect(undo.itemTarget(plan(3, "인사동"), "0-0")?.revision).toBe(1);
    undo.advance(plan(4));
    expect(undo.itemTarget(plan(4), "0-0")).toBeNull();
  });
  it("시간만 바뀌면 기존 시간 되돌리기 자리를 유지한다", () => {
    const undo = new ReviewUndo("intake-a");
    undo.remember(plan(1), plan(2, "경복궁", "광장시장", "10:00"));
    expect(undo.itemTarget(plan(2, "경복궁", "광장시장", "10:00"), "0-0")).toBeNull();
  });
  it("다른 접수·다른 판·미리보기와 새로고침 기록으로 복원하지 않는다", () => {
    const undo = new ReviewUndo("intake-a");
    undo.remember(plan(1), plan(2, "창덕궁"));
    expect(undo.itemTarget(plan(3, "창덕궁"), "0-0")).toBeNull();
    expect(undo.itemTarget({ ...plan(2, "창덕궁"), preview: true }, "0-0")).toBeNull();
    expect(undo.itemTarget({ ...plan(2, "창덕궁"), intake_id: "other" }, "0-0")).toBeNull();
    expect(new ReviewUndo("intake-a").itemTarget(plan(2, "창덕궁"), "0-0")).toBeNull();
  });
});
