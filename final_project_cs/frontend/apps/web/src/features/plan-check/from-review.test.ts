import { describe, expect, it } from "vitest";
import type { IntakeView } from "@/lib/live/intake";
import { emptyStream, reduceStream, toIntakeEvent, type StreamState } from "@/lib/live/intake-events";
import type { Candidate, ReviewItem, ReviewMove, ReviewedIntakeView } from "@/lib/live/intake-review";
import { readingOf } from "./from-intake";
import { draftOfItem } from "./model";
import { asksOf, planCandidate, reviewResultOf, safePhotoUrl, streamingViewOf } from "./from-review";

const place = (name: string, latitude: number | null = 37.57, longitude: number | null = 126.98) =>
  ({ name, latitude, longitude, source: "kakao", kind: null });
const item = (patch: Partial<ReviewItem>): ReviewItem => ({
  id: "0-0", source_id: "s1", index: 0, title: "경복궁 관람", kind: null, day: 1, date: "2026-10-01", starts_at: "09:00", ends_at: "11:00",
  locked: false, status: "keep", can_lock: true, place_state: "found", place: place("경복궁"), candidates_hint: null,
  rows: [{ row: "place", result: "ok", text: "경복궁" }, { row: "hours", result: "ok", text: "09:00–17:00 안에 머물러요" }], ...patch,
});
const move = (patch: Partial<ReviewMove> = {}): ReviewMove => ({
  from: "0-0", to: "0-1", day: 1, date: "2026-10-01", status: "keep", mode: "subway", mode_label: "지하철", minutes: 12, km: 3.1,
  depart: "11:05", arrive: "11:17", slack_min: 8, basis: "timetable", summary: "12분 · 3.1km",
  rows: [{ row: "route", result: "ok", text: "경복궁 → 광장시장" }, { row: "arrival", result: "ok", text: "8분 여유" }], ...patch,
});

function intake(status: IntakeView["status"], stage: string, extra: Partial<ReviewedIntakeView> = {}): ReviewedIntakeView {
  return {
    intake_id: "i1", status, stage, stage_label: "", revision: 3, fatal: null, trip_id: null, needs_review: [], check: null,
    sources: [{ source_id: "s1", kind: "text", filename: null, transcribed: false, items: [], trip: {}, reading: null,
      lines: [{ no: 1, text: "10/1 09:00 경복궁 관람", read: true }, { no: 2, text: "점심은 광장시장", read: false }] }],
    ...extra,
  } as ReviewedIntakeView;
}

