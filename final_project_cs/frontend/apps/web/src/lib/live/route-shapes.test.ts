import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { resetSessionState } from "./client";
import { getRouteShapes, pointsOf, readRouteShapes } from "./route-shapes";
import { answeringSession } from "./session-kit";

const shape = (patch: Record<string, unknown> = {}) => ({
  item_id: "m1", from_item_id: "a", to_item_id: "b", from: "경복궁", to: "광장시장", mode: "walk",
  line: { type: "LineString", coordinates: [[126.977, 37.5796], [126.99, 37.57], [127.0, 37.57]] },
  source: "local_road_graph", grade: "추정", distance_m: 1830, note: null, ...patch,
});

describe("reading the route lines the server gives", () => {
  it("turns GeoJSON [lng, lat] into {lat, lng} in the order of the line, and keeps what the server said about it", () => {
    const { attribution, shapes } = readRouteShapes({ trip_id: "t1", attribution: "경로선: 지도 데이터 © OpenStreetMap contributors (ODbL)", shapes: [shape()] });
    expect(attribution).toContain("ODbL");
    expect(shapes).toHaveLength(1);
    expect(shapes[0]).toMatchObject({ itemId: "m1", fromItemId: "a", toItemId: "b", from: "경복궁", to: "광장시장", mode: "walk", source: "local_road_graph", grade: "추정", distanceM: 1830, note: null });
    expect(shapes[0].points[0]).toEqual({ lat: 37.5796, lng: 126.977 });          // ★the first number is the longitude
    expect(shapes[0].points).toHaveLength(3);
  });

  it("drops what it cannot draw: a point that is not a finite pair in range, a line with fewer than two points, a shape without its two ends", () => {
    expect(pointsOf([[126.9, 37.5], ["x", 1], [200, 10], [127.0, 91], [127.0, 37.6]])).toEqual([{ lat: 37.5, lng: 126.9 }, { lat: 37.6, lng: 127.0 }]);
    expect(pointsOf([[126.9, 37.5]])).toEqual([]);                                  // one point is not a line
    expect(pointsOf("nope")).toEqual([]);
    const { shapes } = readRouteShapes({ shapes: [
      shape({ line: { type: "Point", coordinates: [126.9, 37.5] } }),               // not a LineString
      shape({ from_item_id: null }),                                                // no start stop
      shape({ item_id: "" }),
      shape({ item_id: "ok" }),
      null,
    ] });
    expect(shapes.map((entry) => entry.itemId)).toEqual(["ok"]);
  });

  it("reads a kind it does not know as 'unknown' — never as a good road — and keeps the attribution text, with a fallback when the server leaves it out", () => {
    const { attribution, shapes } = readRouteShapes({ shapes: [shape({ mode: "hover", source: "magic", grade: "great", distance_m: -5, note: "  " })] });
    expect(shapes[0]).toMatchObject({ mode: "unknown", source: "unknown", grade: "unknown", distanceM: null, note: null });
    expect(attribution).toContain("OpenStreetMap");
    expect(readRouteShapes(null)).toMatchObject({ shapes: [] });
  });
});

describe("asking for the lines of a trip", () => {
  let replies: Response[];
  let calls: string[];

  beforeEach(() => {
    replies = [];
    calls = [];
    vi.stubGlobal("window", { localStorage: { getItem: () => null, setItem: () => {}, removeItem: () => {} }, dispatchEvent: () => true });
    vi.stubGlobal("fetch", answeringSession(async (url) => { calls.push(url); return replies.shift() ?? new Response("{}", { status: 200 }); }));
  });
  afterEach(() => { vi.unstubAllGlobals(); resetSessionState(); });

  it("reads the lines from the trip's own route", async () => {
    replies.push(new Response(JSON.stringify({ trip_id: "t 1", attribution: "경로선: …", shapes: [shape()] }), { status: 200 }));
    const result = await getRouteShapes("t 1", "ko");
    expect(result?.shapes).toHaveLength(1);
    expect(calls[0]).toMatch(/\/v1\/web\/trips\/t%201\/route-shapes$/);
  });

  it("takes 404 and 405 as 'the server has no such route yet' (null), not as a failure; any other refusal is a failure", async () => {
    replies.push(new Response(JSON.stringify({ detail: "Not Found" }), { status: 404 }));
    expect(await getRouteShapes("t1", "ko")).toBeNull();
    replies.push(new Response(JSON.stringify({ error: { code: "not_found", message: "resource not found" } }), { status: 404 }));
    expect(await getRouteShapes("t1", "ko")).toBeNull();
    replies.push(new Response("{}", { status: 405 }));
    expect(await getRouteShapes("t1", "ko")).toBeNull();
    replies.push(new Response(JSON.stringify({ error: { code: "internal_error", message: "서버 오류" } }), { status: 500 }));
    await expect(getRouteShapes("t1", "ko")).rejects.toMatchObject({ code: "internal_error" });
  });
});
