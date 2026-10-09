import { describe, expect, it } from "vitest";
import { controlsLayout } from "./map-controls";
import { distanceM, edgeChips, formatDistance, metersPerPixel, niceScale, toPixels } from "./map-geometry";
import type { MapPoint, MapView } from "./model";

/** Seoul city hall at the middle of a 360 × 600 px view about 3.4 km wide. */
const view: MapView = { south: 37.5435, west: 126.9575, north: 37.5895, east: 126.9985, width: 360, height: 600, zoom: 13 };
const point = (id: string, lat: number, lng: number, order = Number(id), tone?: MapPoint["tone"]): MapPoint => ({ id, title: id, date: "", time: "", order, coordinates: { lat, lng }, tone });

describe("toPixels", () => {
  it("puts the corners at the corners of the view and the middle at the middle", () => {
    const topLeft = toPixels(view, { lat: view.north, lng: view.west });
    const bottomRight = toPixels(view, { lat: view.south, lng: view.east });
    expect(topLeft.x).toBeCloseTo(0, 5);
    expect(topLeft.y).toBeCloseTo(0, 5);
    expect(bottomRight.x).toBeCloseTo(360, 5);
    expect(bottomRight.y).toBeCloseTo(600, 5);
    const middle = toPixels(view, { lat: 37.5665, lng: 126.978 });
    expect(middle.x).toBeCloseTo(180, 0);
    expect(middle.y).toBeGreaterThan(290);                                 // Mercator: the middle in latitude is a hair above the middle in px
    expect(middle.y).toBeLessThan(310);
  });

  it("goes outside 0..width / 0..height for a place out of view", () => {
    expect(toPixels(view, { lat: view.north + 0.05, lng: 126.978 }).y).toBeLessThan(0);
    expect(toPixels(view, { lat: 37.56, lng: view.east + 0.05 }).x).toBeGreaterThan(360);
  });
});

describe("scale ruler", () => {
  it("covers about the metres a px covers and picks a round distance whose bar fits", () => {
    expect(metersPerPixel(view)).toBeGreaterThan(9);
    expect(metersPerPixel(view)).toBeLessThan(11);                          // about 3.6 km over 360 px
    const scale = niceScale(view, 34)!;
    expect(scale.meters).toBe(200);                                         // 34 px ≈ 340 m → 200 m
    expect(scale.px).toBeLessThanOrEqual(34);
    expect(scale.px).toBeGreaterThan(12);
    expect(scale.label).toBe("200m");
  });

  it("says kilometres from 1000 m and is silent when the view has no size", () => {
    const far = niceScale({ ...view, south: 36.5, north: 38.5, west: 125.5, east: 128.5 }, 34)!;
    expect(far.label).toMatch(/km$/);
    expect(niceScale({ ...view, width: 0 }, 34)).toBeNull();
  });

  it("writes distances short", () => {
    expect(formatDistance(48)).toBe("50m");
    expect(formatDistance(850)).toBe("850m");
    expect(formatDistance(1000)).toBe("1km");
    expect(formatDistance(1240)).toBe("1.2km");
    expect(formatDistance(12_400)).toBe("12km");
  });

  it("measures a great-circle distance", () => {
    expect(distanceM({ lat: 37.5665, lng: 126.978 }, { lat: 37.5665, lng: 126.978 })).toBe(0);
    expect(distanceM({ lat: 37.5665, lng: 126.978 }, { lat: 37.5665, lng: 127.978 })).toBeGreaterThan(87_000);
    expect(distanceM({ lat: 37.5665, lng: 126.978 }, { lat: 37.5665, lng: 127.978 })).toBeLessThan(89_000);
  });
});