describe("the finished check, from the server's review", () => {
  it("preserves only an explicit server acknowledgement permission on the hours row", () => {
    for (const permission of [true, false, undefined]) {
      const next = intake("review", "review", { review: { revision: 3, built_at: "", engine: "estimate", ready: true,
        needs: { items: 1, moves: 0, total: 1 }, items: [item({ status: "review", rows: [
          { row: "hours", result: "warn", text: "마지막 주문 확인", can_acknowledge: permission },
        ] })], moves: [] } });
      const row = reviewResultOf(next, readingOf(next))!.items[0].checks[0];
      expect(row.canAcknowledge === true).toBe(permission === true);
      expect(row).toMatchObject({ result: "warn", text: "마지막 주문 확인" });
    }
  });
  it("connects breakfast cards to the shared stay without inventing check-in or nights", () => {
    const common = { id: "0-0", members: ["0-0", "0-2"], place: place("공통 숙소") };
    const next = intake("review", "review", { review: { revision: 3, built_at: "", engine: "estimate", ready: true,
      needs: { items: 0, moves: 0, total: 0 }, items: [
        item({ title: "호텔", kind: "dining", lodging_group: common }),
        item({ id: "0-2", date: "2026-10-02", day: 2, title: "호텔", kind: "dining", lodging_group: common }),
      ], moves: [] } });
    const result = reviewResultOf(next, readingOf(next))!;
    expect(result.items.map((row) => row.lodgingGroup)).toEqual([
      { ...common, place: "공통 숙소" }, { ...common, place: "공통 숙소" },
    ]);
    expect(result.items.every((row) => row.kind === "dining" && !row.endDate)).toBe(true);
  });
  it.each([
    { parts: { content_type: "32", lodging_meal: true }, place: null },
    { parts: null, place: { ...place("효자스테이"), kind: "dining", category: "숙소 안 식사" } },
    { parts: null, place: { ...place("호텔"), content_type_id: "32" } },
  ])("keeps breakfast as dining while displaying its lodging icon", (patch) => {
    const next = intake("review", "review", { review: { revision: 3, built_at: "", engine: "estimate", ready: false,
      needs: { items: 1, moves: 0, total: 1 }, items: [item({ ...patch, title: "호텔", kind: "dining" })], moves: [] } });
    expect(reviewResultOf(next, readingOf(next))!.items[0]).toMatchObject({ kind: "dining", displayKind: "lodging" });
  });
  it("retains the dining icon for an ordinary restaurant", () => {
    const next = intake("review", "review", { review: { revision: 3, built_at: "", engine: "estimate", ready: true,
      needs: { items: 0, moves: 0, total: 0 }, items: [item({ kind: "dining", place: place("시장 식당") })], moves: [] } });
    expect(reviewResultOf(next, readingOf(next))!.items[0].displayKind).toBeUndefined();
  });
  const review = {
    revision: 3, built_at: "", engine: "timetable" as const, ready: false, needs: { items: 1, moves: 0, total: 1 },
    items: [item({}), item({ id: "0-1", index: 1, title: "광장시장", starts_at: "12:00", ends_at: "13:00", status: "review", locked: true, place: place("광장시장"),
      rows: [{ row: "closed", result: "bad", text: "수요일은 쉬어요" }] })],
    moves: [move()],
  };
  it("preserves the saved service and actual revision used to invalidate old move candidates", () => {
    const next = intake("review", "review", { revision: 4, review: { ...review, revision: 4, taxi_pricing: { product: "capsi_immediate", quotes: [] } } });
    const mapped = reviewResultOf(next, readingOf(next))!;
    expect(mapped.revision).toBe(4);
    expect(mapped.taxiPricing).toEqual({ product: "capsi_immediate", quotes: [] });
    const older = intake("review", "review", { review });
    expect(reviewResultOf(older, readingOf(older))!.taxiPricing).toBeNull();
  });
  const view = reviewResultOf(intake("review", "review", { review, check: { ready: true, problems: [], filled: [], items: 2, title: "10월 서울 여행", plan: { requested: false, start_date: null, days: null, party_size: null, preferences: "" } } }), readingOf(intake("review", "review")))!;

  it("is done, titled by the server, with a day for every stop", () => {
    expect(view.stage).toBe("done");
    expect(view.title).toBe("10월 서울 여행");
    expect(view.days).toEqual([{ day: 1, date: "2026-10-01" }]);
  });

  it("keeps the server's check lines and verdict as they are — a bad line stays bad", () => {
    expect(view.items[0]).toMatchObject({ id: "0-0", verdict: "keep", locked: false, startsAt: "09:00", endsAt: "11:00", place: "경복궁", coordinates: { lat: 37.57, lng: 126.98 } });
    expect(view.items[0].checks).toEqual([{ kind: "place", result: "ok", text: "경복궁" }, { kind: "hours", result: "ok", text: "09:00–17:00 안에 머물러요" }]);
    expect(view.items[1]).toMatchObject({ verdict: "review", locked: true });
    expect(view.items[1].checks).toEqual([{ kind: "closed", result: "bad", text: "수요일은 쉬어요" }]);
  });

  it("turns a leg into the way from one stop to the next, with its own check lines", () => {
    expect(view.moves).toEqual([{
      id: "0-0:0-1", fromId: "0-0", toId: "0-1", day: 1, departAt: "11:05", mode: "지하철", summary: "12분 · 3.1km", verdict: "keep",
      minutes: 12, arriveAt: "11:17", slackMin: 8, estimated: false, modeKey: "subway", recommendedMode: null, modeChoice: null,
      checks: [{ kind: "route", result: "ok", text: "경복궁 → 광장시장" }, { kind: "arrival", result: "ok", text: "8분 여유" }],
    }]);
  });

  it("carries the way the check uses, the way the calculator chose and what became of the customer's choice (`mode_choice`)", () => {
    const legs = reviewResultOf(intake("review", "review", { review: { ...review, moves: [
      move({ mode: "taxi", recommended_mode: "subway", mode_choice: { mode: "taxi", state: "dropped", why: "앞 일정이 늦어져 택시로도 닿지 않아요" } }),
    ] } }), readingOf(intake("review", "review")))!;
    expect(legs.moves[0]).toMatchObject({ modeKey: "taxi", recommendedMode: "subway", modeChoice: { mode: "taxi", state: "dropped", why: "앞 일정이 늦어져 택시로도 닿지 않아요" } });
  });

  it("carries a leg's minutes, arrival and slack; a straight-line guess (basis estimate) is marked estimated", () => {
    const legs = reviewResultOf(intake("review", "review", { review: { ...review, moves: [
      move({ basis: "estimate", minutes: 25, depart: "11:00", arrive: "11:25", slack_min: -5 }),
      move({ from: "0-1", to: "0-2", basis: "timetable" }),
    ] } }), readingOf(intake("review", "review")))!;
    expect(legs.moves[0]).toMatchObject({ minutes: 25, departAt: "11:00", arriveAt: "11:25", slackMin: -5, estimated: true });
    expect(legs.moves[1]).toMatchObject({ estimated: false });
  });

  it("leaves what the server did not say empty: no arrival is 「」, no minutes or slack is null, no basis is not an estimate", () => {
    const legs = reviewResultOf(intake("review", "review", { review: { ...review, moves: [move({ minutes: null, depart: null, arrive: null, slack_min: null, basis: null })] } }), readingOf(intake("review", "review")))!;
    expect(legs.moves[0]).toMatchObject({ departAt: "", arriveAt: "", minutes: null, slackMin: null, estimated: false });
  });

  it("carries the booked flag of a stop: true, false, or null when the plan (or an older server) says nothing", () => {
    const booked = reviewResultOf(intake("review", "review", { review: { ...review, moves: [], items: [
      item({ id: "0-0", booked: true }), item({ id: "0-1", index: 1, booked: false }), item({ id: "0-2", index: 2, booked: null }), item({ id: "0-3", index: 3 }),
    ] } }), readingOf(intake("review", "review")))!;
    expect(booked.items.map((entry) => entry.booked)).toEqual([true, false, null, null]);
  });

  it("gives a stop with no coordinates no pin and a stop with no place the 「장소 없음」 flag", () => {
    const none = reviewResultOf(intake("review", "review", { review: { ...review, items: [item({ place: null, place_state: "none" }), item({ id: "0-1", index: 1, place: place("어딘가", null, null) })], moves: [] } }), readingOf(intake("review", "review")))!;
    expect(none.items[0]).toMatchObject({ place: "", noPlace: true, coordinates: null });
    expect(none.items[1]).toMatchObject({ place: "어딘가", noPlace: false, coordinates: null });
  });

  it("names a card after the place the customer picked, and keeps the written words for the editor (2026-10-03: the name did not follow the change)", () => {
    const picked = reviewResultOf(intake("review", "review", { review: { ...review, moves: [], items: [
      item({ id: "0-3", index: 3, title: "성수 예약 식당", place_state: "customer", place: place("평양면옥") }),
      item({ id: "0-4", index: 4, title: "경복궁 관람", place_state: "found", place: place("경복궁") }),
      item({ id: "0-5", index: 5, title: "광장시장", place_state: "customer", place: place("광장시장") }),
    ] } }), readingOf(intake("review", "review")))!;
    expect(picked.items[0]).toMatchObject({ title: "평양면옥", written: "성수 예약 식당", place: "평양면옥" });
    expect(draftOfItem(picked.items[0]).title).toBe("성수 예약 식당");                // editing the words edits what was written, not the place
    expect(picked.items[1]).toMatchObject({ title: "경복궁 관람", place: "경복궁" });  // a place the server found keeps the written words as the name
    expect(picked.items[1].written).toBeUndefined();
    expect(picked.items[2].written).toBeUndefined();                                   // same name: nothing to say twice
  });

  it("settles a leg that waits (an end has no place) instead of leaving it spinning", () => {
    const waiting = reviewResultOf(intake("review", "review", { review: { ...review, moves: [move({ status: "waiting", rows: [] })] } }), readingOf(intake("review", "review")))!;
    expect(waiting.moves[0].verdict).toBe("keep");
    expect(waiting.moves[0].checks).toEqual([]);
  });

  it("is null when the server could not build the check — never an empty 「all fine」", () => {
    expect(reviewResultOf(intake("review", "review", { review: null, review_error: "review_failed" }), readingOf(intake("review", "review")))).toBeNull();
  });
});

