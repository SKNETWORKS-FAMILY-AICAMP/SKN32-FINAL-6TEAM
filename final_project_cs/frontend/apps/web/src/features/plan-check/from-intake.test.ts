import { describe, expect, it } from "vitest";
import type { IntakeItem, IntakeView } from "@/lib/live/intake";
import { candidatesOf, readingOf, resultOf } from "./from-intake";

const field = (value: unknown) => ({ value, method: "rule" as const, evidence: {}, needs_review: false, note: null });
const item = (index: number, line: number, day: number | null, fields: IntakeItem["fields"]): IntakeItem => ({ index, line, day, date: null, fields });

function intake(stage: string, status: IntakeView["status"], sources: IntakeView["sources"]): IntakeView {
  return { intake_id: "i1", status, stage, stage_label: "", revision: 1, fatal: null, trip_id: null, sources, check: null, needs_review: [] };
}

const text = (lines: [string, boolean][], items: IntakeItem[] = []) => ({
  source_id: "s1", kind: "text", filename: null, transcribed: false, items, trip: {}, reading: null,
  lines: lines.map(([value, read], at) => ({ no: at + 1, text: value, read })),
});

describe("plan check reading, from the server's intake", () => {
  it("maps the server's stage: received stays received, transcribing and reading are reading, a finished read stays reading", () => {
    expect(readingOf(intake("received", "reading", [])).stage).toBe("received");
    expect(readingOf(intake("transcribing", "reading", [])).stage).toBe("reading");
    expect(readingOf(intake("reading", "reading", [])).stage).toBe("reading");
    expect(readingOf(intake("review", "review", [])).stage).toBe("reading");     // the review screen takes over from here
  });

  it("keeps each line and whether the server read it, and the stop a read line became — day or time only when the server has one", () => {
    const view = readingOf(intake("reading", "reading", [text([["10/1 09:00 경복궁 관람", true], ["점심은 광장시장", true], ["메모: 우산", false]], [
      item(0, 1, 1, { title: field("경복궁 관람"), starts_at: field("09:00") }),
      item(1, 2, null, { title: field("광장시장") }),
    ])]));
    expect(view.lines).toEqual([
      { no: 1, text: "10/1 09:00 경복궁 관람", read: true, found: { kind: "item", day: 1, startsAt: "09:00", title: "경복궁 관람" } },
      { no: 2, text: "점심은 광장시장", read: true, found: { kind: "item", day: null, startsAt: null, title: "광장시장" } },
      { no: 3, text: "메모: 우산", read: false, found: null },
    ]);
    expect(view.items).toEqual([]);                                                 // places and checks are not mapped yet
  });

  it("numbers lines across sources and leaves out a stop the customer removed", () => {
    const photo = { ...text([["11:00 올리브영", true]], [item(0, 1, 1, { title: field("올리브영"), removed: field(true) })]), source_id: "s2", kind: "image" };
    const view = readingOf(intake("reading", "reading", [text([["10/1 09:00 경복궁", true]]), photo]));
    expect(view.lines.map((line) => [line.no, line.text, line.found])).toEqual([[1, "10/1 09:00 경복궁", null], [2, "11:00 올리브영", null]]);
  });
});

