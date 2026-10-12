import { describe, expect, it } from "vitest";
import { readRouteShapes } from "@/lib/live/route-shapes";
import { rideLines, routeNotes, toMapLines } from "./route-lines";

const raw = (source: string, mode: string, rides: unknown[]) => ({
  shapes: [{ item_id: "move", from_item_id: "a", to_item_id: "b", mode, source,
    grade: "추정", line: { type: "LineString", coordinates: [[127.01, 37.54], [127.02, 37.55], [127.03, 37.56]] }, rides }],
});
const bus = { mode: "bus", line: "2016", from: "성수역4번출구", to: "건대입구역6번출구", count: 3, filled: true };
const subway = { mode: "subway", line: "2호선", from: "시청", to: "아현", count: 42, filled: true };

describe("ordered transit stops through the actual web parser and map model", () => {
  it("keeps a known bus-stop source, its ordered points and bus-stop label", () => {
    const shape = readRouteShapes(raw("bus_stops", "bus", [bus])).shapes[0];
    expect(shape.source).toBe("bus_stops");
    expect(shape.rides[0].mode).toBe("bus");
    expect(toMapLines([shape])[0]).toMatchObject({ dashed: false, points: [{ lng: 127.01, lat: 37.54 }, { lng: 127.02, lat: 37.55 }, { lng: 127.03, lat: 37.56 }] });
    expect(rideLines(shape, (ko) => ko)).toEqual(["2016 · 성수역4번출구→건대입구역6번출구 · 3개 정류장"]);
    expect(routeNotes([shape])).toEqual(["버스 구간은 정류장 위치를 순서대로 이은 선이라 실제 도로 모양이 아니에요."]);
  });

  it("keeps mixed stop geometry and explains both its bus and subway approximations", () => {
    const shape = readRouteShapes(raw("transit_stops", "mixed", [bus, subway])).shapes[0];
    expect(shape.source).toBe("transit_stops");
    expect(toMapLines([shape])[0].dashed).toBe(false);
    expect(routeNotes([shape])).toEqual([
      "지하철 구간은 역 위치를 순서대로 이은 선이라 실제 선로 모양이 아니에요.",
      "버스 구간은 정류장 위치를 순서대로 이은 선이라 실제 도로 모양이 아니에요.",
    ]);
    expect(rideLines(shape, (ko, en) => en)).toEqual(["2016 · 성수역4번출구→건대입구역6번출구 · 3 stops", "2호선 · 시청→아현 · 42 stations"]);
  });

  it("does not present an unfilled bus stretch as an established stop path", () => {
    const shape = readRouteShapes(raw("straight_line", "bus", [{ ...bus, filled: false, count: undefined }])).shapes[0];
    expect(toMapLines([shape])[0].dashed).toBe(true);
    expect(rideLines(shape, (ko) => ko)).toEqual(["2016 · 성수역4번출구→건대입구역6번출구 · 정류장 사이는 직선"]);
    expect(routeNotes([shape])).toContain("버스는 정류장 정보가 없어 직선으로 이어요.");
  });

  it("keeps an unrecognized source conservative", () => {
    const shape = readRouteShapes(raw("future_source", "bus", [bus])).shapes[0];
    expect(shape.source).toBe("unknown");
    expect(toMapLines([shape])[0].dashed).toBe(true);
  });
});
