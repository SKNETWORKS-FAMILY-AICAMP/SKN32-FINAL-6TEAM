import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import type { AutofixChange } from "@/lib/live/intake-review";
import { blockedReason, deleteQuestion, eul, gwa, ro, said } from "./review-actions";

const ko = translator("ko");
const en = translator("en");

describe("Korean particles", () => {
  it("follows the last syllable: 을/를 · 과/와 · 으로/로 (ㄹ takes 로)", () => {
    expect(eul("경복궁")).toBe("경복궁을");
    expect(eul("올리브영")).toBe("올리브영을");
    expect(eul("광화문점")).toBe("광화문점을");
    expect(eul("남산타워")).toBe("남산타워를");
    expect(gwa("경복궁")).toBe("경복궁과");
    expect(gwa("남산타워")).toBe("남산타워와");
    expect(ro("명동")).toBe("명동으로");
    expect(ro("서울숲")).toBe("서울숲으로");
    expect(ro("광장시장")).toBe("광장시장으로");
    expect(ro("남산타워")).toBe("남산타워로");
    expect(ro("한강공원길")).toBe("한강공원길로");              // ㄹ → 로
  });

  it("uses the vowel-ending form for a name that does not end in Hangul", () => {
    expect(eul("N서울타워")).toBe("N서울타워를");
    expect(eul("COEX")).toBe("COEX를");
    expect(eul("")).toBe("를");
  });
});

describe("why a button cannot be pressed", () => {
  const settled = { status: "keep" as const, locked: false, can_lock: true };
  const review = { status: "review" as const, locked: false, can_lock: false };
  const locked = { status: "keep" as const, locked: true, can_lock: true };

  it("says so while the server is checking, before anything else", () => {
    expect(blockedReason({ action: "delete", item: settled, busy: true }, ko)).toContain("다시 확인하는 중");
    expect(blockedReason({ action: "register", busy: true, needs: 0 }, ko)).toContain("다시 확인하는 중");
  });

  it("does not let a stop that needs review be locked — it must be fixed first", () => {
    expect(blockedReason({ action: "lock", item: review, busy: false }, ko)).toBe("확인이 필요한 일정은 먼저 고쳐야 고정할 수 있어요");
    expect(blockedReason({ action: "lock", item: settled, busy: false }, ko)).toBeNull();
  });

  it("explains a stop that cannot be locked for another reason (no settled place) without calling it 'needs review'", () => {
    expect(blockedReason({ action: "lock", item: { status: "keep", locked: false, can_lock: false }, busy: false }, ko)).toBe("장소가 정해진 일정만 고정할 수 있어요");
  });

  it("always lets a locked stop be unlocked", () => {
    expect(blockedReason({ action: "lock", item: locked, busy: false }, ko)).toBeNull();
  });

  it("does not let a locked stop be edited, auto-fixed or deleted, and says how to get out of it", () => {
    for (const action of ["edit", "auto"] as const) expect(blockedReason({ action, item: locked, busy: false }, ko)).toContain("잠금을 풀면 수정할 수 있어요");
    expect(blockedReason({ action: "delete", item: locked, busy: false }, ko)).toContain("잠금을 먼저 풀어 주세요");
    expect(blockedReason({ action: "edit", item: settled, busy: false }, ko)).toBeNull();
  });

  it("says nothing to fix for 'auto-fix all', and how many are left for 'register'", () => {
    expect(blockedReason({ action: "autoAll", busy: false, needs: 0 }, ko)).toBe("고칠 곳이 없어요");
    expect(blockedReason({ action: "autoAll", busy: false, needs: 2 }, ko)).toBeNull();
    expect(blockedReason({ action: "register", busy: false, needs: 2 }, ko)).toContain("2건");
    expect(blockedReason({ action: "register", busy: false, needs: 0 }, ko)).toBeNull();
  });

  it("says it in English too", () => {
    expect(blockedReason({ action: "lock", item: review, busy: false }, en)).toContain("must be fixed");
  });
});

