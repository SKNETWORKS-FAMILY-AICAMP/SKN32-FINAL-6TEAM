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
  const review = {
    revision: 3, built_at: "", engine: "timetable" as const, ready: false, needs: { items: 1, moves: 0, total: 1 },
    items: [item({}), item({ id: "0-1", index: 1, title: "광장시장", starts_at: "12:00", ends_at: "13:00", status: "review", locked: true, place: place("광장시장"),
      rows: [{ row: "closed", result: "bad", text: "수요일은 쉬어요" }] })],
    moves: [move()],
  };
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
      minutes: 12, arriveAt: "11:17", slackMin: 8, estimated: false,
      checks: [{ kind: "route", result: "ok", text: "경복궁 → 광장시장" }, { kind: "arrival", result: "ok", text: "8분 여유" }],
    }]);
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