describe("the check while the server is still working, from the events", () => {
  const fold = (events: [string, unknown][]): StreamState => events.reduce((state, [name, body]) => {
    const event = toIntakeEvent(name, JSON.stringify(body));
    return event ? reduceStream(state, event) : state;
  }, emptyStream());

  it("marks a line read and shows what was found on it before the GET has caught up", () => {
    const stream = fold([["line", { source_id: "s1", no: 2, text: "점심은 광장시장", found: { id: "0-1", index: 1, day: 1, date: "2026-10-01", starts_at: "12:00", title: "광장시장" } }]]);
    const view = streamingViewOf(intake("reading", "reading"), stream);
    expect(view.stage).toBe("reading");
    expect(view.lines.map((line) => [line.no, line.read, line.found?.kind === "item" ? line.found.title : null])).toEqual([[1, true, null], [2, true, "광장시장"]]);
  });

  it("moves to the check as soon as a stop has come, with only the lines that have come", () => {
    const stream = fold([
      ["item", { id: "0-0", source_id: "s1", index: 0, title: "경복궁 관람", day: 1, date: "2026-10-01", starts_at: "09:00", place: { name: "경복궁", latitude: 37.58, longitude: 126.98 } }],
      ["check", { item: "0-0", row: "place", result: "ok", text: "경복궁" }],
    ]);
    const view = streamingViewOf(intake("reading", "reading"), stream);
    expect(view.stage).toBe("checking");
    expect(view.items).toHaveLength(1);
    expect(view.items[0].checks).toEqual([{ kind: "place", result: "ok", text: "경복궁" }]);
    expect(view.items[0].verdict).toBeNull();                       // its status has not come: it is still being checked
  });

  it("keeps a read stop's identity and missing date before any checked item arrives", () => {
    const stream = fold([["line", { source_id: "s1", no: 2, text: "점심은 광장시장", found: { id: "0-1", index: 1, day: null, date: null, starts_at: null, title: "광장시장" } }]]);
    const view = streamingViewOf(intake("reading", "checking"), stream);
    expect(view.lines[1]).toEqual({ no: 2, text: "점심은 광장시장", read: true, found: { kind: "item", id: "0-1", sourceKey: "s1:1", day: null, date: null, startsAt: null, title: "광장시장" } });
    expect(view.items).toEqual([]);
  });

  it("stays on 「received」 until the server says it has started reading", () => {
    expect(streamingViewOf(intake("reading", "received"), emptyStream()).stage).toBe("received");
  });
});

