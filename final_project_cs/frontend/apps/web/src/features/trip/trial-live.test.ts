import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import { trialLive } from "@/lib/live/gateway";
import type { TripStop } from "./model";
import { trialLiveText } from "./trip-rows";

// `[2026-10-19 사용자 지시]` 캐치테이블 시험 값(제휴 전제 시험) — 서버가 보낸 지금 값만 한 줄로 말하고, 모양이 다른 것은 버린다.
const ko = translator("ko");
const stop = (trial: TripStop["trialLive"]): TripStop => ({ id: "s", date: "2026-10-20", time: "12:00", title: "메이플탑", booking: "unknown", notes: "", trialLive: trial });

describe("trial readings from the server", () => {
  it("keeps readings it can say and drops the rest", () => {
    expect(trialLive([
      { topic: "waiting", state: "yes", num: 41, asked_at: "2026-10-20T12:03:00+09:00" },
      { topic: "vacancy", state: "no", num: null, asked_at: "2026-10-20T12:03:00+09:00" },
      { topic: "hours", state: "yes", asked_at: "2026-10-20T12:03:00+09:00" },
      { topic: "waiting", state: "unknown", asked_at: "2026-10-20T12:03:00+09:00" },
      { topic: "waiting", state: "yes", num: 3 },
      { topic: "waiting", state: "yes", num: -1, asked_at: "2026-10-20T12:03:00+09:00" },
    ])).toEqual([
      { topic: "waiting", state: "yes", num: 41, askedAt: "2026-10-20T12:03:00+09:00" },
      { topic: "vacancy", state: "no", num: null, askedAt: "2026-10-20T12:03:00+09:00" },
      { topic: "waiting", state: "yes", num: null, askedAt: "2026-10-20T12:03:00+09:00" },
    ]);
  });

  it("is empty when the server sent nothing (switch off)", () => {
    expect(trialLive(undefined)).toEqual([]);
  });
});

describe("the card's trial line", () => {
  const now = Date.parse("2026-10-20T12:06:30+09:00");

  it("says the waiting line, the tables and how long ago it was read", () => {
    expect(trialLiveText(stop([
      { topic: "waiting", state: "yes", num: 41, askedAt: "2026-10-20T12:03:00+09:00" },
      { topic: "vacancy", state: "yes", num: null, askedAt: "2026-10-20T12:02:00+09:00" },
    ]), ko, now)).toBe("웨이팅 41팀 · 예약 가능한 시간 있음 · 3분 전 확인");
  });

  it("says no line and no tables, and 「방금」 under a minute", () => {
    expect(trialLiveText(stop([
      { topic: "waiting", state: "no", num: null, askedAt: "2026-10-20T12:06:00+09:00" },
      { topic: "vacancy", state: "no", num: null, askedAt: "2026-10-20T12:06:00+09:00" },
    ]), ko, now)).toBe("웨이팅 없음 · 지금 예약 가능한 시간 없음 · 방금 확인");
  });

  it("has no line without readings", () => {
    expect(trialLiveText(stop(undefined), ko, now)).toBeNull();
    expect(trialLiveText(stop([]), ko, now)).toBeNull();
  });
});
