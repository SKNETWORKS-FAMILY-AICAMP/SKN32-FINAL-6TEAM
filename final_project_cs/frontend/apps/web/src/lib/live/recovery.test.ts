import { describe, expect, it } from "vitest";
import { recoveryOf } from "./recovery";

const BRIEF = {
  pause_id: "p1", phase: "in_progress", level: "day", resumed_at: "2026-10-06T10:00:00+00:00",
  event: { label: "지진", kind: "earthquake", category: "earthquake", at: "2026-10-06T05:05:00Z", official_text: "안전한 곳으로 대피하세요" },
  facts: ["기상청 지진정보: 안전한 곳으로 대피하세요", "사건 시각: 2026-10-06T05:05:00Z"],
  unknowns: ["지금 계신 곳 · 숙소 · 귀가 경로의 상태는 우리가 알 수 없어요"],
  affected_districts: [],
  items: [
    { item_id: "i1", title: "경복궁 관람", kind: "activity", starts_at: "2026-10-06T06:00:00+00:00", place_name: "경복궁", district: "종로구", status: "unknown", reason: "지진은 영향 범위를 단정하지 않아요" },
    { item_id: "i2", title: "점심", kind: "dining", starts_at: "2026-10-06T07:00:00+00:00", place_name: "식당", district: null, status: "weird", reason: "x" },
    { title: "id 없는 것" },
  ],
  counts: { affected: 0, unknown: 2, unaffected: 0 },
  options: [
    { key: "keep", label: "그대로 이어가기", detail: "일정은 바꾸지 않아요" },
    { key: "replace_affected", label: "영향받은 것만 바꾸기", recommended: true, detail: "…" },
    { key: "something_new", label: "모르는 선택", detail: "…" },
  ],
  extras: [{ key: "lighter_day", label: "오늘은 가볍게", default: false, detail: "하루를 덜 채워 달라는 선택이에요" }],
  questions: [{ key: "lodging", text: "숙소와 귀가 경로는 이용할 수 있나요?", answers: ["yes", "no", "unknown", "maybe"] }, { key: "pets", text: "?", answers: ["yes"] }],
  scope_note: "우리는 일정(시간표)만 조정해요. 업체 예약은 바꾸지 않아요.",
  chosen: { pause_id: "p1", choice: "keep", lighter_day: true, answers: { lodging: "yes", companions: "maybe" } },
};

describe("recoveryOf — the situation brief after a disaster pause was lifted", () => {
  it("is none for anything that is not a brief", () => {
    for (const raw of [null, undefined, "x", [], {}, { pause_id: "" }]) expect(recoveryOf(raw)).toBeNull();
  });

  it("reads the brief the way the server sent it", () => {
    const recovery = recoveryOf(BRIEF)!;
    expect(recovery.pauseId).toBe("p1");
    expect(recovery.phase).toBe("in_progress");
    expect(recovery.event).toEqual({ label: "지진", category: "earthquake", at: "2026-10-06T05:05:00Z", officialText: "안전한 곳으로 대피하세요" });
    expect(recovery.facts).toHaveLength(2);
    expect(recovery.unknowns).toEqual(["지금 계신 곳 · 숙소 · 귀가 경로의 상태는 우리가 알 수 없어요"]);
    expect(recovery.counts).toEqual({ affected: 0, unknown: 2, unaffected: 0 });
    expect(recovery.scopeNote).toBe("우리는 일정(시간표)만 조정해요. 업체 예약은 바꾸지 않아요.");
    expect(recovery.lighterDay).toEqual({ key: "lighter_day", label: "오늘은 가볍게", detail: "하루를 덜 채워 달라는 선택이에요", byDefault: false });
  });

  it("never reads an unknown status as 「unaffected」 and drops a stop it cannot name", () => {
    const { items } = recoveryOf(BRIEF)!;
    expect(items.map((item) => [item.id, item.status])).toEqual([["i1", "unknown"], ["i2", "unknown"]]);        // a status it does not know is unknown, never 「영향 없음」
  });

  it("offers only the ways it can send back, and the answers it knows", () => {
    const recovery = recoveryOf(BRIEF)!;
    expect(recovery.options.map((option) => option.key)).toEqual(["keep", "replace_affected"]);
    expect(recovery.options[1].recommended).toBe(true);
    expect(recovery.questions).toEqual([{ key: "lodging", text: "숙소와 귀가 경로는 이용할 수 있나요?", answers: ["yes", "no", "unknown"] }]);
  });

  it("reads what was chosen before, keeping only known answers", () => {
    expect(recoveryOf(BRIEF)!.chosen).toEqual({ choice: "keep", lighterDay: true, answers: { lodging: "yes" } });
    expect(recoveryOf({ ...BRIEF, chosen: null })!.chosen).toBeNull();
  });

  it("reads the phase of a trip that has not started", () => {
    expect(recoveryOf({ ...BRIEF, phase: "upcoming" })!.phase).toBe("upcoming");
    expect(recoveryOf({ ...BRIEF, phase: "someday" })!.phase).toBeNull();
  });
});