describe("candidates and photos", () => {
  const candidate: Candidate = {
    rank: 1, place: { ...place("올리브영 광화문점"), address: "서울 종로구", category: "쇼핑", ref: "tour:123" }, distance_m: 640, reference: "경복궁",
    rows: [{ row: "hours", result: "ok", text: "열려 있어요" }], fits: true, status: "ok", slack: { before: 5, after: 5 }, estimated: false,
  };

  it("turns a candidate into a card: rank, distance from the nearby stop, checks", () => {
    const card = planCandidate(candidate, "0-1", "candidate", { category: "쇼핑", address: "서울 종로구", photos: [] });
    expect(card).toMatchObject({ name: "올리브영 광화문점", source: "candidate", rank: 1, distance: { km: 0.64, from: "경복궁" }, coordinates: { lat: 37.57, lng: 126.98 } });
    expect(card.checks).toEqual([{ kind: "hours", result: "ok", text: "열려 있어요" }]);
  });

  it("gives a search result no rank", () => {
    expect(planCandidate(candidate, "0-1", "search", null).rank).toBeNull();
  });

  it("asks for a photo only over http or https", () => {
    expect(safePhotoUrl("https://example.org/a.jpg")).toBe("https://example.org/a.jpg");
    expect(safePhotoUrl("javascript:alert(1)")).toBeNull();
    expect(safePhotoUrl("data:text/html,x")).toBeNull();
    expect(safePhotoUrl(null)).toBeNull();
  });
});

