import { describe, expect, it } from "vitest";
import { insertionPoints } from "./insertion-points";
import { exampleDone } from "./test-views";

describe("inserting on the correct side of a travel row", () => {
  it("keeps departure and arrival seams distinct and uses arrival after travel", () => {
    const view = { ...exampleDone, moves: exampleDone.moves.map((move) => ({ ...move, arriveAt: "11:42" })) };
    const points = insertionPoints(view, { day: 1, date: "2026-10-01" });
    expect(points.find((point) => point.key === "1:move:a-b")).toMatchObject({ anchorId: "a", start: "11:30", side: "before-move" });
    expect(points.find((point) => point.key === "1:item:b")).toMatchObject({ anchorId: "b", start: "11:42", side: "before-stop" });
    expect(new Set(points.map((point) => point.key)).size).toBe(points.length);
  });
  it("never uses the previous day's last stop as the new day's anchor", () => {
    const view = { ...exampleDone, items: [...exampleDone.items.filter((item) => item.day === 1), { ...exampleDone.items[0], id: "next-day", day: 2, date: "2026-10-02", startsAt: "09:00" }] };
    expect(insertionPoints(view, { day: 2, date: "2026-10-02" })[0]).toMatchObject({ anchorId: "next-day", previous: null, date: "2026-10-02", start: "08:00", end: "09:00" });
  });
  it("does not invent a clock time when the neighbouring stop has no time", () => {
    const view = { ...exampleDone, items: [{ ...exampleDone.items[0], startsAt: "", endsAt: "" }], moves: [] };
    expect(insertionPoints(view, { day: 1, date: "2026-10-01" }).every((point) => point.start === "" && point.end === "")).toBe(true);
  });
  it("does not create a midnight wrap or a zero duration at the end of the day", () => {
    const view = { ...exampleDone, items: [{ ...exampleDone.items[0], startsAt: "23:30", endsAt: "23:59" }], moves: [] };
    expect(insertionPoints(view, { day: 1, date: "2026-10-01" }).at(-1)).toMatchObject({ start: "", end: "" });
  });
});

// ★`[2026-10-22 사용자 결정 — ST4F-720]` 삭제 예정(회색) 카드가 있어도 ＋ 는 남는다 — 회색 카드 바로 위 자리는 없고, 바로 아래 자리 하나가 회색 카드를 뺀 앞뒤 일정으로 이름 · 시각을 잡는다.
describe("seams around a stop marked for deletion", () => {
  const day1 = { day: 1, date: "2026-10-01" };
  it("keeps one seam under the grey card, worked out from the stops around it (the legs into and out of it still drawn)", () => {
    const points = insertionPoints(exampleDone, day1, new Set(["b"]));    // a · a-b · b · b-c · c
    expect(points).toHaveLength(6);
    expect(points.slice(1, 4)).toEqual([null, null, null]);               // above a-b, b and b-c (all grey)
    expect(points[4]).toMatchObject({ key: "1:item:c", anchorId: "c", previous: "경복궁", next: "광장시장", start: "11:30", end: "12:30", side: "before-stop" });
    expect(points.filter((point) => point && (point.previous === "올리브영" || point.next === "올리브영"))).toEqual([]);
  });
  it("uses the arrival of the new leg past the grey card (deleted on the server already)", () => {
    const view = { ...exampleDone, moves: [{ ...exampleDone.moves[0], id: "a-c", toId: "c", arriveAt: "12:05", verdict: "keep" as const }] };
    const points = insertionPoints(view, day1, new Set(["b"]));          // a · a-c · b · c
    expect(points.map((point) => point?.key ?? null)).toEqual(["1:item:a", "1:move:a-c", null, "1:item:c", "1:end"]);
    expect(points[3]).toMatchObject({ previous: "경복궁", next: "광장시장", start: "12:05", end: "12:30" });
  });
  it("ends the day after the last stop that stays", () => {
    expect(insertionPoints(exampleDone, day1, new Set(["c"])).at(-1)).toMatchObject({ key: "1:end", anchorId: "b", previous: "올리브영", next: null, start: "12:00", end: "13:00" });
  });
  it("is the same as before with nothing marked", () => {
    expect(insertionPoints(exampleDone, day1, new Set())).toEqual(insertionPoints(exampleDone, day1));
  });
});
