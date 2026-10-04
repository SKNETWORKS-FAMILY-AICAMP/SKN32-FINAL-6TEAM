import { describe, expect, it } from "vitest";
import type { RouteShape } from "@/lib/live/route-shapes";
import type { TripStop } from "../trip/model";
import { isGuess, routeNotes, toMapLines, visibleShapes } from "./route-lines";

const stop = (id: string, coordinates: TripStop["coordinates"]): TripStop => ({ id, title: id, date: "2026-10-01", time: "09:00", coordinates } as TripStop);
const shape = (patch: Partial<RouteShape> = {}): RouteShape => ({
  itemId: "m1", fromItemId: "a", toItemId: "b", from: "경복궁", to: "광장시장", mode: "walk", source: "local_road_graph", grade: "추정", distanceM: 1830, note: null,
  points: [{ lat: 37.5796, lng: 126.977 }, { lat: 37.57, lng: 127.0 }], ...patch,
});

describe("which route lines go on the map", () => {
  const stops = [stop("a", { lat: 37.5796, lng: 126.977 }), stop("b", { lat: 37.57, lng: 127.0 }), stop("c", null)];

  it("draws a line only when both stops around the move are on the day shown and have a place", () => {
    const lines = visibleShapes([shape(), shape({ itemId: "m2", fromItemId: "b", toItemId: "c" }), shape({ itemId: "m3", fromItemId: "x", toItemId: "a" })], stops);
    expect(lines.map((entry) => entry.itemId)).toEqual(["m1"]);              // c has no place, x is another day
    expect(visibleShapes(undefined, stops)).toEqual([]);
    expect(visibleShapes([], stops)).toEqual([]);
  });

  it("draws a guess dashed: a straight line, no ground for it, or a kind it does not know — a real road is solid", () => {
    expect(isGuess(shape())).toBe(false);
    expect(isGuess(shape({ source: "stations", mode: "subway" }))).toBe(false);   // stations are joined in order: solid, but the caption says what it is
    expect(isGuess(shape({ source: "straight_line" }))).toBe(true);
    expect(isGuess(shape({ grade: "근거없음" }))).toBe(true);
    expect(isGuess(shape({ source: "unknown" }))).toBe(true);
    expect(toMapLines([shape(), shape({ itemId: "m2", source: "straight_line" })]).map((line) => [line.id, line.dashed])).toEqual([["m1", false], ["m2", true]]);
  });

  it("names a line for the pointer and the screen reader: where from, where to, how, how far", () => {
    expect(toMapLines([shape()])[0].title).toBe("경복궁 → 광장시장 · 도보 1.8km");
    expect(toMapLines([shape({ distanceM: 420, mode: "taxi" })])[0].title).toBe("경복궁 → 광장시장 · 택시 420m");
    expect(toMapLines([shape({ from: null, to: null, distanceM: null, mode: "unknown" })])[0].title).toBe("출발 → 도착 · 이동");
  });

  it("says what the drawn lines do NOT mean — only for the kinds that are on the map", () => {
    expect(routeNotes([shape()])).toEqual([]);
    expect(routeNotes([shape({ source: "straight_line" })])).toEqual(["점선은 길을 몰라 두 곳을 직선으로 이은 구간이에요."]);
    expect(routeNotes([shape({ source: "stations", mode: "subway" })])).toEqual(["지하철 구간은 역 위치를 순서대로 이은 선이라 실제 선로 모양이 아니에요."]);
    expect(routeNotes([shape({ source: "straight_line", mode: "bus" })])).toEqual(["점선은 길을 몰라 두 곳을 직선으로 이은 구간이에요.", "버스는 정류장 정보가 없어 직선으로 이어요."]);
  });
});