describe("D-025 「먼저 채움」 — the server filled in first", () => {
  const filledIntake = (extra: Partial<ReviewedIntakeView>) => intake("review", "review", {
    review: { items: [item({ id: "0-0" }), item({ id: "0-1", title: "숙소 근처", status: "adjusted" })], moves: [] } as unknown as ReviewedIntakeView["review"],
    ...extra,
  });

  it("puts one ✎ line with the reason first on the stop the server filled, and nowhere else", () => {
    const next = filledIntake({ prefill: { filled: [{ item: "0-1", title: "근처 식당", owner: "dining_team", owner_label: "식당 팀",
      reason: "계획서의 「저녁은 숙소 근처에서」 — 근처 식당으로 채웠어요", gap: "meal_place", new: false }], questions: [], kept: [] } });
    const view = reviewResultOf(next, readingOf(next))!;
    const [plain, filled] = view.items;
    expect(plain.checks.some((check) => check.text.startsWith("먼저 채움"))).toBe(false);
    expect(filled.checks[0]).toEqual({ kind: "place", result: "filled", text: "먼저 채움 · 계획서의 「저녁은 숙소 근처에서」 — 근처 식당으로 채웠어요" });
    expect(view.prefill).toEqual({ filledCount: 1, questions: [], understood: [], handoff: [] });
  });

  it("shows questions only the traveller knows and the words read as a move, a condition or a preference", () => {
    const next = filledIntake({ prefill: { filled: [], kept: [], questions: [{ kind: "lodging_name", question: "묵는 숙소 이름을 알려 주세요", quote: null },
      { kind: "lodging_name", question: "묵는 숙소 이름을 알려 주세요", quote: null }] } });
    next.sources[0].understanding = { moves: [{ mode: "taxi", scope: "segment", from: "경복궁", to: "광장시장", quote: "택시로 이동할 거야" }],
      conditions: [{ code: "if_rain_indoor", quote: "비 오면 실내" }], preferences: [{ code: "kid_friendly", quote: "애들 데리고" }] };
    expect(reviewResultOf(next, readingOf(next))!.prefill).toEqual({ filledCount: 0, questions: ["묵는 숙소 이름을 알려 주세요"],
      understood: ["택시로 이동할 거야", "비 오면 실내", "애들 데리고"], handoff: [] });
  });

  it("lists what is handed to an owner — ours as 「우리가 채움」, the traveller's own answer kept (D-025 후속)", () => {
    const next = filledIntake({});
    next.check = { ready: true, problems: [], filled: [], items: 2, title: "t", plan: next.check?.plan as never, handoff: [
      { key: "survey.pace", label: "일정 여유", owner: "일정 짜기", value: "relaxed", text: "여유 있게", codes: ["slow_pace"], quotes: ["천천히"], status: "filled" },
      { key: "survey.priority_details.mobility", label: "이동 수단", owner: "이동 판정 · 일정 짜기", value: ["taxi"], text: "택시", codes: ["prefer_taxi"],
        quotes: ["택시로"], status: "customer" },
      { key: "x", label: "빈 값", owner: "누구", value: null, text: "", codes: [], quotes: [], status: "filled" }] };
    expect(reviewResultOf(next, readingOf(next))!.prefill?.handoff).toEqual([
      { label: "일정 여유", text: "여유 있게", owner: "일정 짜기", mine: true },
      { label: "이동 수단", text: "택시", owner: "이동 판정 · 일정 짜기", mine: false }]);
  });

  it("says nothing when an older server sends no prefill", () => {
    const next = filledIntake({});
    expect(reviewResultOf(next, readingOf(next))!.prefill).toBeNull();
  });
});

