import { describe, expect, it } from "vitest";
import { routeLabels } from "./route-labels";
import type { MapLine, MapView } from "./model";

const view: MapView = { south: 37.55, north: 37.58, west: 126.96, east: 127, width: 400, height: 400, zoom: 15 };
const line: MapLine = { id: "ride", mode: "subway", dashed: true, title: "지하철", points: [{ lat: 37.565, lng: 126.94 }, { lat: 37.565, lng: 127.02 }] };

describe("route names on the visible path", () => {
  it("clips a path crossing the view even when both stops are off screen", () => {
    const [label] = routeLabels(view, [line], [], 64, 24);
    expect(label.x).toBeCloseTo(200);
    expect(label.y).toBeGreaterThan(190);
    expect(label.y).toBeLessThan(210);
    expect(label.dashed).toBe(true);
  });
  it("omits names at overview zoom and outside the visible area", () => {
    expect(routeLabels({ ...view, zoom: 14 }, [line], [])).toEqual([]);
    expect(routeLabels({ ...view, west: 127.1, east: 127.14 }, [line], [])).toEqual([]);
    expect(routeLabels(view, [line], [], 220)).toEqual([]);
  });
  it("keeps pins and competing route names readable", () => {
    expect(routeLabels(view, [line], [{ id: "stop", coordinates: { lat: 37.565, lng: 126.98 }, order: 1, title: "", date: "", time: "" }])).toEqual([]);
    expect(routeLabels(view, [line, { ...line, id: "other" }], [])).toHaveLength(1);
  });
  it("uses a clear quarter of the visible route when its middle overlaps an end pin", () => {
    const partial = { ...line, points: [line.points[0], { lat: 37.565, lng: 126.98 }] };
    const labels = routeLabels(view, [partial], [{ id: "stop", coordinates: partial.points[1], order: 1, title: "", date: "", time: "" }]);
    expect(labels).toHaveLength(1);
    expect(labels[0].x).toBeLessThan(104);
  });
});
