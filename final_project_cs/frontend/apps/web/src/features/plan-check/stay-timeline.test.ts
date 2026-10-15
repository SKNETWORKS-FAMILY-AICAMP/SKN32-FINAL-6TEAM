import { describe, expect, it } from "vitest";
import { exampleDone } from "./test-views";
import { nextStep, timeline, type PlanCheckView, type PlanItem, type PlanMove } from "./model";
import { insertionPoints } from "./insertion-points";

/**
 * `[2026-10-13 사용자 지시]` 계획 확인 화면(등록 전)에도 묵는 날 아침 「숙소 → 그날 첫 일정」 이동 — 그날 타임라인 맨 앞, 첫날 숙소 뒤 짝에서는 빠진다.
 */
const hotel: PlanItem = { ...exampleDone.items[2], id: "h", day: 1, date: "2026-10-01", startsAt: "15:00", endsAt: "11:00", title: "롯데호텔 서울",
  kind: "lodging", endDate: "2026-10-03" };
const evening: PlanMove = { ...exampleDone.moves[1], id: "h-x", fromId: "h", toId: "x", day: 1 };
const morning: PlanMove = { ...exampleDone.moves[1], id: "h:d", fromId: "h", toId: "d", day: 2, departAt: "14:30", arriveAt: "14:50", fromStay: true };
const dinner: PlanItem = { ...exampleDone.items[2], id: "x", day: 1, date: "2026-10-01", startsAt: "18:00", endsAt: "19:00", title: "명동교자" };
const view: PlanCheckView = { ...exampleDone, items: [...exampleDone.items.slice(0, 3), hotel, dinner, exampleDone.items[3]],
  moves: [...exampleDone.moves, evening, morning] };

const ids = (day: number) => timeline(view, day).map((entry) => entry.type === "item" ? entry.item.id : entry.move.id);

describe("plan check — a stay and its morning move", () => {
  it("opens the next day with the morning move and keeps the check-in day's evening move after the hotel", () => {
    expect(ids(1)).toEqual(["a", "a-b", "b", "b-c", "c", "h", "h-x", "x"]);
    expect(ids(2)).toEqual(["h:d", "d"]);
  });

  it("puts the insertion points around the morning move in the day's order", () => {
    const points = insertionPoints(view, { day: 2, date: "2026-10-02" });
    expect(points.map((point) => point.side)).toEqual(["before-move", "before-stop", "after-stop"]);
    expect(points[1].start).toBe("14:50");                                // after arriving from the hotel
  });

  it("reveals the morning move in its place, not at the very end", () => {
    let shown: PlanCheckView = { ...view, stage: "checking", items: [], moves: [] };
    const order: string[] = [];
    for (let guard = 0; guard < 500; guard += 1) {
      const next = nextStep(shown, view, true);
      if (!next) break;
      for (const move of next.moves) if (!shown.moves.some((other) => other.id === move.id)) order.push(move.id);
      for (const item of next.items) if (!shown.items.some((other) => other.id === item.id)) order.push(item.id);
      shown = next;
    }
    expect(order.indexOf("h:d")).toBeLessThan(order.indexOf("d"));
    expect(order.indexOf("h:d")).toBeGreaterThan(order.indexOf("x"));
  });
});