describe("[2026-10-19] 못 찾은 장소 — the question rides on the stop's card", () => {
  const unresolved = item({ id: "0-1", title: "을지로 그 집", status: "review", place_state: "unresolved", place: null });
  const question = (patch: Record<string, unknown> = {}) => ({ kind: "place_not_found", question: "「을지로 그 집」을 지도에서 찾지 못했어요 — 후보에서 고르거나 직접 골라 주세요",
    quote: "을지로 그 집", item: "0-1", source_id: "s1", index: 1, mode: "change", actions: ["pick_candidate", "pick_myself", "no_place"], blocked: false, ...patch });
  const withQuestions = (questions: Record<string, unknown>[], items = [item({ id: "0-0" }), unresolved]) => intake("review", "review", {
    review: { items, moves: [] } as unknown as ReviewedIntakeView["review"],
    prefill: { filled: [], kept: [], questions: questions as never },
  });

  it("puts the server's sentence on the stop it names, and keeps it out of the note above the list", () => {
    const next = withQuestions([question(), { kind: "lodging_name", question: "묵는 숙소 이름을 알려 주세요", quote: null }]);
    const view = reviewResultOf(next, readingOf(next))!;
    expect(view.items.find((entry) => entry.id === "0-1")!.unfound).toEqual({ question: question().question, blocked: false });
    expect(view.items.find((entry) => entry.id === "0-0")!.unfound).toBeUndefined();
    expect(view.prefill?.questions).toEqual(["묵는 숙소 이름을 알려 주세요"]);
  });

  it("says when the lookup was blocked and searched once more", () => {
    const next = withQuestions([question({ blocked: true, question: "조회가 막혀 다시 찾아봤지만 「을지로 그 집」을 찾지 못했어요" })]);
    expect(reviewResultOf(next, readingOf(next))!.items[1].unfound).toEqual({ question: "조회가 막혀 다시 찾아봤지만 「을지로 그 집」을 찾지 못했어요", blocked: true });
  });

  it("asks no more once the stop has a place or 「장소 없음」, and leaves a question naming no stop of the check in the note", () => {
    const placed = withQuestions([question()], [item({ id: "0-0" }), item({ id: "0-1", title: "을지로 그 집" })]);
    expect(reviewResultOf(placed, readingOf(placed))!.items[1].unfound).toBeUndefined();
    expect(reviewResultOf(placed, readingOf(placed))!.prefill).toBeNull();
    const none = withQuestions([question()], [item({ id: "0-0" }), item({ id: "0-1", place_state: "none", place: null })]);
    expect(reviewResultOf(none, readingOf(none))!.items[1].unfound).toBeUndefined();
    const elsewhere = withQuestions([question({ item: "0-9" })]);
    expect(reviewResultOf(elsewhere, readingOf(elsewhere))!.items.some((entry) => entry.unfound)).toBe(false);
    expect(reviewResultOf(elsewhere, readingOf(elsewhere))!.prefill?.questions).toEqual([question().question]);
  });

  // `[2026-10-26 사용자 지시 — 호텔 후보는 고객이 고른다]` 이름 없는 호텔 줄은 먼저 채우지 않고(후보가 하나여도) 그 일정 카드에서 후보를 고르게 묻는다
  it("puts the nameless hotel's pick-a-stay question on its card, not in the note", () => {
    const hotel = item({ id: "0-1", title: "호텔", status: "review", place_state: "needs_choice", place: null });
    const ask = question({ kind: "lodging_place", question: "「호텔」 — 묵을 숙소를 후보에서 골라 주세요(후보가 하나여도 고르신 뒤에 넣어요)", quote: "호텔" });
    const next = withQuestions([ask], [item({ id: "0-0" }), hotel]);
    const view = reviewResultOf(next, readingOf(next))!;
    expect(view.items.find((entry) => entry.id === "0-1")!.unfound).toEqual({ question: ask.question, blocked: false });
    expect(view.prefill).toBeNull();
  });
});

