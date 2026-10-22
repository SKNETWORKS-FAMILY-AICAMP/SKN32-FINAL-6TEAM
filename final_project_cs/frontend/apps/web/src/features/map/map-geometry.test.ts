import { describe, expect, it } from "vitest";
import { controlsLayout, locatePlace } from "./map-controls";
import { distanceM, edgeChips, formatDistance, metersPerPixel, niceScale, toPixels, type EdgeChip } from "./map-geometry";
import type { MapPoint, MapView } from "./model";

/** Seoul city hall at the middle of a 360 × 600 px view about 3.4 km wide. */
const view: MapView = { south: 37.5435, west: 126.9575, north: 37.5895, east: 126.9985, width: 360, height: 600, zoom: 13 };
const point = (id: string, lat: number, lng: number, order = Number(id), tone?: MapPoint["tone"]): MapPoint => ({ id, title: id, date: "", time: "", order, coordinates: { lat, lng }, tone });

type Box = { left: number; top: number; right: number; bottom: number };
// 일반 단추의150px 예약 폭과 좁은 공간 단추의44px 실제 폭을 지도 안으로 보정합니다.
const chipBox = (chip: EdgeChip, width: number): Box => {
  const half = chip.crowded ? 22 : 75;
  const x = Math.max(half, Math.min(width - half, chip.x));
  return { left: x - half, right: x + half, top: chip.y - 18, bottom: chip.y + 18 };
};

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

  it("keeps an inside coordinate under the bar as a normal pin, and ignores muted context", () => {
    const under = edgeChips(view, [point("1", 37.5885, 126.978)], { top: 64 });                       // inside the view but under the 64 px bar
    expect(under).toEqual([]);
    expect(edgeChips(view, [point("1", 37.7, 126.978, 1, "muted")])).toEqual([]);
  });

  it("keeps inside coordinates normal despite bottom placement space, but puts outside chips above it", () => {
    expect(edgeChips(view, [point("1", 37.5455, 126.978)], { bottom: 76 })).toEqual([]);
    const [chip] = edgeChips(view, [point("2", 37.53, 126.978)], { bottom: 76 });
    expect(chip.ids).toEqual(["2"]);
    expect(chip.y).toBeLessThanOrEqual(600 - 76);
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
  // `[2026-10-22 ST4F-721]` 「내 위치로」 stands apart at the bottom right: the group is ＋ − 「모든 일정 보기」 and leaves room above the sheet for it.
  it("leaves 「내 위치로」 its room above the sheet", () => {
    expect(controlsLayout({ width: 375, height: 364 }, 64, 3, 24)).toBe("column");                       // 64 + 12 + 44 + 3 × 52 + 12 + 8 + 44 + 24
    expect(controlsLayout({ width: 375, height: 363 }, 64, 3, 24)).toBe("row");                          // one px short: the column would reach the button
    expect(controlsLayout({ width: 375, height: 207 }, 64, 3, 24)).toBe("tab");                          // a row needs 64 + 44 + 24 + 8 + 44 + 24
  });
});

describe("locatePlace", () => {
  it("is the bottom right corner while it fits under the fold tab, and beside the tab on a low map", () => {
    expect(locatePlace({ width: 375, height: 392 }, 64, 24)).toBe("corner");
    expect(locatePlace({ width: 375, height: 208 }, 64, 24)).toBe("corner");                              // 64 + 12 + 44 + 8 + 44 + 12 + 24
    expect(locatePlace({ width: 375, height: 207 }, 64, 24)).toBe("beside");
    expect(locatePlace({ width: 375, height: 84 }, 64, 24)).toBe("beside");                               // the list opened all the way
    expect(locatePlace({ width: 0, height: 0 }, 64, 24)).toBe("corner");                                  // not measured yet
  });
});

