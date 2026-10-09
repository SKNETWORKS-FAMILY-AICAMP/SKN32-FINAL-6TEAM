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
export interface PinSlot { side: PinSide; push: number; dx?: number; dy?: number; group?: string }
const SIDES: readonly PinSide[] = ["ne", "nw", "se", "sw"];
/** How far a body may be pushed off its coordinate, tried in this order (px along each axis): the first push clears a body that stands on its coordinate (`PIN_BODY` + a little). */
const PUSHES = [0, 38, 76] as const;
/** Air kept between two bodies: none — two bodies may touch (four stops at one spot make a tidy flower of four), but not overlap. */
const GAP = 0;

interface Rect { left: number; top: number; right: number; bottom: number }

/** Where a body stands for a coordinate at (x, y) in the container, in the container's pixels. */
export function pinRect(x: number, y: number, slot: PinSlot): Rect {
  const east = slot.side === "ne" || slot.side === "se", north = slot.side === "ne" || slot.side === "nw";
  const left = (east ? x + slot.push : x - slot.push - PIN_BODY) + (slot.dx ?? 0);
  const top = (north ? y - slot.push - PIN_BODY : y + slot.push) + (slot.dy ?? 0);
  return { left, top, right: left + PIN_BODY, bottom: top + PIN_BODY };
}

/** The body may have been moved to any free slot; its small corner always faces the actual coordinate. */
export function pinFacing(rect: Rect, anchor: { x: number; y: number }): PinSide {
  const east = (rect.left + rect.right) / 2 >= anchor.x;
  const north = (rect.top + rect.bottom) / 2 <= anchor.y;
  return north ? east ? "ne" : "nw" : east ? "se" : "sw";
}

const overlap = (a: Rect, b: Rect, gap = 0) =>
  Math.max(0, Math.min(a.right + gap, b.right) - Math.max(a.left - gap, b.left)) * Math.max(0, Math.min(a.bottom + gap, b.bottom) - Math.max(a.top - gap, b.top));

/**
 * Which slot each pin takes. Pins are placed in the order of the day; each takes the first slot (the one it had, then upright-right, upright-left, below-right, below-left, then pushed
 * further out) that overlaps nothing already placed and stays inside the map below `top` (the bar over the map); when none is free, the one that overlaps least. Pure.
 */
