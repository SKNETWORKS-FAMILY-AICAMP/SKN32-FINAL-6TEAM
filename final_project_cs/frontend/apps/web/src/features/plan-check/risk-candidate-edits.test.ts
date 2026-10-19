import { describe, expect, it } from "vitest";
import type { ReviewItem } from "@/lib/live/intake-review";
import { candidateTimeEdits, proposedTimeOf } from "./risk-candidate-edits";

const item = { source_id: "source-1", index: 2, date: "2026-10-18", starts_at: "10:00", ends_at: "11:00" } as ReviewItem;

describe("검증된 실내 대안의 방문 시각", () => {
  it("제공된 새 날짜와 한국 시각만 사용한다", () => {
    expect(proposedTimeOf({ date: "2026-10-19", starts_at: "2026-10-19T05:30:00Z", ends_at: "2026-10-19T06:30:00Z" }))
      .toEqual({ date: "2026-10-19", startsAt: "14:30", endsAt: "15:30" });
    expect(proposedTimeOf({ starts_at: "14:00", ends_at: "15:00" })).toEqual({ date: null, startsAt: "14:00", endsAt: "15:00" });
  });
  it("옛 시작 시각을 유지하지 않고 날짜·시작·종료를 한 수정 묶음으로 보낸다", () => {
    const edits = candidateTimeEdits(item, { date: "2026-10-19", startsAt: "14:00", endsAt: "15:00" });
    expect(edits.edits).toEqual([
      { source_id: "source-1", field: "items[2].date", value: "2026-10-19" },
      { source_id: "source-1", field: "items[2].starts_at", value: "14:00" },
      { source_id: "source-1", field: "items[2].ends_at", value: "15:00" },
    ]);
    expect(edits.undo?.map((edit) => edit.value)).toEqual(["2026-10-18", "10:00", "11:00"]);
  });
  it("시각 없는 후보는 만들어 넣지 않고 원래 값 모르면 되돌리기를 만들지 않는다", () => {
    expect(proposedTimeOf({ date: "2026-10-19", starts_at: "unconfirmed" })).toBeUndefined();
    expect(candidateTimeEdits(item, undefined)).toEqual({ edits: [], undo: [] });
    expect(candidateTimeEdits({ ...item, starts_at: null }, { date: null, startsAt: "14:00", endsAt: null }).undo).toBeNull();
  });
});