describe("physical viewport bounds", () => {
  it.each([180, 320, 600])("공개 중 동서의 먼 일정은 실제 방향의 가장자리에 남는다 (%ipx)", height => {
    const chips = edgeChips({ ...view, height }, [point("1", 37.5665, 126.8), point("2", 37.5665, 127.15), { ...point("3", 37.5665, 126.978), revealFocus: true }], { top: 64, bottom: 76 });
    expect(chips).toHaveLength(2);
    expect(chips.find(chip => chip.ids.includes("1"))!.x).toBeLessThan(view.width / 2);
    expect(chips.find(chip => chip.ids.includes("2"))!.x).toBeGreaterThan(view.width / 2);
  });
  it.each([180, 320, 600])("공개 중 같은 서쪽의 이전 일정은 스택 하나로 남는다 (%ipx)", height => {
    const chips = edgeChips({ ...view, height }, [point("1", 37.5665, 126.8), point("2", 37.567, 126.801), { ...point("3", 37.5665, 126.978), revealFocus: true }], { top: 64, bottom: 76 });
    expect(chips).toHaveLength(1);
    expect(chips[0].ids).toEqual(["1", "2"]);
    expect(chips[0].labels).toEqual(["1", "2"]);
    expect(chips[0].x).toBeLessThan(view.width / 2);
  });
  it.each([2, 3, 4, 5, 20])("작은 지도에서 같은 방향의 이전 %i개 일정은 빠짐없이 기존 스택에 남는다", count => {
    const outside = Array.from({ length: count }, (_, i) => point(String(i + 1), 37.61 + i * .001, 126.978));
    const chips = edgeChips({ ...view, height: 180 }, [...outside, { ...point("focus", 37.5665, 126.978, count + 1), revealFocus: true }], { top: 64, bottom: 76 });
    expect(chips).toHaveLength(1);
    expect(chips[0].ids).toEqual(outside.map(p => p.id));
    expect(chips[0].distanceM).toBeCloseTo(distanceM({lat: 37.5665, lng: 126.978}, outside[0].coordinates));
  });
  it("같은 방향 스택은 지도 접기 단추를 피한다", () => {
    const obstacle = { left: 270, top: 64, right: 360, bottom: 110 };
    const outside = Array.from({ length: 5 }, (_, i) => point(String(i + 1), 37.61, 126.978));
    const chips = edgeChips({ ...view, height: 180 }, [...outside, { ...point("focus", 37.5665, 126.978, 6), revealFocus: true }], { top: 64, bottom: 76, obstacles: [obstacle] });
    expect(chips).toHaveLength(1);
    expect(chipBox(chips[0], view.width).right).toBeLessThanOrEqual(obstacle.left - 6);
  });
  it("동서남북의 이전 일정은 방향별 스택으로 남으며 현재 일정은 제외한다", () => {
    const outside = [point("1",37.5665,126.8),point("2",37.5665,126.81),point("3",37.5665,127.15),point("4",37.5665,127.16),
      point("5",37.7,126.978),point("6",37.71,126.978),point("7",37.4,126.978),point("8",37.39,126.978)];
    const chips=edgeChips(view,[...outside,{...point("focus",37.5665,126.978,9),revealFocus:true}],{top:64,bottom:76});
    expect(chips.map(chip=>chip.ids).sort()).toEqual([["1","2"],["3","4"],["5","6"],["7","8"]]);
    expect(new Set(chips.flatMap(chip=>chip.ids))).toEqual(new Set(outside.map(p=>p.id)));
  });
  it("같은 방향이라도 지도 안 일정은 스택에 포함하지 않는다", () => {
    const chips=edgeChips(view,[point("1",37.5665,view.west+.001),point("2",37.5665,126.8),point("3",37.5665,126.81),{...point("focus",37.5665,126.978,4),revealFocus:true}]);
    expect(chips.map(chip=>chip.ids)).toEqual([["2","3"]]);
  });
  it("낮은 지도의 첫 거리 버튼도 버리지 않고 거리·접기 단추 반대편에 둔다", () => {
    const [chip] = edgeChips({ ...view, height: 140 }, [point("1", 37.5665, 127.1)], { top: 64, bottom: 40, obstacles: [{ left: 270, top: 64, right: 360, bottom: 110 }] });
    expect(chip.ids).toEqual(["1"]);
    expect(chip.x + 75).toBeLessThan(270 - 6);
  });
  it("카메라가 도착하기 전 새 마커의 거리 표시도 앞선 마커와 합치지 않는다", () => {
    const chips = edgeChips(view, [point("1", 37.61, 126.978), { ...point("2", 37.612, 126.978), revealFocus: true }], { top: 64, bottom: 76 });
    expect(chips.map(chip => chip.ids).sort()).toEqual([["1"], ["2"]]);
  });
  it("keeps pins at the edge and within a few px inside as normal markers", () => {
    const nearLeft = toPixels(view, { lat: 37.5665, lng: view.west });                                                  // x = 0
    expect(nearLeft.x).toBeCloseTo(0, 3);
    const edge = { lat: 37.5665, lng: view.west + (view.east - view.west) * (6 / 360) };                                   // 6 px from the left edge
    expect(edgeChips(view, [point("1", edge.lat, edge.lng)])).toEqual([]);
    const inside = { lat: 37.5665, lng: view.west + (view.east - view.west) * (60 / 360) };                                // 60 px inside
    expect(edgeChips(view, [point("1", inside.lat, inside.lng)])).toEqual([]);
  });

  it("keeps all four viewport corners inside even with reserved placement space", () => {
    const corners = [
      point("1", view.north, view.west), point("2", view.north, view.east),
      point("3", view.south, view.west), point("4", view.south, view.east),
    ];
    expect(edgeChips(view, corners, { top: 64, bottom: 76, rightKeep: 64 })).toEqual([]);
  });

  it("groups only truly outside points when a nearby inside point shares their direction", () => {
    const chips = edgeChips(view, [point("1", 37.589, 126.978), point("2", 37.61, 126.978), point("3", 37.612, 126.978)], { top: 64, bottom: 76 });
    expect(chips).toHaveLength(1);
    expect(chips[0].ids).toEqual(["2", "3"]);
    expect(edgeChips(view, [point("4", 37.5665, view.west - 0.00001)])[0].ids).toEqual(["4"]);
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
