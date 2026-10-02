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
  /** The server's conversation record (`GET …/chat`); `null` = that call fails, so the tab's own copy is shown. */
  let chat: unknown[] | null;

  beforeEach(() => {
    calls = [];
    replies = [];
    chat = null;
    vi.stubGlobal("window", { localStorage: memory(), sessionStorage: memory() });
    vi.stubGlobal("fetch", async (url: string, init: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/v1/web/session")) return new Response(JSON.stringify({ user_key: "acop_u_test" }), { status: 201 });
      if (url.includes("/chat?")) return chat === null ? new Response("{}", { status: 404 }) : new Response(JSON.stringify({ turns: chat }), { status: 200 });
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

  it("lists nothing without asking the server when this browser has no user key", async () => {
    expect(await createLiveGateway().listTrips("ko")).toEqual([]);
    expect(calls).toHaveLength(0);                                 // ★no key issued — viewing the list creates no user
  });

  it("lists the server's trips with the stored user key", async () => {
    const gateway = createLiveGateway();
    await gateway.getTrip(TRIP.trip_id, "ko");                     // issues and stores the key
    replies.push({ trips: [{ trip_id: TRIP.trip_id, title: "서울 가족여행", version: 3, created_at: "2026-09-28T03:12:00+00:00" }] });
    expect(await gateway.listTrips("ko")).toEqual([{ id: TRIP.trip_id, title: "서울 가족여행", createdAt: "2026-09-28T03:12:00+00:00", version: 3 }]);
    expect(calls.at(-1)!.url).toMatch(/\/v1\/web\/trips$/);
    expect((calls.at(-1)!.init.headers as Record<string, string>)["X-User-Key"]).toBe("acop_u_test");
  });

  it("offers no trip delete: the server has no delete call, so the list must not pretend one happened", () => {
    expect(createLiveGateway().deleteTrip).toBeUndefined();
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

  it("never fills in its own “passed to a person” sentence: an escalated result without an answer shows its status, one with an answer shows the server's words", async () => {
    replies.push({ status: "escalated", reason: "not_understood" }, TRIP,
      { status: "escalated", reason: "question_needs_policy_answer", answer: "규정에서 그 내용을 찾지 못했어요." }, TRIP);
    const gateway = createLiveGateway();
    const bare = await gateway.sendMessage(TRIP.trip_id, "???", "ko");
    expect(bare.messages.at(-1)?.text).not.toContain("담당자");
    expect(bare.messages.at(-1)?.text).toContain("escalated");
    const answered = await gateway.sendMessage(TRIP.trip_id, "위약금이 있나요?", "ko");
    expect(answered.messages.at(-1)?.text).toBe("규정에서 그 내용을 찾지 못했어요.");
  });

  it("carries what the server did and found: history, warnings, pinned stops and the other options it kept", async () => {
    replies.push({
      ...TRIP,
      items: [{ ...TRIP.items[0], customer_pinned: true, other_options: [{ key: "a", name: "대체 식당" }, { key: 1, name: "깨진 것" }] }, TRIP.items[1]],
      history: [{ version: 2, reason: "closed", at: "2026-10-15T01:30:00+00:00", causes: [{ category: "place", summary: "식당이 문을 닫았어요." }, { kind: "closed" }] }],
      warnings: [{ code: "density_exceeded", date: "2026-10-15", reason: "하루가 빡빡해요", remedy: "일정을 줄이세요" }, { code: "no_reason" }],
    });
    const trip = await createLiveGateway().getTrip(TRIP.trip_id, "ko");
    expect(trip.planUrl).toBe("http://x/plan");
    expect(trip.stops[0]).toMatchObject({ pinned: true, otherOptions: [{ key: "a", name: "대체 식당" }] });
    expect(trip.stops[1]).toMatchObject({ pinned: false, otherOptions: [] });
    // Seoul wall clock, and a cause without a sentence still says what kind of thing it was
    expect(trip.history).toEqual([{ version: 2, reason: "closed", at: "2026-10-15 10:30", causes: ["식당이 문을 닫았어요.", "closed"] }]);
    // ★a warning without the server's reason is dropped — it is not replaced by a made-up one
    expect(trip.warnings).toEqual([{ code: "density_exceeded", date: "2026-10-15", reason: "하루가 빡빡해요", remedy: "일정을 줄이세요" }]);
  });

  it("carries the place facts the server sent (dining ledger) and leaves out what it did not", async () => {
    replies.push({
      ...TRIP,
      items: [
        { ...TRIP.items[0], place_info: { address: "서울특별시 종로구 율곡로1길 7", phone: "02-000-0000", category: "한식", hours: [{ day: "월", open: "11:30", close: "21:00", last_order: "20:30" }, { day: "화" }],
          tags: ["michelin_selected", "card_payment", 3], michelin: { level: "셀렉티드", year: 2026 }, source_note: "" } },
        { ...TRIP.items[1], place_info: { address: "", hours: null, tags: [] } },
      ],
    });
    const trip = await createLiveGateway().getTrip(TRIP.trip_id, "ko");
    expect(trip.stops[0].placeInfo).toEqual({ address: "서울특별시 종로구 율곡로1길 7", phone: "02-000-0000", category: "한식", hours: ["월 11:30–21:00 (주문 마감 20:30)", "화"],
      hoursNotes: [], tags: ["michelin_selected", "card_payment"], michelin: { level: "셀렉티드", year: 2026 }, sourceNote: undefined });
    // ★nothing real was sent — no block at all, not a row of "unknown"
    expect(trip.stops[1].placeInfo).toBeNull();
  });

  it("shows closed days, last entry, and the source's hours text for places outside the dining ledger", async () => {
    replies.push({ ...TRIP, items: [
      { ...TRIP.items[0], place_info: { address: "서울특별시 종로구 사직로 161 (세종로)", hours: [{ day: "월", closed: true, open: "09:00", close: "18:00" }, { day: "화", open: "09:00", close: "18:00", last_entry: "17:00", closed: false }],
        hours_text: ["09:00~18:00", "매주 화요일 휴무"], hours_conditions: ["공휴일은 개방"], tags: [], source_note: "ⓒ한국관광공사" } },
      { ...TRIP.items[1], place_info: { hours: null, hours_text: ["09:00~18:00", "매주 화요일 휴무"], hours_conditions: ["매주 화요일 휴무"], tags: [] } },
    ] });
    const trip = await createLiveGateway().getTrip(TRIP.trip_id, "ko");
    expect(trip.stops[0].placeInfo).toMatchObject({ hours: ["월 휴무", "화 09:00–18:00 (입장 마감 17:00)"], hoursNotes: ["공휴일은 개방"], sourceNote: "ⓒ한국관광공사" });
    // no weekly table: the source text is the hours (a repeated line is shown once)
    expect(trip.stops[1].placeInfo).toMatchObject({ hours: [], hoursNotes: ["09:00~18:00", "매주 화요일 휴무"] });
  });

  it("keeps only Google Maps links for the map app: each stop and each day's route", async () => {
    replies.push({ ...TRIP,
      items: [{ ...TRIP.items[0], map_url: "https://www.google.com/maps/search/?api=1&query=%EA%B2%BD%EB%B3%B5%EA%B6%81" },
        { ...TRIP.items[1], map_url: "javascript:alert(1)" }],
      map: { days: [{ date: "2026-10-15", app_route_urls: ["https://www.google.com/maps/dir/?api=1&origin=a&destination=b", "https://evil.example/x"] },
        { date: "2026-10-16", app_route_urls: [] }] } });
    const trip = await createLiveGateway().getTrip(TRIP.trip_id, "ko");
    expect(trip.stops[0].mapUrl).toBe("https://www.google.com/maps/search/?api=1&query=%EA%B2%BD%EB%B3%B5%EA%B6%81");
    expect(trip.stops[1].mapUrl).toBeUndefined();                       // ★not a map link — no button at all
    expect(trip.dayRoutes).toEqual({ "2026-10-15": ["https://www.google.com/maps/dir/?api=1&origin=a&destination=b"] });
    expect(trip.legs).toEqual({});

    replies.push({ ...TRIP, map: { days: [{ date: "2026-10-15", legs: [
      { from_item_id: "a", to_item_id: "b", url: "https://www.google.com/maps/dir/?api=1&origin=a&destination=b&travelmode=transit" },
      { from_item_id: "b", to_item_id: "c", url: "http://www.google.com/maps/dir/" },            // not https — dropped
      { from_item_id: "c", url: "https://www.google.com/maps/dir/?api=1&origin=c&destination=d" },  // no destination stop — dropped
    ] }] } });
    const withLegs = await createLiveGateway().getTrip(TRIP.trip_id, "ko");
    expect(withLegs.legs).toEqual({ "a>b": "https://www.google.com/maps/dir/?api=1&origin=a&destination=b&travelmode=transit" });
  });

  it("keeps the rule sections behind an answer only when the server sends them (development mode)", async () => {
    const gateway = createLiveGateway();
    replies.push({ status: "answered", answer: "비 오면 취소돼요.", basis: { writer: "rules" }, basis_sources: ["t_doc_07#c5", { source: "t_doc_06#c2" }, 3] }, TRIP,
      { status: "answered", answer: "네." }, TRIP);
    const dev = await gateway.sendMessage(TRIP.trip_id, "비 오면?", "ko");
    expect(dev.messages.at(-1)).toMatchObject({ text: "비 오면 취소돼요.", basis: ["t_doc_07#c5", "t_doc_06#c2"] });
    const customer = await gateway.sendMessage(TRIP.trip_id, "또?", "ko");
    expect(customer.messages.at(-1)).not.toHaveProperty("basis");        // ★no field — nothing is shown to the customer
  });

  it("sends the stop the customer picked as item_id, and nothing when none was picked", async () => {
    const gateway = createLiveGateway();
    replies.push({ status: "adjusted", answer: "바꿨어요." }, TRIP, { status: "answered", answer: "네." }, TRIP);
    await gateway.sendMessage(TRIP.trip_id, "다른 데로 바꿔 줘", "ko", "b");
    await gateway.sendMessage(TRIP.trip_id, "하루 요약", "ko");
    const bodies = calls.filter((call) => call.url.endsWith("/messages")).map((call) => JSON.parse(String(call.init.body)));
    expect(bodies[0]).toMatchObject({ message: "다른 데로 바꿔 줘", item_id: "b" });
    expect(bodies[1]).not.toHaveProperty("item_id");
  });

  it("does not quietly become a new user when the saved key is rejected", async () => {
    replies.push(new Response(JSON.stringify({ error: { code: "unauthenticated", message: "no" } }), { status: 401 }));
    const failure = await createLiveGateway().getTrip(TRIP.trip_id, "ko").catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(LiveError);
    expect((failure as LiveError).code).toBe("key_rejected");
    expect(calls.filter((call) => call.url.endsWith("/v1/web/session"))).toHaveLength(1);   // ★no second key issued behind the user's back
  });

  it("keeps the folded rest of an answer and the 「혹시 이런 뜻이었나요?」 readings the server offers with it", async () => {
    const more = ["· 운영시간 원문: 10:00~18:30", "· 쉬는 날: 월요일"].join("\n");
    replies.push({ status: "answered", answer: "세종이야기 — 서울특별시 종로구 세종대로 지하175", more,
      choices_title: "혹시 이런 뜻이었나요?", choices: [{ label: "세종이야기 운영시간", message: "세종이야기 몇 시까지 해?" }] }, TRIP);
    const trip = await createLiveGateway().sendMessage(TRIP.trip_id, "그건 어딧는거야", "ko");
    expect(trip.messages.at(-1)).toMatchObject({ more, choicesTitle: "혹시 이런 뜻이었나요?",
      choices: [{ label: "세종이야기 운영시간", message: "세종이야기 몇 시까지 해?" }] });
  });

  it("shows the conversation from the server's record, keeping this tab's choices on the latest answer", async () => {
    const gateway = createLiveGateway();
    const question = ["다음 중 하나인가요?", "1) 1일차 저녁 식당 바꾸기", "2) 1일차 저녁 식당 알아보기"].join("\n");
    replies.push({ status: "clarify", answer: question,
      choices: [{ label: "1일차 저녁 식당 바꾸기", message: "1일차 저녁 식당 바꿔 줘" }, { label: "빈 것" }] }, TRIP);
    const asked = await gateway.sendMessage(TRIP.trip_id, "저녁", "ko");
    expect(asked.messages.at(-1)?.choices).toEqual([{ label: "1일차 저녁 식당 바꾸기", message: "1일차 저녁 식당 바꿔 줘" }]);
    // another device: the server's record is the conversation; this tab adds the choices to the same answer
    // (the record's times are after this tab's messages: the record has caught up with everything this tab saw)
    chat = [{ role: "customer", text: "저녁", case_id: "c1", at: "2999-01-01T00:00:00+09:00" },
      { role: "assistant", text: question, case_id: "c1", at: "2999-01-01T00:00:01+09:00" }];
    const trip = await gateway.getTrip(TRIP.trip_id, "ko");
    expect(trip.messages.map((message) => [message.role, message.text.split("\n")[0]])).toEqual([["user", "저녁"], ["assistant", "다음 중 하나인가요?"]]);
    expect(trip.messages[1].choices?.[0].message).toBe("1일차 저녁 식당 바꿔 줘");
    // the record lags: what this tab just said and heard (after the record's last turn) stays at the end, once
    chat = [{ role: "customer", text: "저녁", case_id: "c1", at: "2020-01-01T10:00:00+09:00" }];
    const lagging = await gateway.getTrip(TRIP.trip_id, "ko");
    expect(lagging.messages.map((message) => message.role)).toEqual(["user", "user", "assistant"]);
    expect(lagging.messages.at(-1)?.text).toBe(question);
    chat = [{ role: "customer", text: "저녁", case_id: "c1", at: "2026-09-29T10:00:00+09:00" },
      { role: "assistant", text: question, case_id: "c1", at: "2999-01-01T00:00:00+09:00" }];
    // a fresh browser: the record alone, no choices to invent
    window.sessionStorage.removeItem(`tripilot.web.live.messages:${TRIP.trip_id}`);
    expect((await gateway.getTrip(TRIP.trip_id, "ko")).messages[1]).not.toHaveProperty("choices");
  });

  // 2026-09-30 (teammate question Q-05): sending and re-reading are two steps.
  it("keeps the server's reply when only the re-read after it fails — it is not reported as 'not sent'", async () => {
    const gateway = createLiveGateway();
    replies.push({ status: "answered", answer: "경복궁은 사직로 161에 있어요." }, new Response("{}", { status: 503 }));
    const failure = await gateway.sendMessage(TRIP.trip_id, "경복궁 어디야", "ko").catch((error: unknown) => error);
    expect(failure).toBeInstanceOf(LiveError);
    expect((failure as LiveError).code).toBe("reply_kept");
    const sent = ((failure as LiveError).detail as { sent: { role: string; text: string }[] }).sent;
    expect(sent.map((message) => [message.role, message.text])).toEqual([["user", "경복궁 어디야"], ["assistant", "경복궁은 사직로 161에 있어요."]]);
    // the next successful read still shows it (this tab's copy, until the server's record has it)
    expect((await gateway.getTrip(TRIP.trip_id, "ko")).messages.map((message) => message.text)).toContain("경복궁은 사직로 161에 있어요.");
  });

  it("sends a failed message again with the same request id, so the server does not act on it twice", async () => {
    const gateway = createLiveGateway();
    const ids = () => calls.filter((call) => call.url.endsWith("/messages")).map((call) => JSON.parse(String(call.init.body)).request_id as string);
    replies.push(new Response("{}", { status: 502 }));
    await expect(gateway.sendMessage(TRIP.trip_id, "점심 바꿔 줘", "ko", "b")).rejects.toBeInstanceOf(LiveError);
    replies.push({ status: "adjusted", answer: "바꿨어요." });
    await gateway.sendMessage(TRIP.trip_id, "점심 바꿔 줘", "ko", "b");
    expect(ids()[1]).toBe(ids()[0]);
    // answered: the same words later are a new request
    replies.push({ status: "answered", answer: "네." });
    await gateway.sendMessage(TRIP.trip_id, "점심 바꿔 줘", "ko", "b");
    expect(ids()[2]).not.toBe(ids()[0]);
  });

  it("does not reuse a failed message's request id for different words or a different stop", async () => {
    const gateway = createLiveGateway();
    const ids = () => calls.filter((call) => call.url.endsWith("/messages")).map((call) => JSON.parse(String(call.init.body)).request_id as string);
    replies.push(new Response("{}", { status: 502 }));
    await expect(gateway.sendMessage(TRIP.trip_id, "저녁 바꿔 줘", "ko", "a")).rejects.toBeInstanceOf(LiveError);
    replies.push({ status: "answered", answer: "네." });
    await gateway.sendMessage(TRIP.trip_id, "저녁 바꿔 줘", "ko", "b");
    expect(ids()[1]).not.toBe(ids()[0]);
  });

  // 2026-09-30: the customer's position from the browser, sent only after the server asked for it.
  it("marks an answer that needs the customer's position, and sends the position only when given", async () => {
    const gateway = createLiveGateway();
    const bodies = () => calls.filter((call) => call.url.endsWith("/messages")).map((call) => JSON.parse(String(call.init.body)) as Record<string, unknown>);
    replies.push({ status: "answered", answer: "현재 위치를 알려 주시면 길을 찾아 드릴게요.", needs_location: true });
    const asked = await gateway.sendMessage(TRIP.trip_id, "여기서 경복궁 어떻게 가?", "ko");
    expect(asked.messages.at(-1)).toMatchObject({ role: "assistant", needsLocation: true });
    expect(bodies()[0]).not.toHaveProperty("location");

    replies.push({ status: "answered", answer: "지금 계신 곳에서 도보 12분이에요.", needs_location: true });
    const answered = await gateway.sendMessage(TRIP.trip_id, "여기서 경복궁 어떻게 가?", "ko", null, { lat: 37.57, lng: 126.98, accuracyM: 20, at: "2026-09-30T06:00:00.000Z" });
    expect(bodies()[1].location).toEqual({ lat: 37.57, lng: 126.98, accuracy_m: 20, at: "2026-09-30T06:00:00.000Z" });
    expect(bodies()[1].request_id).not.toBe(bodies()[0].request_id);
    // ★a position was sent: no second offer to send it again
    expect(answered.messages.at(-1)).not.toHaveProperty("needsLocation");
  });
});
