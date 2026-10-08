import { describe, expect, it } from "vitest";
import { layoutPins, PIN_BODY, pinRect, type PinSlot } from "./pin";

const AREA = { width: 402, height: 220, top: 64 };
const rects = (points: { id: string; x: number; y: number }[], slots: Record<string, PinSlot>) => points.map((point) => pinRect(point.x, point.y, slots[point.id]));
const overlaps = (a: ReturnType<typeof pinRect>, b: ReturnType<typeof pinRect>) =>
  Math.min(a.right, b.right) > Math.max(a.left, b.left) && Math.min(a.bottom, b.bottom) > Math.max(a.top, b.top);

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