describe("chips for stops out of view", () => {
  it("has none while every stop is in view", () => {
    expect(edgeChips(view, [point("1", 37.56, 126.97), point("2", 37.575, 126.99)])).toEqual([]);
  });

  it("stands a chip at the edge toward a stop that is out of view, with its distance, and points at it", () => {
    const [chip] = edgeChips(view, [point("1", 37.56, 126.97), point("2", 37.5665, 127.05)]);        // to the east
    expect(chip.ids).toEqual(["2"]);
    expect(chip.labels).toEqual(["2"]);
    expect(chip.x).toBeGreaterThan(280);                                                               // at the right edge
    expect(chip.x).toBeLessThanOrEqual(360 - 46);                                                      // and the whole chip inside the view
    expect(Math.abs(chip.angle)).toBeLessThan(40);                                                     // pointing right
    expect(chip.distanceM).toBeGreaterThan(5000);
  });

  it("puts stops that are close to each other on one chip (the nearest gives the distance)", () => {
    const chips = edgeChips(view, [point("1", 37.57, 126.98), point("3", 37.6, 126.98), point("4", 37.602, 126.981)]);   // two stops far to the north
    expect(chips).toHaveLength(1);
    expect(chips[0].ids).toEqual(["3", "4"]);
    expect(chips[0].labels).toEqual(["3", "4"]);
    expect(chips[0].y).toBeLessThan(120);
  });

  it("does not stand one under the bar at the top, nor point at a stop shown only as context", () => {
    const under = edgeChips(view, [point("1", 37.5885, 126.978)], { top: 64 });                       // inside the view but under the 64 px bar
    expect(under).toHaveLength(1);
    expect(under[0].y).toBeGreaterThanOrEqual(64);
    expect(edgeChips(view, [point("1", 37.7, 126.978, 1, "muted")])).toEqual([]);
  });

  it("treats what is under the sheet at the bottom as out of view, and stands its chip above the sheet", () => {
    const [chip] = edgeChips(view, [point("1", 37.5455, 126.978)], { bottom: 24 });                    // inside the view (26 px above the edge) but under the 24 px the sheet covers
    expect(chip.y).toBeLessThanOrEqual(600 - 24);
    expect(edgeChips(view, [point("1", 37.5455, 126.978)])).toEqual([]);                               // with nothing over it, it is in view
  });

  it("keeps clear of the map's own buttons at the top right", () => {
    const [chip] = edgeChips(view, [point("1", 37.62, 127.02)], { top: 64, rightKeep: 64 });          // north-east, far out
    expect(chip.x).toBeLessThanOrEqual(360 - 64 - 46);
  });

  it("is silent for a view that has no size (a map that cannot say what it shows)", () => {
    expect(edgeChips({ ...view, width: 0 }, [point("1", 37.7, 126.978)])).toEqual([]);
  });
});

describe("controlsLayout", () => {
  it("is a column while there is height, a row when the map is low, and a tab when there is no room at all", () => {
    expect(controlsLayout({ width: 390, height: 600 }, 64, 4)).toBe("column");
    expect(controlsLayout({ width: 390, height: 260 }, 64, 4)).toBe("row");
    expect(controlsLayout({ width: 390, height: 90 }, 64, 4)).toBe("tab");
    expect(controlsLayout({ width: 200, height: 260 }, 64, 4)).toBe("tab");                              // not even a row fits across
    expect(controlsLayout({ width: 0, height: 0 }, 64, 4)).toBe("column");                              // not measured yet
  });
});

describe("a pin that could be cut by the edge", () => {
  it("gets a chip when its coordinate is within a few px of the left edge (the drop would be cut), and none when it is well inside", () => {
    const nearLeft = toPixels(view, { lat: 37.5665, lng: view.west });                                                  // x = 0
    expect(nearLeft.x).toBeCloseTo(0, 3);
    const edge = { lat: 37.5665, lng: view.west + (view.east - view.west) * (6 / 360) };                                   // 6 px from the left edge
    expect(edgeChips(view, [point("1", edge.lat, edge.lng)])).toHaveLength(1);
    const inside = { lat: 37.5665, lng: view.west + (view.east - view.west) * (60 / 360) };                                // 60 px inside
    expect(edgeChips(view, [point("1", inside.lat, inside.lng)])).toEqual([]);
  });

  it("shows up to eight chips (it was five: with many stops spread apart the farthest ones had no sign)", () => {
    const far = Array.from({ length: 10 }, (_, index) => point(String(index + 1), 37.5665 + 0.2 * (index % 2 ? 1 : -1), 126.7 + index * 0.06));
    expect(edgeChips(view, far).length).toBeGreaterThan(5);
    expect(edgeChips(view, far).length).toBeLessThanOrEqual(8);
  });
});


it("거리 칩의 표시 한도를 넘어도 모든 일정 번호가 합쳐져 남는다", () => {
  const view = { west: 126.9, east: 127.0, south: 37.5, north: 37.6, width: 375, height: 400, zoom: 12 };
  const points = Array.from({ length: 40 }, (_, i) => ({ id: String(i), title: "일정", date: "2026-10-01", time: "09:00", order: i + 1, coordinates: { lat: i % 2 ? 37.8 : 37.3, lng: 126.4 + i * .03 } }));
  const chips = edgeChips(view, points, { top: 64, bottom: 76, rightKeep: 64 });
  expect(new Set(chips.flatMap((chip) => chip.ids)).size).toBe(40);
  chips.forEach((chip, i) => chips.slice(i + 1).forEach((other) => expect(Math.abs(chip.y-other.y) >= 36 || Math.abs(chip.x-other.x) >= 158).toBe(true)));
});
