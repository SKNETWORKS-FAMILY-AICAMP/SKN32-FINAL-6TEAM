import type { MapPoint } from "../model";

export function pointLabel(point: MapPoint) {
  const time = point.endTime ? `${point.time}–${point.endTime}` : point.time;
  const when = [point.date, time].filter(Boolean).join(" ");
  return `${point.label ?? point.order}. ${point.title}${when ? ` · ${when}` : ""}`;
}

/**
 * ★`[2026-10-04 사용자 지시 · 코덱스 의견]` 핀 겹침. 핀은 목업처럼 작은 번호 물방울(34px, 흰 바탕에 짙은 테두리)이고, 그 꼭짓점이 장소의 좌표에 닿는다.
 * 서울 도심의 일정은 한 지점 300m 안에 모이는 일이 흔해서 핀끼리 포개지므로, 핀마다 **꼭짓점이 어느 모서리인지**(`side`: 몸통이 좌표의 오른쪽 위 · 왼쪽 위 · 오른쪽 아래 ·
 * 왼쪽 아래)를 화면 좌표에서 겹침이 가장 적게 골라 준다(숫자는 늘 바로 서 있다). 네 방향으로도 겹치면 몸통을 대각선으로 조금 밀고(`push`) 좌표까지 가는 선을 긋는다.
 */
export const PIN_BODY = 34;
/** The marker's box: transparent, with the stop's coordinate at its middle; the body stands in one of its four quarters. */
export const PIN_BOX = PIN_BODY * 2 + 32;

export type PinSide = "ne" | "nw" | "se" | "sw";
export interface PinSlot { side: PinSide; push: number }
const SIDES: readonly PinSide[] = ["ne", "nw", "se", "sw"];
/** How far a body may be pushed off its coordinate, tried in this order (px along each axis): the first push clears a body that stands on its coordinate (`PIN_BODY` + a little). */
const PUSHES = [0, 38, 76] as const;
/** Air kept between two bodies: none — two bodies may touch (four stops at one spot make a tidy flower of four), but not overlap. */
const GAP = 0;

interface Rect { left: number; top: number; right: number; bottom: number }

/** Where a body stands for a coordinate at (x, y) in the container, in the container's pixels. */
export function pinRect(x: number, y: number, slot: PinSlot): Rect {
  const east = slot.side === "ne" || slot.side === "se", north = slot.side === "ne" || slot.side === "nw";
  const left = east ? x + slot.push : x - slot.push - PIN_BODY;
  const top = north ? y - slot.push - PIN_BODY : y + slot.push;
  return { left, top, right: left + PIN_BODY, bottom: top + PIN_BODY };
}

const overlap = (a: Rect, b: Rect, gap = 0) =>
  Math.max(0, Math.min(a.right + gap, b.right) - Math.max(a.left - gap, b.left)) * Math.max(0, Math.min(a.bottom + gap, b.bottom) - Math.max(a.top - gap, b.top));

/**
 * Which slot each pin takes. Pins are placed in the order of the day; each takes the first slot (the one it had, then upright-right, upright-left, below-right, below-left, then pushed
 * further out) that overlaps nothing already placed and stays inside the map below `top` (the bar over the map); when none is free, the one that overlaps least. Pure.
 */
export function layoutPins(points: readonly { id: string; x: number; y: number }[], area: { width: number; height: number; top?: number }, previous: Readonly<Record<string, PinSlot>> = {}): Record<string, PinSlot> {
  const bounds: Rect = { left: 0, top: area.top ?? 0, right: area.width, bottom: area.height };
  const placed: Rect[] = [];
  const out: Record<string, PinSlot> = {};
  for (const point of points) {
    const candidates: PinSlot[] = [];
    // A pin keeps the side it had while that still overlaps nothing — but only a side on its coordinate: a pushed-off body goes back as soon as a side is free.
    const before = previous[point.id];
    if (before && before.push === 0) candidates.push(before);
    for (const push of PUSHES) for (const side of SIDES) candidates.push({ side, push });
    let best = candidates[0], bestCost = Infinity;
    for (const slot of candidates) {
      const rect = pinRect(point.x, point.y, slot);
      const outside = PIN_BODY * PIN_BODY - overlap(rect, bounds);
      const cost = placed.reduce((sum, other) => sum + overlap(rect, other, GAP), 0) * 4 + outside * 2 + slot.push;
      if (cost < bestCost) { best = slot; bestCost = cost; }
      if (cost === slot.push) break;                       // nothing overlaps and it is inside the map: the first such slot wins
    }
    out[point.id] = best;
    placed.push(pinRect(point.x, point.y, best));
  }
  return out;
}

/** Pins live in the page, so they take the theme's roles (`styles/tokens.css`) like any other element. */
const shadow = "color-mix(in srgb, var(--color-text) 25%, transparent)";
const SVG = "http://www.w3.org/2000/svg";

const bodyOf = (pin: HTMLElement) => pin.querySelector<HTMLElement>("[data-pin-body]")!;

/**
 * The marker's element: a transparent box with the coordinate at its middle (`PIN_BOX` square), holding the numbered body and a thin line to the coordinate for a body that had
 * to be pushed away. Only the body takes presses — the box leaves the map under it draggable.
 */