describe("what is said after an action", () => {
  it("says a lock and an unlock, with the name and the particle", () => {
    expect(said.locked("경복궁", ko).message).toBe("경복궁을 꼭 넣을 일정으로 고정했어요");
    expect(said.unlocked("경복궁", ko).message).toBe("경복궁 고정을 풀었어요");
    expect(said.removed("올리브영", ko).message).toBe("올리브영 일정을 삭제했어요");
  });

  it("says a change of place with both names, and whether it was the top alternative", () => {
    expect(said.changedPlace("올리브영 인사동점", "올리브영 광화문점", "auto", ko).message).toBe("올리브영 인사동점을 올리브영 광화문점으로 바꿨어요");
    expect(said.changedPlace("광장시장", "통인시장", "auto", ko).sub).toContain("대체 후보 1순위");
    expect(said.changedPlace("광장시장", "통인시장", "pick", ko).sub).not.toContain("1순위");
    expect(said.changedPlace("A", "B", "pick", en).message).toBe("Changed A to B");
  });

  it("asks the delete question with the stop's name", () => {
    expect(deleteQuestion("경복궁", "1일차 10:00–11:30", ko)).toEqual({ title: "경복궁 일정을 삭제하시겠습니까?", detail: "1일차 10:00–11:30" });
  });
});

describe("what is said after the whole plan is fixed at once", () => {
  const change = (title: string, from: string | null, to: string, starts: string, ends: string): AutofixChange => ({
    id: "0-1", source_id: "s1", index: 1, title,
    from: { place: from ? { name: from, latitude: 37.57, longitude: 126.98, source: "kakao" } : null, starts_at: "11:00", ends_at: "12:30" },
    to: { place: { name: to, latitude: 37.5717, longitude: 126.9791, source: "kakao" }, starts_at: starts, ends_at: ends }, reason: "place_and_time",
  });

  it("names the places by their names (the answer carries places, not strings) and the new time", () => {
    const text = said.autofixed([change("올리브영", "올리브영 인사동점", "올리브영 광화문점", "11:45", "12:15")], 2, 0, ko);
    expect(text.message).toBe("확인이 필요한 2건을 검증된 대체 일정으로 바꿨어요");
    expect(text.sub).toBe("올리브영 인사동점 → 올리브영 광화문점 11:45–12:15");
    expect(text.sub).not.toContain("[object");
  });

  it("falls back to the stop's title when it had no place, lists three and counts the rest, and says how many stayed", () => {
    const many = [change("a", null, "A", "09:00", "10:00"), change("b", "B0", "B", "10:00", "11:00"), change("c", "C0", "C", "11:00", "12:00"), change("d", "D0", "D", "12:00", "13:00")];
    const text = said.autofixed(many, 4, 1, ko);
    expect(text.sub?.split(" · ")).toEqual(["a → A 09:00–10:00", "B0 → B 10:00–11:00", "C0 → C 11:00–12:00", "외 1곳", "1곳은 그대로"]);
  });

  it("says why nothing could be changed, in the server's reasons, without the 'nothing to change' filler", () => {
    expect(said.autofixNothing([{ reason: "locked" }, { reason: "no_candidates" }, { reason: "locked" }, { reason: "nothing_to_change" }], ko))
      .toEqual({ message: "바꿀 수 있는 대체 일정이 없어요", sub: "고정한 일정이에요 · 대체 후보가 없어요" });
    expect(said.autofixNothing([{ reason: "nothing_to_change" }], ko).sub).toBeUndefined();
  });

  it("says a recheck passed, or what is left", () => {
    expect(said.revalidated(true, 0, ko).message).toBe("재검증을 통과했어요");
    expect(said.revalidated(false, 2, ko).sub).toBe("확인이 필요한 항목 2건이 남아 있어요");
    expect(said.revalidated(false, 0, ko).sub).toBe("위의 확인할 것을 먼저 채워 주세요");
  });
});
