import { describe, expect, it } from "vitest";
import type { Trip, TripStop } from "./model";
import { liveStop, ownNotice, progressToast } from "./stop-progress";
import { dayTimeline, entryTimes } from "./trip-timeline";

const t = (ko: string) => ko;
const stop = (id: string, time: string, endTime?: string, more: Partial<TripStop> = {}): TripStop =>
  ({ id, date: "2026-10-22", time, endTime, title: id, booking: "unknown", notes: "", ...more });
const day = (stops: TripStop[]): Pick<Trip, "stops" | "moves" | "legs"> => ({
  stops,
  moves: [{ id: "m1", fromId: "북촌", toId: "인사동", date: "2026-10-22", departAt: "11:30", arriveAt: "11:45", title: "북촌 → 인사동" }],
  legs: {},
});
const at = (trip: Pick<Trip, "stops" | "moves" | "legs">, hm: string) => {
  const entries = dayTimeline(trip, "2026-10-22");
  const [h, m] = hm.split(":").map(Number);
  return liveStop(entries, entryTimes(entries, "2026-10-22", { date: "2026-10-22", minute: h * 60 + m }));
};

// `[2026-10-22 사용자 결정 — ST4F-716]` 진행 중 카드 · 「끝났어요」 — mockups/tripilot-trip-now-done.html
describe("the stop going on now", () => {
  const plan = day([stop("호텔 조식", "09:00", "09:30"), stop("북촌", "10:00", "11:30"), stop("인사동", "12:00", "13:00"), stop("창덕궁", "14:00", "15:30")]);

  it("is the stop whose start has passed and whose end has not, with the day's next stop to start", () => {
    expect(at(plan, "10:50")).toMatchObject({ stop: { id: "북촌" }, next: { id: "인사동" }, fixed: false });
  });

  it("is none between stops, before the day's first and after its last", () => {
    expect(at(plan, "11:40")).toBeNull();          // 이동 중
    expect(at(plan, "08:30")).toBeNull();
    expect(at(plan, "15:31")).toBeNull();
  });

  it("has no next stop on the day's last stop — 「끝났어요」 then asks nothing", () => {
    expect(at(plan, "14:05")).toMatchObject({ stop: { id: "창덕궁" }, next: null, fixed: false });
  });

  it("marks a booked or pinned next stop as fixed — the server keeps its time", () => {
    const booked = day([stop("북촌", "10:00", "11:30"), stop("인사동", "12:00", "13:00", { booking: "booked" })]);
    const pinned = day([stop("북촌", "10:00", "11:30"), stop("인사동", "12:00", "13:00", { pinned: true })]);
    expect(at(booked, "10:50")?.fixed).toBe(true);
    expect(at(pinned, "10:50")?.fixed).toBe(true);
  });

  it("is not a stop paused for a disaster", () => {
    expect(at(day([stop("북촌", "10:00", "11:30", { paused: true }), stop("인사동", "12:00", "13:00")]), "10:50")).toBeNull();
  });

  it("is over once the server recorded an earlier end (the stop then ends at that time)", () => {
    expect(at(day([stop("북촌", "10:00", "10:50"), stop("인사동", "12:00", "13:00")]), "10:50")).toBeNull();
  });
});

describe("what came of 「끝났어요」", () => {
  it("says the server's sentence: moved → 바뀜, kept → 확인 필요, only the end → the sentence alone", () => {
    expect(progressToast({ status: "adjusted", text: "북촌을 10:50에 마쳤고 …", state: "departing" }, t))
      .toEqual({ text: "북촌을 10:50에 마쳤고 …", chip: { text: "바뀜", tone: "changed" } });
    expect(progressToast({ status: "adjusted", text: "북촌은 완료했어요. …", navigation: "hours_conflict" }, t))
      .toEqual({ text: "북촌은 완료했어요. …", chip: { text: "확인 필요", tone: "warn" } });
    expect(progressToast({ status: "adjusted", text: "북촌을 10:50에 완료한 것으로 반영했어요.", state: "completed" }, t))
      .toEqual({ text: "북촌을 10:50에 완료한 것으로 반영했어요." });
  });
});

// `[2026-10-22 사용자 결정 — A]` 이 기기에서 누른 결과는 결과 토스트만 — 그 판의 변경 알림은 막대로 다시 띄우지 않는다
describe("the change notice of this device's own report", () => {
  const own = new Set([4]);
  it("is the change notice of a version this device wrote", () => {
    expect(ownNotice({ type: "change_notice", version: 4 }, own)).toBe(true);
  });
  it("is not a change from elsewhere, another kind of notice, or a notice with no version", () => {
    expect(ownNotice({ type: "change_notice", version: 5 }, own)).toBe(false);
    expect(ownNotice({ type: "proposal_request", version: 4 }, own)).toBe(false);
    expect(ownNotice({ type: "change_notice", version: null }, own)).toBe(false);
  });
});
