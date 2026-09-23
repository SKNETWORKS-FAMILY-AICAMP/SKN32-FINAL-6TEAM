import { beforeEach, describe, expect, it } from "vitest";
import { createDemoGateway, DEMO_STORAGE_PREFIX, DEMO_VERIFICATION_DURATION, SAMPLE_PLAN, type DemoStorage } from "./index";

function memoryStorage(): DemoStorage & { items: Map<string, string> } {
  const items = new Map<string, string>();
  return { items, getItem: (key) => items.get(key) ?? null, setItem: (key, value) => { items.set(key, value); } };
}

describe("demo trip gateway", () => {
  let storage: ReturnType<typeof memoryStorage>;
  let clock: number;
  let gateway: ReturnType<typeof createDemoGateway>;

  beforeEach(() => {
    storage = memoryStorage();
    clock = Date.UTC(2026, 8, 15);
    gateway = createDemoGateway({ storage, now: () => clock, delay: async () => {} });
  });

  it("rejects absent, malformed and mismatched trip IDs without inventing a trip", async () => {
    await expect(gateway.getTrip(crypto.randomUUID())).rejects.toMatchObject({ code: "NOT_FOUND" });
    await expect(gateway.getTrip("../../other-storage")).rejects.toMatchObject({ code: "NOT_FOUND" });
    const trip = await gateway.createTrip({ source: SAMPLE_PLAN });
    const wrongId = crypto.randomUUID();
    storage.setItem(DEMO_STORAGE_PREFIX + wrongId, storage.getItem(DEMO_STORAGE_PREFIX + trip.id)!);
    await expect(gateway.getTrip(wrongId)).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
  });

  it("reports corrupt JSON and schema-invalid data without replacing either", async () => {
    const trip = await gateway.createTrip({ source: SAMPLE_PLAN });
    const key = DEMO_STORAGE_PREFIX + trip.id;
    for (const value of ["{broken", JSON.stringify({ version: 2, trip })]) {
      storage.setItem(key, value);
      await expect(gateway.getTrip(trip.id)).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
      expect(storage.getItem(key)).toBe(value);
    }
  });

  it("reports unavailable or full browser storage", async () => {
    const unavailable = createDemoGateway({ storage: () => { throw new Error("denied"); } });
    await expect(unavailable.createTrip({ source: SAMPLE_PLAN })).rejects.toMatchObject({ code: "STORAGE_UNAVAILABLE" });
    const full = createDemoGateway({ storage: { getItem: () => null, setItem: () => { throw new Error("quota"); } } });
    await expect(full.createTrip({ source: SAMPLE_PLAN })).rejects.toMatchObject({ code: "STORAGE_UNAVAILABLE" });
  });

  it("rejects completed storage with empty or missing verification results", async () => {
    const created = await gateway.createTrip({ source: SAMPLE_PLAN });
    clock += DEMO_VERIFICATION_DURATION;
    await gateway.getTrip(created.id);
    const key = DEMO_STORAGE_PREFIX + created.id;
    const original = storage.getItem(key)!;
    for (const length of [0, created.stops.length - 1]) {
      const stored = JSON.parse(original);
      stored.trip.verification.results = stored.trip.verification.results.slice(0, length);
      storage.setItem(key, JSON.stringify(stored));
      await expect(gateway.startTrip(created.id)).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
    }
  });

  it("rejects duplicated result coverage and unchanged times that disagree with the itinerary", async () => {
    const created = await gateway.createTrip({ source: SAMPLE_PLAN });
    clock += DEMO_VERIFICATION_DURATION;
    await gateway.getTrip(created.id);
    const key = DEMO_STORAGE_PREFIX + created.id;
    const original = storage.getItem(key)!;
    const duplicate = JSON.parse(original);
    duplicate.trip.verification.results[1] = duplicate.trip.verification.results[0];
    storage.setItem(key, JSON.stringify(duplicate));
    await expect(gateway.getTrip(created.id)).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
    const inconsistent = JSON.parse(original);
    const unchanged = inconsistent.trip.verification.results.find((result: { status: string }) => result.status === "unchanged");
    unchanged.proposedValue = "00:00";
    storage.setItem(key, JSON.stringify(inconsistent));
    await expect(gateway.getTrip(created.id)).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
  });

  it("restores progress after reload and never moves it backward", async () => {
    const created = await gateway.createTrip({ source: SAMPLE_PLAN });
    expect(created.verification.progress).toBe(0);
    clock += DEMO_VERIFICATION_DURATION / 2;
    const reloaded = createDemoGateway({ storage, now: () => clock });
    const half = await reloaded.getTrip(created.id);
    expect(half.verification.progress).toBe(50);
    expect(half.verification.stages.map((stage) => stage.status)).toEqual(["completed", "running", "pending", "pending"]);
    clock -= 1000;
    expect((await reloaded.getTrip(created.id)).verification.progress).toBe(50);
  });

  it("applies multiple example results consistently and preserves all reserved times", async () => {
    const created = await gateway.createTrip({ source: SAMPLE_PLAN });
    clock += DEMO_VERIFICATION_DURATION;
    const ready = await gateway.getTrip(created.id);
    const changed = ready.verification.results.filter((result) => result.status === "adjusted");
    expect(changed).toHaveLength(2);
    expect(ready.verification.results).toHaveLength(created.stops.length);
    expect(ready.verification.stages.every((stage) => stage.status === "completed")).toBe(true);
    expect(ready.status).toBe("ready");
    for (const result of changed) {
      const stop = ready.stops.find((item) => item.id === result.stopId)!;
      expect(stop.time).toBe(result.proposedValue);
      expect(stop.originalTime).toBe(result.originalValue);
      expect(stop.booking).toBe("none");
    }
    for (const stop of created.stops.filter((item) => item.booking === "booked")) {
      expect(ready.stops.find((item) => item.id === stop.id)?.time).toBe(stop.time);
    }
    const active = await gateway.startTrip(created.id);
    expect(active.status).toBe("active");
    expect(active.stops).toEqual(ready.stops);
    expect((await gateway.startTrip(created.id)).messages).toHaveLength(1);
  });

  it("blocks management at the adapter boundary even for a 100% incomplete result", async () => {
    const created = await gateway.createTrip({ source: SAMPLE_PLAN, scenario: "needs-review" });
    await expect(gateway.startTrip(created.id)).rejects.toMatchObject({ code: "NOT_READY" });
    clock += DEMO_VERIFICATION_DURATION;
    const reviewed = await gateway.getTrip(created.id);
    expect(reviewed.verification.progress).toBe(100);
    expect(reviewed.verification.results.some((result) => result.status === "needs_review")).toBe(true);
    await expect(gateway.startTrip(created.id)).rejects.toMatchObject({ code: "VERIFICATION_BLOCKED" });
    expect((await gateway.getTrip(created.id)).status).toBe("ready");
  });

  it("preserves identity and source on failure/retry, then completes only one adjustment pass", async () => {
    const created = await gateway.createTrip({ source: SAMPLE_PLAN, scenario: "failed" });
    clock += DEMO_VERIFICATION_DURATION;
    const failed = await gateway.getTrip(created.id);
    expect(failed.status).toBe("failed");
    expect(failed.verification.progress).toBe(55);
    await expect(gateway.startTrip(created.id)).rejects.toMatchObject({ code: "NOT_READY" });
    const retried = await gateway.retryVerification(created.id);
    expect(retried.id).toBe(created.id);
    expect(retried.source).toBe(created.source);
    expect(retried.stops).toEqual(created.stops);
    expect(retried.verification.progress).toBe(0);
    clock += DEMO_VERIFICATION_DURATION;
    const completed = await gateway.getTrip(created.id);
    expect(completed.status).toBe("ready");
    expect((await gateway.getTrip(created.id)).stops).toEqual(completed.stops);
  });

  it("restores original times before retrying incomplete results", async () => {
    const created = await gateway.createTrip({ source: SAMPLE_PLAN, scenario: "needs-review" });
    clock += DEMO_VERIFICATION_DURATION;
    const incomplete = await gateway.getTrip(created.id);
    expect(incomplete.stops.some((stop) => stop.originalTime)).toBe(true);
    const retried = await gateway.retryVerification(created.id);
    expect(retried.stops).toEqual(created.stops);
    clock += DEMO_VERIFICATION_DURATION;
    const completed = await gateway.getTrip(created.id);
    expect(completed.verification.results.some((result) => result.status === "needs_review")).toBe(false);
    await expect(gateway.startTrip(created.id)).resolves.toMatchObject({ status: "active" });
  });

  it("parses typed custom plans and never swaps them for sample stops", async () => {
    const source = "1일차 · 2026-12-24\n9:05 제주 작은 책방 · 예약 없음\n11:30 바닷가 카페 · 예약 있음\n\n2일차\n10:00 돌담 산책";
    const created = await gateway.createTrip({ source });
    expect(created.source).toBe(source);
    expect(created.stops.map((stop) => stop.title)).toEqual(["제주 작은 책방", "바닷가 카페", "돌담 산책"]);
    expect(created.stops.map((stop) => stop.booking)).toEqual(["none", "booked", "unknown"]);
    expect(created.startDate).toBe("2026-12-24");
    expect(created.endDate).toBe("2026-12-25");
    clock += DEMO_VERIFICATION_DURATION;
    const ready = await gateway.getTrip(created.id);
    expect(ready.stops[0].time).toBe("09:20");
    expect(ready.stops[1].time).toBe("11:30");
    expect(ready.stops[2].time).toBe("10:00");
  });

  it.each([
    "",
    "1일차 · 2026-02-30\n09:00 책방",
    "09:00 날짜 없는 책방",
    "1일차 · 2026-12-24\n25:00 책방",
    "1일차 · 2026-12-24\n09:00 책방\n시간 없는 카페",
    "1일차 · 2026-12-24\n15:00 책방 · 14:00 종료",
  ])("rejects incomplete typed source without silently dropping lines: %s", async (source) => {
    await expect(gateway.createTrip({ source })).rejects.toMatchObject({ code: "INVALID_INPUT" });
    expect(storage.items.size).toBe(0);
  });

  it("does not move late or tightly spaced stops across a date or next stop", async () => {
    const created = await gateway.createTrip({ source: "1일차 · 2026-12-24\n09:00 서점 · 예약 없음\n09:10 카페 · 예약 있음\n23:50 호텔 · 예약 없음" });
    clock += DEMO_VERIFICATION_DURATION;
    const ready = await gateway.getTrip(created.id);
    expect(ready.verification.results.every((result) => result.status === "unchanged")).toBe(true);
  });

  it("labels demo chat, keeps typed messages and persists them after reload", async () => {
    const created = await gateway.createTrip({ source: SAMPLE_PLAN });
    await expect(gateway.sendMessage(created.id, "예약 목록")).rejects.toMatchObject({ code: "NOT_READY" });
    clock += DEMO_VERIFICATION_DURATION;
    await gateway.startTrip(created.id);
    const chat = await gateway.sendMessage(created.id, "예약 목록");
    expect(chat.messages.at(-2)?.text).toBe("예약 목록");
    expect(chat.messages.at(-1)?.text).toContain("[데모 응답 · 실제 AI 연결 전]");
    expect(chat.messages.at(-1)?.text).toContain("이촌동 점심 식당");
    const reloaded = createDemoGateway({ storage, now: () => clock });
    expect((await reloaded.getTrip(created.id)).messages).toEqual(chat.messages);
  });

  it("scopes quick prompts and identically named stops to the requested date and time", async () => {
    const created = await gateway.createTrip({ source: SAMPLE_PLAN });
    clock += DEMO_VERIFICATION_DURATION;
    await gateway.startTrip(created.id);
    const daily = await gateway.sendMessage(created.id, "2026-09-16 하루 일정 요약을 알려 주세요.");
    expect(daily.messages.at(-1)?.text).toContain("2일차 · 2026-09-16");
    expect(daily.messages.at(-1)?.text).not.toContain("성수동 쇼핑");
    const reservations = await gateway.sendMessage(created.id, "2026-09-16 예약 일정 확인을 해 주세요.");
    expect(reservations.messages.at(-1)?.text).toContain("이촌동 점심 식당");
    expect(reservations.messages.at(-1)?.text).not.toContain("성수 예약 식당");
    const stop = await gateway.sendMessage(created.id, "2026-09-16 09:00 호텔 조식 일정의 상세와 확인할 조건을 알려 주세요.");
    expect(stop.messages.at(-1)?.text).toContain("2026-09-16 09:00");
    expect(stop.messages.at(-1)?.text).not.toContain("2026-09-15");
  });

  it("numbers nonconsecutive itinerary days by calendar date in chat", async () => {
    const created = await gateway.createTrip({ source: "1일차 · 2026-12-24\n09:00 서점\n\n3일차 · 2026-12-26\n10:00 카페" });
    clock += DEMO_VERIFICATION_DURATION;
    await gateway.startTrip(created.id);
    const chat = await gateway.sendMessage(created.id, "2026-12-26 하루 일정 요약을 알려 주세요.");
    expect(chat.messages.at(-1)?.text).toContain("3일차 · 2026-12-26");
    expect(chat.messages.at(-1)?.text).not.toContain("2일차");
  });
});