export function layoutPins(points: readonly { id: string; x: number; y: number }[], area: { width: number; height: number; top?: number; bottom?: number; obstacles?: Rect[]; gap?: number }, previous: Readonly<Record<string, PinSlot>> = {}): Record<string, PinSlot> {
  const bounds: Rect = { left: 0, top: area.top ?? 0, right: area.width, bottom: area.height - (area.bottom ?? 0) };
  const placed: Rect[] = [...(area.obstacles ?? [])];
  const out: Record<string, PinSlot> = {};
  for (const point of points) {
    const candidates: PinSlot[] = [];
    // A pin keeps the side it had while that still overlaps nothing — but only a side on its coordinate: a pushed-off body goes back as soon as a side is free.
    const before = previous[point.id];
    if (before && before.push === 0 && !before.group) candidates.push(before);
    for (const push of PUSHES) for (const side of SIDES) candidates.push({ side, push });
    let best = candidates[0], bestCost = Infinity;
    for (const slot of candidates) {
      const rect = pinRect(point.x, point.y, slot);
      const outside = PIN_BODY * PIN_BODY - overlap(rect, bounds);
      const cost = placed.reduce((sum, other) => sum + overlap(rect, other, area.gap ?? GAP), 0) * 4 + outside * 2 + slot.push;
      if (cost < bestCost) { best = slot; bestCost = cost; }
      if (cost === slot.push) break;                       // nothing overlaps and it is inside the map: the first such slot wins
    }
    // SDK UI와 거리 칩까지 피한다. 네 모서리에 자리가 없으면 가장 가까운 빈 칸을 찾는다.
    if (bestCost > best.push) {
      let distance = Infinity;
      // 낮은 지도에서는 경계에서 4px를 더 비우면 실제 빈 상단 띠를 놓친다.
      for (let y = bounds.top; y + PIN_BODY <= bounds.bottom; y += PIN_BODY + 8) {
        for (let x = 4; x + PIN_BODY <= bounds.right - 4; x += PIN_BODY + 8) {
          const rect = { left: x, top: y, right: x + PIN_BODY, bottom: y + PIN_BODY };
          if (placed.some((other) => overlap(rect, other, 4) > 0)) continue;
          const d = Math.hypot(x - point.x, y - (point.y - PIN_BODY));
          if (d < distance) { distance = d; best = { side: "ne", push: 1, dx: x - point.x - 1, dy: y - point.y + PIN_BODY + 1 }; }
        }
      }
      if (!Number.isFinite(distance) && Object.keys(out).length) {
        const owner = Object.keys(out).filter((id) => !out[id].group).sort((a, b) => {
          const pa = points.find((entry) => entry.id === a)!, pb = points.find((entry) => entry.id === b)!;
          return Math.hypot(pa.x-point.x,pa.y-point.y)-Math.hypot(pb.x-point.x,pb.y-point.y);
        })[0];
        if (owner) { out[point.id] = { ...out[owner], group: owner }; continue; }
      }
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
export function createPin(point: MapPoint, detachLeader = false): HTMLDivElement {
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
  body.dataset.pinLabel = point.label ?? String(point.order);
  body.textContent = point.label ?? String(point.order);
  Object.assign(body.style, {
    position: "absolute", display: "grid", placeItems: "center", width: `${PIN_BODY}px`, height: `${PIN_BODY}px`, boxSizing: "border-box",
    border: "2px solid var(--color-text)", font: "700 14px/1 system-ui, sans-serif", boxShadow: `0 2px 8px ${shadow}`, cursor: "pointer", pointerEvents: "auto",
    transition: "transform .15s ease",
  });
  // ★`[2026-10-06 사용자 지적 — 점과 선이 핀 위에 막 찍혀 있다]` The line back to the coordinate and its dot belong UNDER every pin. Inside the pin's own marker they stack with that marker only (one pin's line crossed
  //   another pin's body), so a map that can (`detachLeader`) keeps them in a box of their own (`createPinLeader`) that it puts in a layer below all the pins.
  if (detachLeader) pin.append(body); else pin.append(leader, dot, body);
  (pin as PinWithLeader).pinLeader = detachLeader ? { leader, dot } : undefined;
  placePin(pin, { side: "ne", push: 0 });
  return pin;
}

type PinWithLeader = HTMLDivElement & { pinLeader?: { leader: SVGElement; dot: HTMLElement } };

/** The detached line + dot of a pin made with `createPinLeader`'s partner `createPin(point, true)`: a transparent box the same size as the pin's (`PIN_BOX`), centred on the coordinate like it. */
export function createPinLeader(pin: HTMLElement): HTMLDivElement {
  const parts = (pin as PinWithLeader).pinLeader;
  const box = document.createElement("div");
  Object.assign(box.style, { position: "relative", width: `${PIN_BOX}px`, height: `${PIN_BOX}px`, pointerEvents: "none", userSelect: "none" });
  if (parts) box.append(parts.leader, parts.dot);
  return box;
}

/** Stand the body in its slot: its tip corner (the small corner of the drop) at the coordinate, or pushed off it with a line back. */
export function placePin(pin: HTMLElement, slot: PinSlot, leaderBox?: HTMLElement) {
  const body = bodyOf(pin);
  const east = slot.side === "ne" || slot.side === "se", north = slot.side === "ne" || slot.side === "nw";
  const middle = PIN_BOX / 2;
  const left = (east ? middle + slot.push : middle - slot.push - PIN_BODY) + (slot.dx ?? 0);
  const top = (north ? middle - slot.push - PIN_BODY : middle + slot.push) + (slot.dy ?? 0);
  const facing = pinFacing({ left, top, right: left + PIN_BODY, bottom: top + PIN_BODY }, { x: middle, y: middle });
  const facesEast = facing === "ne" || facing === "se", facesNorth = facing === "ne" || facing === "nw";
  const tipX = facesEast ? left : left + PIN_BODY, tipY = facesNorth ? top + PIN_BODY : top;
  // The drop: three round corners and a small one where the coordinate is.
  body.style.left = `${left}px`;
  body.style.top = `${top}px`;
  body.style.borderRadius = facing === "ne" ? "50% 50% 50% 5px" : facing === "nw" ? "50% 50% 5px 50%" : facing === "se" ? "5px 50% 50% 50%" : "50% 5px 50% 50%";
  body.style.transformOrigin = `${facesEast ? "0%" : "100%"} ${facesNorth ? "100%" : "0%"}`;
  body.dataset.facing = facing;
  pin.dataset.side = slot.side;
  pin.dataset.push = String(slot.push);
  const own = (pin as PinWithLeader).pinLeader;
  const leader = (own?.leader ?? (leaderBox ?? pin).querySelector<SVGElement>("[data-pin-leader]"))!, dot = (own?.dot ?? (leaderBox ?? pin).querySelector<HTMLElement>("[data-pin-dot]"))!;
  body.style.visibility = slot.group ? "hidden" : "";
  pin.dataset.pinGroup = slot.group ?? "";
  const pushed = slot.push > 0 && !slot.group;
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
  body.style.background = selected ? "var(--color-selected)" : tone === "current" ? "var(--color-text)" : tone === "warn" ? "var(--color-warning-soft)" : "var(--color-surface)";
  body.style.color = selected || tone === "current" ? "var(--color-on-primary)" : tone === "candidate" ? "var(--color-success)" : tone === "warn" ? "var(--color-warning)" : "var(--color-text)";
  body.style.borderColor = selected ? "var(--color-selected)" : tone === "candidate" ? "var(--color-success)" : tone === "warn" ? "var(--color-warning)" : "var(--color-text)";
  body.style.boxShadow = selected ? `0 0 0 3px color-mix(in srgb, var(--color-selected) 35%, var(--color-surface)), 0 3px 12px ${shadow}` : `0 2px 8px ${shadow}`;
  body.style.transform = selected ? "scale(1.14)" : "none";
  body.style.pointerEvents = "auto";
}

/**
 * `[2026-10-05 사용자 선택 — 첫 지도 시점 안 C]` A day is shown whole, and its FIRST stop is pointed out once: its pin swells a little and a ring spreads from it, twice. Done with the browser's own
 * animation API so it needs no stylesheet; a screen that asks for less motion gets no animation.
 */
export function pulsePin(pin: HTMLElement) {
  if (typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const body = bodyOf(pin);
  if (!body || typeof body.animate !== "function") return;
  const ring = document.createElement("span");
  ring.dataset.pinPulse = "";
  Object.assign(ring.style, {
    position: "absolute", left: body.style.left, top: body.style.top, width: `${PIN_BODY}px`, height: `${PIN_BODY}px`, boxSizing: "border-box",
    border: "3px solid var(--color-selected)", borderRadius: "50%", pointerEvents: "none", opacity: "0",
  });
  pin.append(ring);
  const timing = { duration: 900, iterations: 2, easing: "ease-out" } as const;
  ring.animate([{ transform: "scale(1)", opacity: 0.85 }, { transform: "scale(2.3)", opacity: 0 }], timing).onfinish = () => ring.remove();
  body.animate([{ transform: body.style.transform || "none" }, { transform: "scale(1.22)" }, { transform: body.style.transform || "none" }], { ...timing, duration: 900 });
}

/**
 * `[2026-10-06 사용자 지시 — 새 마커가 생길 때 시선이 갈 시간을 주고 부드럽게]` A pin that has just appeared (a stop the check has just drawn) pops in: it grows from small with a little overshoot and fades in, over
 * about half a second, so the eye catches it. Done with the browser's own animation API; a screen that asks for less motion gets nothing.
 */
export function popPin(pin: HTMLElement) {
  if (typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const body = bodyOf(pin);
  if (!body || typeof body.animate !== "function") return;
  const rest = body.style.transform || "none";
  body.animate([{ transform: "scale(.2)", opacity: 0 }, { transform: "scale(1.22)", opacity: 1, offset: 0.6 }, { transform: rest === "none" ? "scale(1)" : rest, opacity: 1 }], { duration: 520, easing: "cubic-bezier(.2, .9, .3, 1)" });
}

/** Presentation-only updates must not reset the user's camera. */
export function geometryKey(points: MapPoint[]) {
  return JSON.stringify(points.map(({ id, coordinates }) => [id, coordinates.lat, coordinates.lng]));
}

/** 화면에 실제로 그려진 지도 도구와 거리 칩의 영역을 마커 배치에서 제외한다. */
export function pinArea(container: HTMLElement, options: { topInset?: number; bottomInset?: number }) {
  const box = container.getBoundingClientRect();
  const live = container.closest('[aria-label="여행 지도"]');
  const obstacles = [...(live?.querySelectorAll<HTMLElement>('[data-map-controls], [data-edge-chip]') ?? [])].map((node) => {
    const r = node.getBoundingClientRect();
    return { left: r.left - box.left - 6, top: r.top - box.top - 6, right: r.right - box.left + 6, bottom: r.bottom - box.top + 6 };
  });
  return { width: box.width, height: box.height, top: options.topInset ?? 0, bottom: options.bottomInset ?? 0, obstacles, gap: 4 };
}

/** 마커가 들어갈 빈 칸이 전부 차면 가까운 마커의 개수 표시로 합친다. 목록에는 모든 일정이 남는다. */
export function paintPinGroups(markers: readonly { id: string; pin: HTMLElement }[], slots: Record<string, PinSlot>) {
  for (const { id, pin } of markers) {
    const body = bodyOf(pin);
    const grouped = markers.filter((entry) => slots[entry.id]?.group === id);
    body.textContent = `${body.dataset.pinLabel ?? ""}${grouped.length ? `+${grouped.length}` : ""}`;
    body.style.fontSize = grouped.length ? "10px" : "14px";
    if (grouped.length) body.title = `함께 표시한 일정 ${[body.dataset.pinLabel, ...grouped.map((entry) => bodyOf(entry.pin).dataset.pinLabel)].join(" · ")} · 목록에서 각 일정을 선택할 수 있어요`;
    else body.removeAttribute("title");
  }
}
