import { describe, expect, it } from "vitest";
import type { IntakeView } from "@/lib/live/intake";
import { emptyStream, reduceStream, toIntakeEvent, type StreamState } from "@/lib/live/intake-events";
import type { Candidate, ReviewItem, ReviewMove, ReviewedIntakeView } from "@/lib/live/intake-review";
import { readingOf } from "./from-intake";
import { draftOfItem } from "./model";
import { planCandidate, reviewResultOf, safePhotoUrl, streamingViewOf } from "./from-review";

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

describe("D-025 「우리가 채움」 — the server filled in first", () => {
  const filledIntake = (extra: Partial<ReviewedIntakeView>) => intake("review", "review", {
    review: { items: [item({ id: "0-0" }), item({ id: "0-1", title: "숙소 근처", status: "adjusted" })], moves: [] } as unknown as ReviewedIntakeView["review"],
    ...extra,
  });

  it("puts one ✎ line with the reason first on the stop the server filled, and nowhere else", () => {
    const next = filledIntake({ prefill: { filled: [{ item: "0-1", title: "근처 식당", owner: "dining_team", owner_label: "식당 팀",
      reason: "계획서의 「저녁은 숙소 근처에서」 — 근처 식당으로 채웠어요", gap: "meal_place", new: false }], questions: [], kept: [] } });
    const view = reviewResultOf(next, readingOf(next))!;
    const [plain, filled] = view.items;
    expect(plain.checks.some((check) => check.text.startsWith("우리가 채움"))).toBe(false);
    expect(filled.checks[0]).toEqual({ kind: "place", result: "filled", text: "우리가 채움 · 계획서의 「저녁은 숙소 근처에서」 — 근처 식당으로 채웠어요" });
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