describe("`[2026-10-21 사용자 결정 — P6]` the interpretation questions the first check stops to ask", () => {
  const field = (value: unknown) => ({ value, method: "customer" as const, evidence: {}, needs_review: false, note: null });
  const question = (fields: Record<string, unknown> = {}) => ({ id: "q-0-5", kind: "interpretation", question: "계획서의 「14시~16시 정도 시간이 비는데」를 어떻게 이해할까요?", quote: "14시~16시 정도 시간이 비는데",
    line: 5, item: "0-3", source_id: "s1", index: 3, answer: null, applied: "reading", actions: ["pick_myself"], options: [
      { id: "reading", label: "14:00~16:00 빈 시간", recommended: true, reason: "읽기 AI 가 빈 시간으로 읽었어요", effect: "일정에 넣지 않고 14:00~16:00 빈 시간으로 둬요", action: null, query: null },
      { id: "item_search", label: "「정도」 이름 그대로 찾기", recommended: false, reason: null, effect: "14:00 일정으로 넣고 「정도」을 장소 검색에서 직접 골라요", action: "pick_myself", query: "정도" }], ...fields });
  const intake = (interpretations: unknown[]) => ({ interpretations, sources: [{ source_id: "s1", kind: "text", filename: null, transcribed: false, lines: [], trip: {}, items: [
    { index: 3, line: 5, day: null, date: "2026-10-01", fields: { title: field("정도"), starts_at: field("14:00"), removed: { ...field(true), method: "llm_agent" as const } } }] }] }) as unknown as Pick<IntakeView, "interpretations" | "sources">;
  const days = [{ day: 1, date: "2026-10-01" }];

  it("places a question not answered at its line's day and time, with the server's words and options", () => {
    expect(asksOf(intake([question()]), days)).toEqual([{ id: "q-0-5", itemId: "0-3", day: 1, date: "2026-10-01", startsAt: "14:00", title: "정도",
      question: "계획서의 「14시~16시 정도 시간이 비는데」를 어떻게 이해할까요?", quote: "14시~16시 정도 시간이 비는데", options: [
        { id: "reading", label: "14:00~16:00 빈 시간", recommended: true, reason: "읽기 AI 가 빈 시간으로 읽었어요", effect: "일정에 넣지 않고 14:00~16:00 빈 시간으로 둬요", pickMyself: false, query: null },
        { id: "item_search", label: "「정도」 이름 그대로 찾기", recommended: false, reason: null, effect: "14:00 일정으로 넣고 「정도」을 장소 검색에서 직접 골라요", pickMyself: true, query: "정도" }] }]);
  });

  it("leaves out a question already answered, one whose stop the plan holds again, and one it cannot read", () => {
    expect(asksOf(intake([question({ answer: "reading" })]), days)).toEqual([]);
    expect(asksOf(intake([question({ applied: "item" })]), days)).toEqual([]);
    expect(asksOf(intake([question({ index: 9 })]), days)).toEqual([]);
    expect(asksOf(intake([question({ options: [] })]), days)).toEqual([]);
    expect(asksOf(intake([question({ kind: "other" })]), days)).toEqual([]);
    expect(asksOf({ sources: [] } as unknown as Pick<IntakeView, "interpretations" | "sources">, days)).toEqual([]);
  });

  // `[2026-10-26 사용자 지시 — 호텔 종류 확인]` 호텔 줄의 종류(숙박 · 활동 · 식사) 질문도 같은 화면 길로 묻는다 — 서버 문구 · 선택지 그대로, 답한 뒤에는 그리지 않는다
  it("asks the hotel's kind with the server's three options, the reading on top, and not once answered", () => {
    const kind = question({ id: "k-0-1", type: "kind", question: "「롯데호텔 서울」을 어떤 일정으로 볼까요? — 숙박 · 활동 · 식사 중에 골라 주세요", quote: "15:00 롯데호텔 서울",
      applied: "reading", options: [
        { id: "reading", label: "숙박", recommended: true, action: null, query: null, reason: "읽기 AI 가 숙박으로 읽었어요", effect: "숙박으로 둬요" },
        { id: "activity", label: "활동", recommended: false, action: null, query: null, reason: null, effect: "활동 일정으로 둬요" },
        { id: "dining", label: "식사", recommended: false, action: null, query: null, reason: null, effect: "식사 일정으로 둬요" }] });
    const [ask] = asksOf(intake([kind]), days);
    expect(ask.question).toBe(kind.question);
    expect(ask.options.map((option) => [option.id, option.label, option.recommended, option.pickMyself])).toEqual([
      ["reading", "숙박", true, false], ["activity", "활동", false, false], ["dining", "식사", false, false]]);
    expect(asksOf(intake([{ ...kind, answer: "activity", applied: "activity" }]), days)).toEqual([]);
  });
});
