import { describe, expect, it } from "vitest";
import { translator } from "@/lib/i18n";
import type { ReviewItem, ReviewMove } from "@/lib/live/intake-review";
import { dayHeading, headSummary, MARK_TONE, projectDay, statusTone, statusWord, timeline } from "./review-model";

const ko = translator("ko");
const en = translator("en");

function item(id: string, patch: Partial<ReviewItem> = {}): ReviewItem {
  return { id, source_id: "s1", index: Number(id.split("-")[1]), title: id, kind: null, day: 1, date: "2026-10-01", starts_at: "10:00", ends_at: "11:00", locked: false,
    status: "keep", can_lock: true, place_state: "found", place: { name: id, latitude: 37.57, longitude: 126.98, source: "tour_api", kind: null }, candidates_hint: null, rows: [], ...patch };
}
function move(from: string, to: string, patch: Partial<ReviewMove> = {}): ReviewMove {
  return { from, to, day: 1, date: "2026-10-01", status: "keep", mode: "walk", mode_label: "도보", minutes: 10, km: 0.5, depart: "11:00", arrive: "11:10", slack_min: 5, basis: "timetable", summary: "도보 10분", rows: [], ...patch };
}

describe("marks", () => {
  it("draws every verdict with its own mark, and an unknown one as grey — never as a check", () => {
    expect(MARK_TONE).toEqual({ ok: "ok", filled: "adj", warn: "warn", bad: "bad", unknown: "none" });
    expect(statusTone("keep")).toBe("ok");
    expect(statusTone("adjusted")).toBe("adj");
    expect(statusTone("review")).toBe("warn");
    expect(statusTone("waiting")).toBe("none");
    expect(statusTone(null)).toBe("none");
  });

  it("says the status in words, and 'checking' while the check is not done", () => {
    expect(statusWord("review", ko)).toBe("확인 필요");
    expect(statusWord("adjusted", en)).toBe("Adjusted");
    expect(statusWord(null, ko)).toBe("확인 중");
  });
});

describe("day headings", () => {
  it("reads the weekday from the date", () => {
    expect(dayHeading(1, "2026-10-01", ko)).toEqual({ title: "1일차", sub: "10.01 목" });
    expect(dayHeading(2, "2026-10-02", en)).toEqual({ title: "Day 2", sub: "10.02 Fri" });
  });
  it("has no date part for a day the server could not date", () => {
    expect(dayHeading(null, null, ko)).toEqual({ title: "날짜 미정", sub: "" });
    expect(dayHeading(3, "not a date", ko)).toEqual({ title: "3일차", sub: "" });
  });
});

describe("the list in the sheet", () => {
  const items = [item("0-0"), item("0-1"), item("0-2"), item("0-3", { day: 2, date: "2026-10-02" })];
  const moves = [move("0-0", "0-1"), move("0-1", "0-2", { status: "review" })];

  it("puts a heading before each day, the stops in order, and the measured leg between two stops of one day", () => {
    const keys = timeline({ items, moves }).map((entry) => entry.key);
    expect(keys).toEqual(["day:1|2026-10-01", "item:0-0", "move:0-0:0-1", "item:0-1", "move:0-1:0-2", "item:0-2", "day:2|2026-10-02", "item:0-3"]);
  });

  it("marks the last stop of each day — the rail ends there", () => {
    const lasts = timeline({ items, moves }).flatMap((entry) => entry.kind === "item" ? [[entry.item.id, entry.last]] : []);
    expect(lasts).toEqual([["0-0", false], ["0-1", false], ["0-2", true], ["0-3", true]]);
  });

  it("leaves a gap where the server measured no leg, and never draws a leg across two days", () => {
    const keys = timeline({ items: [item("0-0"), item("0-1"), item("0-2", { day: 2, date: "2026-10-02" })], moves: [move("0-1", "0-2")] }).map((entry) => entry.key);
    expect(keys).toEqual(["day:1|2026-10-01", "item:0-0", "item:0-1", "day:2|2026-10-02", "item:0-2"]);
  });

  it("is empty for a plan with no stops", () => {
    expect(timeline({ items: [], moves: [] })).toEqual([]);
  });
});

describe("what is left to do", () => {
  const needs = (items: number, moves: number) => ({ needs: { items, moves, total: items + moves }, ready: items + moves === 0 });
  it("says what needs the customer, in the words the mockup uses", () => {
    expect(headSummary(needs(1, 1), ko)).toEqual({ tone: "warn", text: "장소 1곳 · 이동 1구간 확인 필요" });
    expect(headSummary(needs(0, 2), ko)).toEqual({ tone: "warn", text: "이동 2구간 확인 필요" });
    expect(headSummary(needs(2, 0), en)).toEqual({ tone: "warn", text: "2 places to review" });
  });
  it("says nothing is left only when nothing is", () => {
    expect(headSummary(needs(0, 0), ko)).toEqual({ tone: "ok", text: "고칠 곳이 없어요" });
  });
});

describe("the concept map", () => {
  it("draws stops from their real coordinates, north up, filling the area", () => {
    const spots = projectDay([item("a", { place: { name: "a", latitude: 37.58, longitude: 126.97, source: null, kind: null } }),
      item("b", { place: { name: "b", latitude: 37.55, longitude: 126.99, source: null, kind: null } })]);
    const [a, b] = spots;
    expect(a.located && b.located).toBe(true);
    expect(a.y).toBeLessThan(b.y);                 // a is further north → higher on the map
    expect(a.x).toBeLessThan(b.x);                 // a is further west → further left
    for (const spot of spots) { expect(spot.x).toBeGreaterThan(0); expect(spot.x).toBeLessThan(100); expect(spot.y).toBeGreaterThan(0); expect(spot.y).toBeLessThan(100); }
  });

  it("puts a stop without coordinates between its neighbours and marks it as not located", () => {
    const spots = projectDay([item("a"), item("b", { place: null, place_state: "unresolved" }), item("c", { place: { name: "c", latitude: 37.55, longitude: 127.0, source: null, kind: null } })]);
    const [a, b, c] = spots;
    expect(b.located).toBe(false);
    expect(b.x).toBeCloseTo((a.x + c.x) / 2, 5);
    expect(b.y).toBeCloseTo((a.y + c.y) / 2, 5);
  });

  it("keeps a single stop, or stops on one spot, from blowing up", () => {
    const only = projectDay([item("a")]);
    expect(only[0]).toMatchObject({ x: 50, y: 50, located: true });
    const same = projectDay([item("a"), item("b")]);
    expect(Math.abs(same[0].x - same[1].x)).toBeLessThan(1);
  });

  it("puts a day with nothing located in the middle instead of failing", () => {
    expect(projectDay([item("a", { place: null })])).toEqual([{ id: "a", x: 50, y: 50, located: false }]);
  });
});
