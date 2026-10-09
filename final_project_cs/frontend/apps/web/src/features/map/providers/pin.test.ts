import { describe, expect, it } from "vitest";
import { layoutPins, PIN_BODY, pinRect, pinFacing, type PinSlot } from "./pin";

const AREA = { width: 402, height: 220, top: 64 };

it("낮은 지도에서 단추와 거리 칩 사이의 빈 상단 띠도 사용한다", () => {
  const points = [{ id: "selected", x: 104, y: 110 }];
  const obstacles = [{ left: 132, top: 70, right: 365, bottom: 122 }, { left: -6, top: 103, right: 111, bottom: 149 }];
  const slots = layoutPins(points, { width: 375, height: 212, top: 64, bottom: 76, obstacles, gap: 4 });
  const rect = pinRect(104, 110, slots.selected);
  expect(rect.top).toBeGreaterThanOrEqual(64);
  expect(rect.bottom).toBeLessThanOrEqual(99);
  expect(rect.right).toBeLessThanOrEqual(128);
});
const rects = (points: { id: string; x: number; y: number }[], slots: Record<string, PinSlot>) => points.map((point) => pinRect(point.x, point.y, slots[point.id]));
const overlaps = (a: ReturnType<typeof pinRect>, b: ReturnType<typeof pinRect>) =>
  Math.min(a.right, b.right) > Math.max(a.left, b.left) && Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top);

it("지도 안의 메뉴 아래·하단·가장자리 좌표는 개별 몸통으로 빈 곳에 배치한다", () => {
  const points = [{ id: "top", x: 180, y: 8 }, { id: "near", x: 181, y: 9 }, { id: "bottom", x: 180, y: 296 }, { id: "left", x: 2, y: 150 }, { id: "right", x: 373, y: 150 }];
  const area = { width: 375, height: 300, top: 64, bottom: 76, gap: 4 };
  const slots = layoutPins(points, area);
  const bodies = rects(points, slots);
  points.forEach((point, i) => {
    expect(slots[point.id].group).toBeUndefined();
    const body = bodies[i];
    expect(body.left).toBeGreaterThanOrEqual(0); expect(body.right).toBeLessThanOrEqual(375);
    expect(body.top).toBeGreaterThanOrEqual(64); expect(body.bottom).toBeLessThanOrEqual(224);
    bodies.slice(i+1).forEach((other) => expect(overlaps(body, other)).toBe(false));
  });
  expect(slots.top.push).toBeGreaterThan(0); expect(slots.bottom.push).toBeGreaterThan(0);
});

describe("where a numbered pin stands beside its coordinate", () => {
  it("puts the body up and to the right of the coordinate when nothing is near (the tip of the drop is the coordinate)", () => {
    const slots = layoutPins([{ id: "a", x: 200, y: 150 }], AREA);
    expect(slots.a).toEqual({ side: "ne", push: 0 });
    expect(pinRect(200, 150, slots.a)).toEqual({ left: 200, top: 150 - PIN_BODY, right: 200 + PIN_BODY, bottom: 150 });
  });

  it("turns a pin to another side of its coordinate when it would overlap one already placed — no two bodies overlap when a side is free", () => {
    const points = [{ id: "a", x: 200, y: 150 }, { id: "b", x: 212, y: 146 }, { id: "c", x: 190, y: 156 }];
    const slots = layoutPins(points, AREA);
    expect(new Set(Object.values(slots).map((slot) => slot.side)).size).toBeGreaterThan(1);
    const placed = rects(points, slots);
    placed.forEach((one, at) => placed.slice(at + 1).forEach((other) => expect(overlaps(one, other)).toBe(false)));
  });

  it("pushes a body off its coordinate (with a line back to it) only when every side is taken", () => {
    const stack = Array.from({ length: 6 }, (_, at) => ({ id: `p${at}`, x: 200, y: 150 }));      // six stops at the very same spot: four sides, then two pushed out
    const slots = layoutPins(stack, AREA);
    const pushed = Object.values(slots).filter((slot) => slot.push > 0);
    expect(pushed.length).toBeGreaterThan(0);
    expect(Object.values(slots).slice(0, 4).every((slot) => slot.push === 0)).toBe(true);        // the first four take the four sides
    const placed = rects(stack, slots);
    placed.forEach((one, at) => placed.slice(at + 1).forEach((other) => expect(overlaps(one, other)).toBe(false)));
  });

  it("keeps a pin where it was while that still overlaps nothing — it does not flip each time the map moves", () => {
    const points = [{ id: "a", x: 200, y: 150 }, { id: "b", x: 212, y: 146 }];
    const first = layoutPins(points, AREA);
    expect(layoutPins(points, AREA, first)).toEqual(first);
    expect(layoutPins(points.map((point) => ({ ...point, x: point.x + 3 })), AREA, first)).toEqual(first);
  });

  it("brings a pushed-off pin back onto its coordinate once a side is free again", () => {
    const stack = Array.from({ length: 6 }, (_, at) => ({ id: `p${at}`, x: 200, y: 150 }));
    const crowded = layoutPins(stack, AREA);
    expect(Object.values(crowded).some((slot) => slot.push > 0)).toBe(true);
    const spread = layoutPins(stack.map((point, at) => ({ ...point, x: 40 + at * 60 })), AREA, crowded);            // the map was zoomed in: the stops are far apart now
    expect(Object.values(spread).every((slot) => slot.push === 0)).toBe(true);
  });

  it("keeps the bodies inside the map and out from under the bar over its top", () => {
    const slots = layoutPins([{ id: "a", x: 390, y: 70 }], AREA);                               // near the top-right corner
    const body = pinRect(390, 70, slots.a);
    expect(body.top).toBeGreaterThanOrEqual(AREA.top - 1);
    expect(body.right).toBeLessThanOrEqual(AREA.width + 1);
    expect(slots.a.side).toBe("sw");                                                            // below and to the left of the coordinate: the only side that is inside
  });
});


describe("지도 도구와 밀집된 마커", () => {
  it("거리 칩과 지도 단추를 피하고 빈 자리가 없으면 마커를 묶는다", () => {
    const obstacles = [{ left: 240, top: 64, right: 360, bottom: 190 }];
    const points = Array.from({ length: 40 }, (_, i) => ({ id: String(i), x: 250, y: 110 }));
    const slots = layoutPins(points, { width: 375, height: 240, top: 64, bottom: 40, obstacles, gap: 4 });
    const bodies = points.filter((point) => !slots[point.id].group).map((point) => pinRect(point.x, point.y, slots[point.id]));
    expect(Object.values(slots).some((slot) => slot.group)).toBe(true);
    expect(Object.keys(slots)).toHaveLength(40);
    bodies.forEach((body, i) => {
      expect(body.top).toBeGreaterThanOrEqual(64); expect(body.bottom).toBeLessThanOrEqual(200);
      obstacles.forEach((obstacle) => expect(overlaps(body, obstacle)).toBe(false));
      bodies.slice(i+1).forEach((other) => expect(overlaps(body, other)).toBe(false));
    });
  });
});

// A displaced marker can cross to the opposite side of its original slot.
it.each([
  ["ne", { left: 80, top: 10, right: 114, bottom: 44 }],
  ["nw", { left: 10, top: 10, right: 44, bottom: 44 }],
  ["se", { left: 80, top: 80, right: 114, bottom: 114 }],
  ["sw", { left: 10, top: 80, right: 44, bottom: 114 }],
] as const)("옮긴 마커 %s의 모서리는 실제 좌표를 향한다", (side, rect) => {
  expect(pinFacing(rect, { x: 60, y: 60 })).toBe(side);
});
