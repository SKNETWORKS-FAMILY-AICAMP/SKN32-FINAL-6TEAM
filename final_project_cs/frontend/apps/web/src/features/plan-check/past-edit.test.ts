import { describe, expect, it } from "vitest";
import type { ReviewItem, ReviewedIntakeView } from "@/lib/live/intake-review";
import { refusalSentence } from "@/lib/live/error-text";
import { intakeRegistrationReady } from "./dining-status";
import { draftProblem, pastEdit, type ItemDraft } from "./model";

/**
 * `[2026-10-26 사용자 확정]` 과거 날짜 가드레일 — 화면 쪽.
 * 1. 계획서 전부가 과거면 서버 검사(`review.ready=false`)대로 등록 버튼을 열지 않는다(확인 단계에 머문다)
 * 2. 등록한 여행을 고칠 때 새로 넣거나 바꾸는 날짜·시각은 지금 이후만 — 지난 일정은 날짜·시각을 그대로 두고 이름만 고칠 수 있다. 최종 판정은 서버
 */
const NOW = { date: "2026-10-26", minute: 12 * 60 };
const draft = (patch: Partial<ItemDraft> = {}): ItemDraft => ({ title: "경복궁", date: "2026-10-26", start: "13:00", end: "14:00", place: "경복궁", noPlace: false, ...patch });

describe("all-past plan stays in review", () => {
  const item = (date: string): ReviewItem => ({
    id: "0-0", source_id: "s1", index: 0, title: "경복궁", kind: "activity", day: 1, date, starts_at: "10:00", ends_at: "11:00",
    locked: false, status: "review", can_lock: false, place_state: "found", place: null, candidates_hint: null,
    rows: [{ row: "date", result: "bad", text: "모든 일정이 오늘 이전이에요. 여행 날짜를 확인해주세요" }],
  } as unknown as ReviewItem);
  const view = (ready: boolean): ReviewedIntakeView => ({
    intake_id: "i1", revision: 2, status: "review", stage: "review", stage_label: "", fatal: null, trip_id: null, sources: [], check: null, needs_review: [],
    review: { revision: 2, dining_judge: null, built_at: "", engine: null, items: [item("2026-10-01")], moves: [], needs: { items: 1, moves: 0, total: 1 }, ready },
  } as unknown as ReviewedIntakeView);

  it("does not open registration when the server says the plan is wholly past", () => {
    expect(intakeRegistrationReady(view(false))).toBe(false);
  });
});

describe("edit dates and times only from now on", () => {
  it("refuses a new stop that starts before now, and allows one from this minute", () => {
    expect(pastEdit(draft({ start: "11:30", end: "13:00" }), null, NOW)).toBe(true);
    expect(pastEdit(draft({ start: "12:00", end: "13:00" }), null, NOW)).toBe(false);
    expect(pastEdit(draft({ date: "2026-10-25" }), null, NOW)).toBe(true);
  });

  it("lets a past stop keep its date and time while its name changes, but not move", () => {
    const over = draft({ start: "09:00", end: "10:00" });
    expect(pastEdit(draft({ ...over, title: "경복궁 야간" }), over, NOW)).toBe(false);
    expect(pastEdit({ ...over, date: "2026-10-28" }, over, NOW)).toBe(true);
  });

  it("lets a running stop stay longer but not restart before now or end before now", () => {
    const running = draft({ start: "11:00", end: "13:00" });
    expect(pastEdit({ ...running, end: "14:00" }, running, NOW)).toBe(false);
    expect(pastEdit({ ...running, start: "11:30" }, running, NOW)).toBe(true);
    expect(pastEdit({ ...running, end: "12:00" }, running, NOW)).toBe(true);
  });

  it("reports it as the editor's own problem only when the clock is given (edit mode)", () => {
    expect(draftProblem(draft({ start: "09:00", end: "10:00", date: "2026-10-27" }), { original: draft(), now: NOW })).toBe(null);
    expect(draftProblem(draft({ start: "09:00", end: "10:00" }), { original: draft(), now: NOW })).toBe("past");
    expect(draftProblem(draft({ start: "09:00", end: "10:00" }))).toBe(null);
  });
});

describe("server refusals for past edits", () => {
  it("has its own sentence for item_in_past and no_upcoming_items on the English screen", () => {
    expect(refusalSentence("item_in_past", "지난 때로는 넣거나 옮길 수 없어요: 덕수궁", undefined, "en")).toBe("Stops can't be added at or moved to a time that has passed.");
    expect(refusalSentence("no_upcoming_items", "진행 중이거나 앞으로 남은 일정이 하나는 있어야 해요 — 마지막 남은 일정은 뺄 수 없어요", undefined, "en"))
      .toBe("At least one current or upcoming stop must stay. The last one can't be removed.");
  });
});
