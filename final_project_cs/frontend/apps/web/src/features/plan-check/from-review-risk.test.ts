import { describe, expect, it } from "vitest";
import type { Candidate, ReviewItem, ReviewedIntakeView } from "@/lib/live/intake-review";
import { readingOf } from "./from-intake";
import { planCandidate, reviewResultOf } from "./from-review";
import { candidateNoteText } from "./place-change";

const risk = { item_id: "i1", status: "problem", mode: "cached", problems: [{ category: "traffic_control", message: "도로 전면 통제", source: "UTIC" }] };

describe("검증 화면의 실제 위험과 대안", () => {
  it("장소 검증 결과를 유지하면서 도로 위험을 별도로 표시한다", () => {
    const next = { intake_id: "a1", revision: 2, status: "review", stage: "review", stage_label: "", fatal: null, trip_id: null, needs_review: [], check: null,
      sources: [{ source_id: "s1", kind: "text", filename: null, transcribed: false, lines: [], items: [], trip: {}, reading: null }], review: { revision: 2, ready: true, built_at: "", engine: "estimate", needs: { items: 0, moves: 0, total: 0 },
        risk_schema_version: 1, risk_mode: "cached", risk_checked_at: "2026-10-18T14:00:00+09:00", moves: [],
        items: [{ id: "0-0", source_id: "s1", index: 0, title: "계획의 방문지", date: "2026-10-18", status: "keep", place: null, kind: "activity", day: 1, starts_at: "14:00", ends_at: "15:00", locked: false, can_lock: true, place_state: "none", candidates_hint: null,
          rows: [{ row: "place", result: "ok", text: "장소 확인" }, { row: "risk", result: "warn", text: "중복 원문" }], risk } as ReviewItem] } } as ReviewedIntakeView;
    const result = reviewResultOf(next, readingOf(next))!;
    expect(result.risksAvailable).toBe(true);
    expect(result.items[0].verdict).toBe("keep");
    expect(result.items[0].risk).toMatchObject({ itemId: "0-0", title: "계획의 방문지", status: "problem" });
    expect(result.items[0].checks).toEqual([{ kind: "place", result: "ok", text: "장소 확인" }, { kind: "risk", result: "warn", text: "도로 전면 통제" }]);
  });
  it("실내 후보 카드에 실제 제안된 날짜와 시각을 보여 준다", () => {
    const candidate = { rank: 1, fits: true, rows: [], status: "ok", distance_m: 500, reference: "방문지", slack: { before: 5, after: 5 }, estimated: false, place: { name: "실내 전시관", ref: "catalog:sample", latitude: 37.5, longitude: 127.0, source: "tour", kind: "activity", category: "전시관", address: "서울" },
      date: "2026-10-18", starts_at: "2026-10-18T14:30:00+09:00", ends_at: "2026-10-18T15:30:00+09:00", risk: { ...risk, status: "clear", problems: [] } } as Candidate;
    const card = planCandidate(candidate, "0-0", "candidate", null);
    expect(card.proposedTime).toEqual({ date: "2026-10-18", startsAt: "14:30", endsAt: "15:30" });
    expect(card.reason).toContain("2026-10-18 · 14:30–15:30");
    expect(card.checks[0].result).toBe("ok");
  });
  it("확인 실패를 검증된 후보가 없다는 뜻으로 표시하지 않는다", () => {
    const t = (ko: string) => ko;
    expect(candidateNoteText(["risk_alternatives", "verification_unavailable"], t)).toContain("확인하지 못했어요");
    expect(candidateNoteText(["no_verified_alternative"], t)).toContain("조건을 모두 만족하는 곳이 없었어요");
    expect(candidateNoteText(["verified_indoor"], t)).toContain("방문 시각도 함께 적용");
  });
  it("교통 자료 일부 미확인 후보를 완전한 안전 확인으로 표시하지 않는다", () => {
    const t = (ko: string) => ko;
    const note = candidateNoteText(["verified_indoor", "indoor_with_coverage_warning"], t)!;
    expect(note).toContain("교통 통제 자료 일부를 확인하지 못한");
    expect(note).not.toContain("안전·운영시간·이동을 확인한");
    const candidate = { rank: 1, fits: true, status: "warn", rows: [{ row: "risk", result: "unknown", text: "교통 자료 일부 미확인" }],
      distance_m: 500, reference: "방문지", slack: { before: 5, after: 5 }, estimated: false,
      place: { name: "실내 전시관", ref: "catalog:sample", latitude: 37.5, longitude: 127.0, source: "tour", kind: "activity", category: "전시관", address: "서울" },
      reason: "교통자료 일부 미확인", risk: { ...risk, status: "unknown", problems: [], unknown_categories: [{ label: "교통 통제", code: "partial" }] } } as Candidate;
    const card = planCandidate(candidate, "0-0", "candidate", null);
    expect(card.risk?.status).toBe("unknown");
    expect(card.checks).toEqual([{ kind: "risk", result: "unknown", text: "확인 불가: 교통 통제" }]);
    expect(card.reason).toContain("교통자료 일부 미확인");
  });
});