describe("plan check result, from an intake the server has read", () => {
  const found = { value: { name: "경복궁", latitude: 37.5796, longitude: 126.977 }, method: "lookup" as const, evidence: {}, needs_review: false, note: null };
  const flaggedStart = { value: "11:00", method: "rule" as const, evidence: { line: 2 }, needs_review: true, note: "시각이 두 가지로 읽혔어요" };
  function read(items: IntakeItem[], check: Partial<NonNullable<IntakeView["check"]>> = {}): IntakeView {
    return { ...intake("review", "review", [text([["10/1 09:00 경복궁", true], ["11시 올리브영", true], ["12시 광장시장", true], ["13시 뺀 곳", true]], items)]),
      check: { ready: true, problems: [], filled: [], items: items.length, title: "10월 서울 여행", plan: { requested: false, start_date: null, days: null, party_size: null, preferences: "" }, ...check } };
  }

  it("shows each stop with only what the server said: the place it found, a problem, a flag, a time it filled in", () => {
    const view = resultOf(read([
      item(0, 1, 1, { title: field("경복궁"), starts_at: field("09:00"), date: field("2026-10-01"), place: found }),
      item(1, 2, 1, { title: field("올리브영"), starts_at: flaggedStart, date: field("2026-10-01") }),
      item(2, 3, 2, { title: field("광장시장"), starts_at: field("12:00"), date: field("2026-10-02") }),
      item(3, 4, 2, { title: field("뺀 곳"), removed: { ...field(true), method: "customer" as const } }),
    ], {
      problems: [{ code: "no_place", field: "items[1].place", message: "장소를 정하지 못했습니다", source_id: "s1" }],
      filled: [{ source_id: "s1", field: "items[2].ends_at", value: "13:00", method: "rule", note: "끝 시각이 없어 식사 1시간으로 채웠어요" }],
    }));
    expect(view).toMatchObject({ stage: "done", title: "10월 서울 여행", moves: [], days: [{ day: 1, date: "2026-10-01" }, { day: 2, date: "2026-10-02" }] });
    expect(view.items.map((entry) => [entry.id, entry.day, entry.startsAt, entry.title, entry.verdict])).toEqual([
      ["s1:0", 1, "09:00", "경복궁", "keep"], ["s1:1", 1, "11:00", "올리브영", "review"], ["s1:2", 2, "12:00", "광장시장", "adjusted"],
    ]);
    expect(view.items[0].coordinates).toEqual({ lat: 37.5796, lng: 126.977 });
    expect(view.items[0].checks).toEqual([{ kind: "place", result: "ok", text: "경복궁" }]);
    expect(view.items[1].checks).toEqual([
      { kind: "place", result: "bad", text: "장소를 정하지 못했습니다" },
      { kind: "time", result: "warn", text: "시각이 두 가지로 읽혔어요" },
    ]);
    expect(view.items[1].coordinates).toBeNull();
    expect(view.items[2].checks).toEqual([{ kind: "time", result: "filled", text: "끝 시각이 없어 식사 1시간으로 채웠어요" }]);
    // Opening hours and closed days are not in the response: no such rows.
    expect(view.items.flatMap((entry) => entry.checks.map((check) => check.kind))).not.toContain("hours");
  });

  it("does not flag what the server only assumed (a year or a day it filled); a stop the customer changed counts as adjusted", () => {
    const view = resultOf(read([
      item(0, 1, 1, { title: field("경복궁"), place: found, date: { value: "2026-10-01", method: "rule", evidence: { how: "year_filled" }, needs_review: true, note: "해를 2026년으로 두었어요" } }),
      item(1, 2, 1, { title: field("올리브영"), starts_at: { ...flaggedStart, method: "customer" as const } }),
    ]));
    expect(view.items.map((entry) => entry.verdict)).toEqual(["keep", "adjusted"]);
    expect(view.items[1].checks).toEqual([]);
  });
});

describe("the places the server weighed for one stop (its alternatives on the live route)", () => {
  const picked = { value: { name: "올리브영 광화문점", latitude: 37.5717, longitude: 126.9791 }, method: "lookup" as const, needs_review: true, note: "이름이 특정하지 않아…",
    evidence: { source: "kakao", chosen_from: ["올리브영 광화문점", "올리브영 종각역점", "올리브영 인사동점", 7] } };
  const view = { ...intake("review", "review", [text([["11시 올리브영", true]], [item(0, 1, 1, { title: field("올리브영"), place: picked })])]), check: null };

  it("lists the names it chose among, without the one it picked, by the order it gave — names only, nothing made up", () => {
    expect(candidatesOf(view, "s1:0")).toEqual([
      { id: "s1:0:올리브영 종각역점", name: "올리브영 종각역점", source: "candidate", rank: 1, distance: null, coordinates: null, info: null, checks: [] },
      { id: "s1:0:올리브영 인사동점", name: "올리브영 인사동점", source: "candidate", rank: 2, distance: null, coordinates: null, info: null, checks: [] },
    ]);
  });

  it("has none when the server weighed nothing, or for a stop it does not know", () => {
    const plain = { ...view, sources: [text([["11시 경복궁", true]], [item(0, 1, 1, { title: field("경복궁") })])] };
    expect(candidatesOf(plain, "s1:0")).toEqual([]);
    expect(candidatesOf(view, "s9:0")).toEqual([]);
  });

  it("maps the result with nothing locked, no details, no first alternative, and never 「changed since the last check」", () => {
    const result = resultOf({ ...view, check: { ready: false, problems: [], filled: [], items: 1, title: "10월 서울 여행", plan: { requested: false, start_date: null, days: null, party_size: null, preferences: "" } } });
    expect(result.items[0]).toMatchObject({ locked: false, info: null, suggestion: null });
    expect(result).toMatchObject({ dirty: false, rechecking: null });
  });
});