export function createPin(point: MapPoint): HTMLDivElement {
  const pin = document.createElement("div");
  pin.title = pointLabel(point);
  if (point.tone) pin.dataset.tone = point.tone;
  Object.assign(pin.style, { position: "relative", width: `${PIN_BOX}px`, height: `${PIN_BOX}px`, pointerEvents: "none", userSelect: "none" });
  const leader = document.createElementNS(SVG, "svg");
  leader.dataset.pinLeader = "";
  leader.setAttribute("width", String(PIN_BOX));
  leader.setAttribute("height", String(PIN_BOX));
  Object.assign(leader.style, { position: "absolute", inset: "0", overflow: "visible", pointerEvents: "none", display: "none" });
  const line = document.createElementNS(SVG, "line");
  line.setAttribute("stroke", "var(--color-text)");
  line.setAttribute("stroke-width", "1.5");
  line.setAttribute("stroke-linecap", "round");
  leader.append(line);
  const dot = document.createElement("span");
  dot.dataset.pinDot = "";
  Object.assign(dot.style, { position: "absolute", left: `${PIN_BOX / 2 - 3}px`, top: `${PIN_BOX / 2 - 3}px`, width: "6px", height: "6px", borderRadius: "50%", background: "var(--color-text)", display: "none", pointerEvents: "none" });
  const body = document.createElement("div");
  body.dataset.pinBody = "";
  body.textContent = point.label ?? String(point.order);
  Object.assign(body.style, {
    position: "absolute", display: "grid", placeItems: "center", width: `${PIN_BODY}px`, height: `${PIN_BODY}px`, boxSizing: "border-box",
    border: "2px solid var(--color-text)", font: "700 14px/1 system-ui, sans-serif", boxShadow: `0 2px 8px ${shadow}`, cursor: "pointer", pointerEvents: "auto",
    transition: "transform .15s ease",
  });
  pin.append(leader, dot, body);
  placePin(pin, { side: "ne", push: 0 });
  return pin;
}

/** Stand the body in its slot: its tip corner (the small corner of the drop) at the coordinate, or pushed off it with a line back. */
export function placePin(pin: HTMLElement, slot: PinSlot) {
  const body = bodyOf(pin);
  const east = slot.side === "ne" || slot.side === "se", north = slot.side === "ne" || slot.side === "nw";
  const middle = PIN_BOX / 2;
  const left = east ? middle + slot.push : middle - slot.push - PIN_BODY;
  const top = north ? middle - slot.push - PIN_BODY : middle + slot.push;
  const tipX = east ? left : left + PIN_BODY, tipY = north ? top + PIN_BODY : top;
  // The drop: three round corners and a small one where the coordinate is.
  body.style.left = `${left}px`;
  body.style.top = `${top}px`;
  body.style.borderRadius = slot.side === "ne" ? "50% 50% 50% 5px" : slot.side === "nw" ? "50% 50% 5px 50%" : slot.side === "se" ? "5px 50% 50% 50%" : "50% 5px 50% 50%";
  body.style.transformOrigin = `${east ? "0%" : "100%"} ${north ? "100%" : "0%"}`;
  pin.dataset.side = slot.side;
  pin.dataset.push = String(slot.push);
  const leader = pin.querySelector<SVGElement>("[data-pin-leader]")!, dot = pin.querySelector<HTMLElement>("[data-pin-dot]")!;
  const pushed = slot.push > 0;
  leader.style.display = dot.style.display = pushed ? "" : "none";
  if (pushed) {
    const line = leader.firstElementChild!;
    line.setAttribute("x1", String(middle)); line.setAttribute("y1", String(middle));
    line.setAttribute("x2", String(tipX)); line.setAttribute("y2", String(tipY));
  }
}

export function setPinSelected(pin: HTMLElement, selected: boolean) {
  const tone = pin.dataset.tone;
  const body = bodyOf(pin);
  // A muted pin is context only: it never takes the selection and is not pressed.
  if (tone === "muted") {
    Object.assign(body.style, { background: "var(--color-subtle)", color: "var(--color-faint)", borderColor: "var(--color-border-strong)", boxShadow: "none", pointerEvents: "none", transform: "none" });
    return;
  }
  body.style.background = selected ? "var(--color-selected)" : tone === "current" ? "var(--color-text)" : "var(--color-surface)";
  body.style.color = selected || tone === "current" ? "var(--color-on-primary)" : tone === "candidate" ? "var(--color-success)" : "var(--color-text)";
  body.style.borderColor = selected ? "var(--color-selected)" : tone === "candidate" ? "var(--color-success)" : "var(--color-text)";
  body.style.boxShadow = selected ? `0 0 0 3px color-mix(in srgb, var(--color-selected) 35%, var(--color-surface)), 0 3px 12px ${shadow}` : `0 2px 8px ${shadow}`;
  body.style.transform = selected ? "scale(1.14)" : "none";
  body.style.pointerEvents = "auto";
}

/** Presentation-only updates must not reset the user's camera. */
export function geometryKey(points: MapPoint[]) {
  return JSON.stringify(points.map(({ id, coordinates }) => [id, coordinates.lat, coordinates.lng]));
}
