import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LiveError } from "./client";
import { createLiveGateway } from "./gateway";

function memory() {
  const items = new Map<string, string>();
  return { getItem: (key: string) => items.get(key) ?? null, setItem: (key: string, value: string) => { items.set(key, value); }, removeItem: (key: string) => { items.delete(key); } };
}

const TRIP = {
  trip_id: "c287a5e9-7707-408c-9ea9-456cde20cbec", title: "서울 가족여행", version: 1, plan_url: "http://x/plan",
  items: [
    { item_id: "a", seq: 1, kind: "activity", title: "경복궁 관람", place: "경복궁", starts_at: "2026-10-15T00:00:00+00:00", ends_at: "2026-10-15T01:30:00+00:00", changed: false, lat: 37.5796, lon: 126.977, booked: false },
    { item_id: "b", seq: 2, kind: "activity", title: "명동난타극장", place: "명동난타극장", starts_at: "2026-10-16T10:00:00+00:00", ends_at: null, changed: true, lat: null, lon: null, booked: true },
  ],
};

describe("live trip gateway", () => {
  let calls: { url: string; init: RequestInit }[];
  let replies: unknown[];

  beforeEach(() => {
    calls = [];
    replies = [];
    vi.stubGlobal("window", { localStorage: memory(), sessionStorage: memory() });
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/v1/web/session")) return new Response(JSON.stringify({ user_key: "acop_u_test" }), { status: 201 });
      const next = replies.shift();
      return next instanceof Response ? next : new Response(JSON.stringify(next ?? TRIP), { status: 200 });
    });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("maps server items to stops in Seoul time with pins and booking marks", async () => {
    const trip = await createLiveGateway().getTrip(TRIP.trip_id, "ko");
    expect(trip.status).toBe("active");
    expect(trip.stops.map((stop) => [stop.date, stop.time, stop.endTime, stop.booking])).toEqual([
      ["2026-10-15", "09:00", "10:30", "unknown"],
      ["2026-10-16", "19:00", undefined, "booked"],
    ]);
    expect(trip.stops[0].coordinates).toEqual({ lat: 37.5796, lng: 126.977 });
    expect(trip.stops[1].coordinates).toBeNull();                 // ★no coordinates → no pin, never guessed
    expect(trip.stops[1].notes).toContain("바뀐");
    // ★the key is issued once and sent as X-User-Key — never a server scope key
    expect(calls[0].url).toMatch(/\/v1\/web\/session$/);
    expect((calls[1].init.headers as Record<string, string>)["X-User-Key"]).toBe("acop_u_test");
  });

  it("folds move items into the next stop as a departure time instead of listing them as stops", async () => {
    replies.push({ ...TRIP, items: [TRIP.items[0],
      { item_id: "m", seq: 2, kind: "mobility", title: "경복궁 → 명동난타극장", place: null, starts_at: "2026-10-16T09:25:00+00:00", ends_at: "2026-10-16T09:50:00+00:00", changed: false, lat: null, lon: null, booked: false },
      TRIP.items[1]] });
    const trip = await createLiveGateway().getTrip(TRIP.trip_id, "ko");
    expect(trip.stops.map((stop) => stop.title)).toEqual(["경복궁 관람", "명동난타극장"]);
    expect(trip.stops[1].notes.startsWith("18:25 출발")).toBe(true);
  });

  it("shows the server's own answer and falls back to fixed words, never inventing one", async () => {
    replies.push({ status: "no_meal", answer: "그 시각 뒤에는 식사 일정이 없어요." }, TRIP,
      { status: "mystery_status" }, TRIP);
    const gateway = createLiveGateway();
    const first = await gateway.sendMessage(TRIP.trip_id, "식당이 휴무예요", "ko");
    expect(first.messages.map((message) => [message.role, message.text])).toEqual([
      ["user", "식당이 휴무예요"], ["assistant", "그 시각 뒤에는 식사 일정이 없어요."]]);
    const second = await gateway.sendMessage(TRIP.trip_id, "?", "ko");
    expect(second.messages.at(-1)?.text).toContain("mystery_status");
  });

  it("does not quietly become a new user when the saved key is rejected", async () => {
    replies.push(new Response(JSON.stringify({ error: { code: "unauthenticated", message: "no" } }), { status: 401 }));
    const failure = await createLiveGateway().getTrip(TRIP.trip_id, "ko").catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(LiveError);
    expect((failure as LiveError).code).toBe("key_rejected");
    expect(calls.filter((call) => call.url.endsWith("/v1/web/session"))).toHaveLength(1);   // ★no second key issued behind the user's back
  });
});
