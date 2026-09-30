import { beforeEach, describe, expect, it } from "vitest";
import { initialAnswers, toggle } from "../../features/onboarding/model";
import { toSurvey, type TripSurvey } from "../../features/onboarding/payload";
import type { DemoScenario } from "../../features/trip/model";
import { createDemoGateway, DEMO_STORAGE_PREFIX, DEMO_VERIFICATION_DURATION, SAMPLE_PLANS, type DemoStorage } from "./index";

function memoryStorage(): DemoStorage & { items: Map<string, string> } {
  const items = new Map<string, string>();
  return {
    items, getItem: (key) => items.get(key) ?? null, setItem: (key, value) => { items.set(key, value); }, removeItem: (key) => { items.delete(key); },
    get length() { return items.size; }, key: (index) => [...items.keys()][index] ?? null,
  };
}

describe("demo trip gateway", () => {
  let storage: ReturnType<typeof memoryStorage>;
  let clock: number;
  let gateway: ReturnType<typeof createDemoGateway>;
  const SAMPLE = SAMPLE_PLANS.ko;

  beforeEach(() => {
    storage = memoryStorage();
    clock = Date.UTC(2026, 8, 15);
    gateway = createDemoGateway({ storage, now: () => clock, delay: async () => {} });
  });

  async function activeTrip(source = SAMPLE, language: "ko" | "en" = "ko") {
    const created = await gateway.createTrip({ source }, language);
    clock += DEMO_VERIFICATION_DURATION;
    return gateway.startTrip(created.id, language);
  }

  it("rejects absent, malformed and mismatched trip IDs without inventing a trip", async () => {
    await expect(gateway.getTrip(crypto.randomUUID(), "ko")).rejects.toMatchObject({ code: "NOT_FOUND" });
    await expect(gateway.getTrip("../../other-storage", "ko")).rejects.toMatchObject({ code: "NOT_FOUND" });
    const trip = await gateway.createTrip({ source: SAMPLE }, "ko");
    const wrongId = crypto.randomUUID();
    storage.setItem(DEMO_STORAGE_PREFIX + wrongId, storage.getItem(DEMO_STORAGE_PREFIX + trip.id)!);
    await expect(gateway.getTrip(wrongId, "ko")).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
  });

  it("reports corrupt JSON, schema-invalid and earlier-format data without replacing either", async () => {
    const trip = await gateway.createTrip({ source: SAMPLE }, "ko");
    const key = DEMO_STORAGE_PREFIX + trip.id;
    const earlier = JSON.parse(storage.getItem(key)!);
    earlier.version = 1;
    for (const value of ["{broken", JSON.stringify({ version: 2, trip }), JSON.stringify(earlier)]) {
      storage.setItem(key, value);
      await expect(gateway.getTrip(trip.id, "ko")).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
      expect(storage.getItem(key)).toBe(value);
    }
  });

  it("reports unavailable or full browser storage", async () => {
    const unavailable = createDemoGateway({ storage: () => { throw new Error("denied"); } });
    await expect(unavailable.createTrip({ source: SAMPLE }, "ko")).rejects.toMatchObject({ code: "STORAGE_UNAVAILABLE" });
    const full = createDemoGateway({ storage: { getItem: () => null, setItem: () => { throw new Error("quota"); }, removeItem: () => {}, length: 0, key: () => null } });
    await expect(full.createTrip({ source: SAMPLE }, "ko")).rejects.toMatchObject({ code: "STORAGE_UNAVAILABLE" });
    await expect(unavailable.listTrips("ko")).rejects.toMatchObject({ code: "STORAGE_UNAVAILABLE" });
  });

  it("lists this tab's trips newest first, named by their dates, ignoring other storage", async () => {
    expect(await gateway.listTrips("ko")).toEqual([]);
    const first = await gateway.createTrip({ source: SAMPLE }, "ko");
    clock += 60_000;
    const second = await gateway.createTrip({ source: "2026-10-01\n09:00 경복궁" }, "ko");
    storage.setItem("tripilot.web-mvp.draft", "작성 중인 글");
    const trips = await gateway.listTrips("ko");
    expect(trips.map((trip) => trip.id)).toEqual([second.id, first.id]);
    expect(trips[0]).toEqual({ id: second.id, title: "2026-10-01 여행", createdAt: new Date(clock).toISOString(), version: null });
    expect(trips[1].title).toBe("2026-09-15 – 2026-09-16 여행");
    expect((await gateway.listTrips("en"))[1].title).toBe("Trip · 2026-09-15 – 2026-09-16");
  });

  it("lists a trip saved before registration time was kept last, with no time, and reports a corrupt one", async () => {
    const older = await gateway.createTrip({ source: SAMPLE }, "ko");
    const key = DEMO_STORAGE_PREFIX + older.id;
    const stored = JSON.parse(storage.getItem(key)!);
    delete stored.createdAt;
    storage.setItem(key, JSON.stringify(stored));
    const newer = await gateway.createTrip({ source: SAMPLE }, "ko");
    const trips = await gateway.listTrips("ko");
    expect(trips.map((trip) => [trip.id, trip.createdAt === null])).toEqual([[newer.id, false], [older.id, true]]);
    storage.setItem(key, "{broken");
    await expect(gateway.listTrips("ko")).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
  });

  it("deletes only the trip asked for — by ID, beside a trip with the same title — and keeps every other stored item", async () => {
    const first = await gateway.createTrip({ source: SAMPLE }, "ko");
    const twin = await gateway.createTrip({ source: SAMPLE }, "ko");
    storage.setItem("tripilot.web-mvp.draft", "작성 중인 글");
    const titles = (await gateway.listTrips("ko")).map((trip) => trip.title);
    expect(titles[0]).toBe(titles[1]);
    await expect(gateway.deleteTrip!(first.id, "ko")).resolves.toBeUndefined();
    expect((await gateway.listTrips("ko")).map((trip) => trip.id)).toEqual([twin.id]);
    await expect(gateway.getTrip(first.id, "en")).rejects.toMatchObject({ code: "NOT_FOUND" });
    expect([...storage.items.keys()].sort()).toEqual([DEMO_STORAGE_PREFIX + twin.id, "tripilot.web-mvp.draft"].sort());
  });

  it("refuses a missing or malformed ID and reports a storage failure, leaving the trip in place", async () => {
    const trip = await gateway.createTrip({ source: SAMPLE }, "ko");
    await expect(gateway.deleteTrip!(crypto.randomUUID(), "ko")).rejects.toMatchObject({ code: "NOT_FOUND" });
    await expect(gateway.deleteTrip!("../../tripilot.web.settings.v1", "ko")).rejects.toMatchObject({ code: "NOT_FOUND" });
    const locked = createDemoGateway({ storage: { getItem: (key) => storage.getItem(key), setItem: () => {}, removeItem: () => { throw new Error("denied"); }, length: 0, key: () => null } });
    await expect(locked.deleteTrip!(trip.id, "en")).rejects.toMatchObject({ code: "STORAGE_UNAVAILABLE", message: expect.stringContaining("could not be saved or loaded") });
    expect(storage.getItem(DEMO_STORAGE_PREFIX + trip.id)).not.toBeNull();
    await gateway.deleteTrip!(trip.id, "ko");
    await expect(gateway.deleteTrip!(trip.id, "ko")).rejects.toMatchObject({ code: "NOT_FOUND" });
  });

  it("a deleted trip is not written back by a check still running or by a chat reply that was waiting", async () => {
    const running = await gateway.createTrip({ source: SAMPLE }, "ko");
    clock += DEMO_VERIFICATION_DURATION / 2;
    await gateway.deleteTrip!(running.id, "ko");
    await expect(gateway.getTrip(running.id, "ko")).rejects.toMatchObject({ code: "NOT_FOUND" });
    const active = await activeTrip();
    const reply = gateway.sendMessage(active.id, "예약 목록", "ko");   // waits before it reads the trip again
    await gateway.deleteTrip!(active.id, "ko");
    await expect(reply).rejects.toMatchObject({ code: "NOT_FOUND" });
    expect(storage.items.size).toBe(0);
  });

  it("rejects completed storage with empty or missing verification results", async () => {
    const created = await gateway.createTrip({ source: SAMPLE }, "ko");
    clock += DEMO_VERIFICATION_DURATION;
    await gateway.getTrip(created.id, "ko");
    const key = DEMO_STORAGE_PREFIX + created.id;
    const original = storage.getItem(key)!;
    for (const length of [0, created.stops.length - 1]) {
      const stored = JSON.parse(original);
      stored.trip.verification.results = stored.trip.verification.results.slice(0, length);
      storage.setItem(key, JSON.stringify(stored));
      await expect(gateway.startTrip(created.id, "ko")).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
    }
  });

  it("rejects duplicated result coverage and unchanged times that disagree with the itinerary", async () => {
    const created = await gateway.createTrip({ source: SAMPLE }, "ko");
    clock += DEMO_VERIFICATION_DURATION;
    await gateway.getTrip(created.id, "ko");
    const key = DEMO_STORAGE_PREFIX + created.id;
    const original = storage.getItem(key)!;
    const duplicate = JSON.parse(original);
    duplicate.trip.verification.results[1] = duplicate.trip.verification.results[0];
    storage.setItem(key, JSON.stringify(duplicate));
    await expect(gateway.getTrip(created.id, "ko")).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
    const inconsistent = JSON.parse(original);
    const unchanged = inconsistent.trip.verification.results.find((result: { status: string }) => result.status === "unchanged");
    unchanged.proposedValue = "00:00";
    storage.setItem(key, JSON.stringify(inconsistent));
    await expect(gateway.getTrip(created.id, "ko")).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
  });

  it("restores progress after reload and never moves it backward", async () => {
    const created = await gateway.createTrip({ source: SAMPLE }, "ko");
    expect(created.verification.progress).toBe(0);
    clock += DEMO_VERIFICATION_DURATION / 2;
    const reloaded = createDemoGateway({ storage, now: () => clock });
    const half = await reloaded.getTrip(created.id, "ko");
    expect(half.verification.progress).toBe(50);
    expect(half.verification.stages.map((stage) => stage.status)).toEqual(["completed", "running", "pending", "pending"]);
    clock -= 1000;
    expect((await reloaded.getTrip(created.id, "ko")).verification.progress).toBe(50);
  });

  it("applies multiple example results consistently and preserves all reserved times", async () => {
    const created = await gateway.createTrip({ source: SAMPLE }, "ko");
    clock += DEMO_VERIFICATION_DURATION;
    const ready = await gateway.getTrip(created.id, "ko");
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
    const active = await gateway.startTrip(created.id, "ko");
    expect(active.status).toBe("active");
    expect(active.stops).toEqual(ready.stops);
    // Starting twice is harmless and adds nothing to the conversation.
    expect((await gateway.startTrip(created.id, "ko")).messages).toHaveLength(0);
  });

  it("speaks the reader's language on every read of the same stored trip", async () => {
    const created = await gateway.createTrip({ source: SAMPLE }, "ko");
    const running = await gateway.getTrip(created.id, "en");
    expect(running.verification.stages[0].label).toBe("Read your plan");
    clock += DEMO_VERIFICATION_DURATION;
    const korean = await gateway.getTrip(created.id, "ko");
    const english = await gateway.getTrip(created.id, "en");
    expect(english.verification.results.map((result) => result.status)).toEqual(korean.verification.results.map((result) => result.status));
    const adjusted = (trip: typeof korean) => trip.verification.results.find((result) => result.status === "adjusted")!;
    expect(adjusted(korean).reason).toContain("이동 여유 15분");
    expect(adjusted(english).reason).toContain("15-minute buffer");
    expect(english.verification.stages[3].label).toBe("Bring it all together");
  });

  it("blocks management at the adapter boundary even for a 100% incomplete result", async () => {
    const created = await gateway.createTrip({ source: SAMPLE, scenario: "needs-review" }, "ko");
    await expect(gateway.startTrip(created.id, "ko")).rejects.toMatchObject({ code: "NOT_READY" });
    clock += DEMO_VERIFICATION_DURATION;
    const reviewed = await gateway.getTrip(created.id, "ko");
    expect(reviewed.verification.progress).toBe(100);
    expect(reviewed.verification.results.some((result) => result.status === "needs_review")).toBe(true);
    await expect(gateway.startTrip(created.id, "ko")).rejects.toMatchObject({ code: "VERIFICATION_BLOCKED" });
    expect((await gateway.getTrip(created.id, "ko")).status).toBe("ready");
  });

  it("preserves identity and source on failure/retry, then completes only one adjustment pass", async () => {
    const created = await gateway.createTrip({ source: SAMPLE, scenario: "failed" }, "ko");
    clock += DEMO_VERIFICATION_DURATION;
    const failed = await gateway.getTrip(created.id, "en");
    expect(failed.status).toBe("failed");
    expect(failed.verification.progress).toBe(55);
    expect(failed.verification.error).toContain("interrupted check");
    await expect(gateway.startTrip(created.id, "ko")).rejects.toMatchObject({ code: "NOT_READY" });
    const retried = await gateway.retryVerification(created.id, "ko");
    expect(retried.id).toBe(created.id);
    expect(retried.source).toBe(created.source);
    expect(retried.stops).toEqual(created.stops);
    expect(retried.verification.progress).toBe(0);
    clock += DEMO_VERIFICATION_DURATION;
    const completed = await gateway.getTrip(created.id, "ko");
    expect(completed.status).toBe("ready");
    expect((await gateway.getTrip(created.id, "ko")).stops).toEqual(completed.stops);
  });

  it("restores original times before retrying incomplete results", async () => {
    const created = await gateway.createTrip({ source: SAMPLE, scenario: "needs-review" }, "ko");
    clock += DEMO_VERIFICATION_DURATION;
    const incomplete = await gateway.getTrip(created.id, "ko");
    expect(incomplete.stops.some((stop) => stop.originalTime)).toBe(true);
    const retried = await gateway.retryVerification(created.id, "ko");
    expect(retried.stops).toEqual(created.stops);
    clock += DEMO_VERIFICATION_DURATION;
    const completed = await gateway.getTrip(created.id, "ko");
    expect(completed.verification.results.some((result) => result.status === "needs_review")).toBe(false);
    await expect(gateway.startTrip(created.id, "ko")).resolves.toMatchObject({ status: "active" });
  });

  it("parses typed custom plans and never swaps them for sample stops", async () => {
    const source = "1일차 · 2026-12-24\n9:05 제주 작은 책방 · 예약 없음\n11:30 바닷가 카페 · 예약 있음\n\n2일차\n10:00 돌담 산책";
    const created = await gateway.createTrip({ source }, "ko");
    expect(created.source).toBe(source);
    expect(created.stops.map((stop) => stop.title)).toEqual(["제주 작은 책방", "바닷가 카페", "돌담 산책"]);
    expect(created.stops.map((stop) => stop.booking)).toEqual(["none", "booked", "unknown"]);
    expect(created.startDate).toBe("2026-12-24");
    expect(created.endDate).toBe("2026-12-25");
    clock += DEMO_VERIFICATION_DURATION;
    const ready = await gateway.getTrip(created.id, "ko");
    expect(ready.stops[0].time).toBe("09:20");
    expect(ready.stops[1].time).toBe("11:30");
    expect(ready.stops[2].time).toBe("10:00");
  });

  it("reads the English sample's headings, end times and booking notes", async () => {
    const created = await gateway.createTrip({ source: SAMPLE_PLANS.en }, "en");
    expect(created.stops).toHaveLength(14);
    expect(created.stops[1]).toMatchObject({ title: "Jamsil Sky Tower", endTime: "10:45" });
    expect(created.stops.find((stop) => stop.title === "Seongsu restaurant")?.booking).toBe("booked");
    expect(created.stops.find((stop) => stop.title === "Dinner near Seoul Station")?.booking).toBe("none");
    expect(created.stops.find((stop) => stop.title === "Hotel breakfast")?.booking).toBe("none");
    const notBooked = await gateway.createTrip({ source: "DAY 1 · 2026-12-24\n09:00 Book shop · not booked" }, "en");
    expect(notBooked.stops[0].booking).toBe("none");
  });

  it.each([
    "",
    "1일차 · 2026-02-30\n09:00 책방",
    "09:00 날짜 없는 책방",
    "1일차 · 2026-12-24\n25:00 책방",
    "1일차 · 2026-12-24\n09:00 책방\n시간 없는 카페",
    "1일차 · 2026-12-24\n15:00 책방 · 14:00 종료",
  ])("rejects incomplete typed source without silently dropping lines: %s", async (source) => {
    await expect(gateway.createTrip({ source }, "ko")).rejects.toMatchObject({ code: "INVALID_INPUT" });
    expect(storage.items.size).toBe(0);
  });

  it("explains input problems in the reader's language and rejects unknown scenarios", async () => {
    await expect(gateway.createTrip({ source: "" }, "en")).rejects.toMatchObject({ message: "Enter a travel plan with times and places." });
    await expect(gateway.createTrip({ source: "DAY 1 · 2026-02-30\n09:00 Book shop" }, "en")).rejects.toMatchObject({ message: "Line 1: Add a valid date (YYYY-MM-DD) to the day heading." });
    await expect(gateway.createTrip({ source: "1일차 · 2026-02-30\n09:00 책방" }, "ko")).rejects.toMatchObject({ message: "1번째 줄: 일차 제목에 올바른 날짜(YYYY-MM-DD)를 적어 주세요." });
    await expect(gateway.createTrip({ source: SAMPLE, scenario: "surprise" as DemoScenario }, "ko")).rejects.toMatchObject({ code: "INVALID_INPUT" });
    expect(storage.items.size).toBe(0);
  });

  it("does not move late or tightly spaced stops across a date or next stop", async () => {
    const created = await gateway.createTrip({ source: "1일차 · 2026-12-24\n09:00 서점 · 예약 없음\n09:10 카페 · 예약 있음\n23:50 호텔 · 예약 없음" }, "ko");
    clock += DEMO_VERIFICATION_DURATION;
    const ready = await gateway.getTrip(created.id, "ko");
    expect(ready.verification.results.every((result) => result.status === "unchanged")).toBe(true);
  });

  it("keeps typed messages and replies after reload, and only after the trip starts", async () => {
    const created = await gateway.createTrip({ source: SAMPLE }, "ko");
    await expect(gateway.sendMessage(created.id, "예약 목록", "ko")).rejects.toMatchObject({ code: "NOT_READY" });
    clock += DEMO_VERIFICATION_DURATION;
    await gateway.startTrip(created.id, "ko");
    const chat = await gateway.sendMessage(created.id, "예약 목록", "ko");
    expect(chat.messages.at(-2)?.text).toBe("예약 목록");
    expect(chat.messages.at(-1)?.text).toContain("13:00 · 성수 예약 식당");
    const reloaded = createDemoGateway({ storage, now: () => clock });
    expect((await reloaded.getTrip(created.id, "ko")).messages).toEqual(chat.messages);
    await expect(gateway.sendMessage(created.id, "   ", "ko")).rejects.toMatchObject({ code: "INVALID_INPUT" });
  });

  it("scopes quick prompts and identically named stops to the requested date and time", async () => {
    const trip = await activeTrip();
    const reply = async (text: string) => (await gateway.sendMessage(trip.id, text, "ko")).messages.at(-1)!.text;
    const daily = await reply("2026-09-16 하루 일정을 요약해 주세요.");
    expect(daily).toContain("2026-09-16\n1. 09:00 · 호텔 조식");
    expect(daily).not.toContain("성수동 쇼핑");
    const bookings = await reply("2026-09-16 예약 표시를 알려 주세요.");
    expect(bookings).toContain("이촌동 점심 식당");
    expect(bookings).not.toContain("성수 예약 식당");
    const stop = await reply("2026-09-16 09:00 호텔 조식 일정의 상세를 알려 주세요.");
    expect(stop).toContain("2026-09-16 09:00 · 호텔 조식");
    expect(stop).toContain("다음 일정: 10:00 · 국립중앙박물관");
    expect(await reply("2026-09-16 20:00 호텔 복귀 다음 일정을 알려 주세요.")).toBe("호텔 복귀는 이날 마지막으로 등록한 일정이에요.");
    expect(await reply("성수 예약 식당 취소해 주세요")).toContain("변경하거나 취소하지 않아요");
  });

  it("answers the English quick prompts from the English itinerary", async () => {
    const trip = await activeTrip(SAMPLE_PLANS.en, "en");
    const reply = async (text: string) => (await gateway.sendMessage(trip.id, text, "en")).messages.at(-1)!.text;
    expect(await reply("Summarize the itinerary for 2026-09-16.")).toContain("2. 10:00 · National Museum of Korea");
    expect(await reply("Tell me about the Lunch in Ichon-dong stop on 2026-09-16 at 12:00.")).toContain("Booking noted");
    expect(await reply("What comes after Lunch in Ichon-dong on 2026-09-16 at 12:00?")).toContain("After Lunch in Ichon-dong: 14:15 · Itaewon gift shops");
    expect(await reply("Show booking notes for 2026-09-15.")).toContain("13:00 · Seongsu restaurant");
    expect(await reply("Please cancel my dinner")).toContain("does not change or cancel");
  });

  it("registers a trip with its survey but refuses a malformed survey without creating a trip, like the server's 422", async () => {
    const survey = toSurvey(toggle(initialAnswers, "pace", "relaxed"));
    await expect(gateway.createTrip({ source: SAMPLE, survey }, "ko")).resolves.toMatchObject({ status: "processing" });
    const saved = storage.items.size;
    await expect(gateway.createTrip({ source: SAMPLE, survey: { ...survey, budget: "mid" } as TripSurvey }, "ko")).rejects.toMatchObject({ code: "INVALID_INPUT" });
    expect(storage.items.size).toBe(saved);
  });
});
