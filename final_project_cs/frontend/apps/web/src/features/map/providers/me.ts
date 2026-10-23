import type { MyLocation, StayPoint } from "../model";

/**
 * `[2026-10-05 사용자 지시]` 「내 위치」 on a map, the same for the three providers.
 * - A small blue dot with a white ring — round and without a number, so it never reads as a stop (a stop is a numbered drop, `pin.ts`).
 * - When the browser says how sure it is, a pale circle of that radius. ★A circle wider than `ACCURACY_CIRCLE_MAX_M` is left out (it would cover the
 *   day's map and say nothing); the dot still shows.
 * - ★It never takes a press (`pointer-events: none`) and stands under the pins, so a pin next to it stays pressable.
 * - Its name for a screen reader is 「내 위치」 (`role="img"`).
 * - ★A position is personal data: it is not written into the page (no coordinates in attributes or text) — only where the dot is drawn.
 *
 * The places the server says the customer stayed (`StayPoint`) are smaller grey dots, under 「내 위치」.
 */
export const ME_LABEL = "내 위치";
/** The dot (px) and the box around it (room for the ring's shadow; the coordinate is at the box's middle). */
export const ME_DOT = 16;
export const ME_BOX = 28;
export const STAY_DOT = 10;
export const STAY_BOX = 18;
export const ACCURACY_CIRCLE_MAX_M = 500;
/** The usual "you are here" blue. An SDK paints its circle itself and cannot take a CSS variable, hence a plain colour; the dot takes the theme's when it has one. */
export const ME_BLUE = "#1a73e8";
export const STAY_GREY = "#80868b";

/** The accuracy circle's radius in metres, or null when there is none to draw (unknown, nonsense, or wider than 500 m). */
export function accuracyRadius(me: MyLocation | null): number | null {
  const value = me?.accuracyM;
  return typeof value === "number" && Number.isFinite(value) && value > 0 && value <= ACCURACY_CIRCLE_MAX_M ? value : null;
}

/** Same position and same circle: nothing to redraw. */
export function meKey(me: MyLocation | null): string {
  return me ? `${me.coordinates.lat},${me.coordinates.lng},${accuracyRadius(me) ?? "-"}` : "";
}

export function staysKey(stays: StayPoint[]): string {
  return JSON.stringify(stays.map(({ id, coordinates, label }) => [id, coordinates.lat, coordinates.lng, label]));
}

function box(size: number): HTMLDivElement {
  const element = document.createElement("div");
  Object.assign(element.style, { position: "relative", width: `${size}px`, height: `${size}px`, pointerEvents: "none", userSelect: "none" });
  return element;
}

/** The marker's element for 「내 위치」: a transparent `ME_BOX` square with the coordinate at its middle and the dot on it. */
export function createMeDot(): HTMLDivElement {
  const element = box(ME_BOX);
  element.dataset.myLocation = "";
  element.setAttribute("role", "img");
  element.setAttribute("aria-label", ME_LABEL);
  element.title = ME_LABEL;
  const dot = document.createElement("span");
  Object.assign(dot.style, {
    position: "absolute", left: `${(ME_BOX - ME_DOT) / 2}px`, top: `${(ME_BOX - ME_DOT) / 2}px`, width: `${ME_DOT}px`, height: `${ME_DOT}px`, boxSizing: "border-box",
    borderRadius: "50%", border: "3px solid #fff", background: `var(--color-my-location, ${ME_BLUE})`,
    boxShadow: "0 0 0 1px color-mix(in srgb, #000 18%, transparent), 0 1px 4px color-mix(in srgb, #000 30%, transparent)", pointerEvents: "none",
  });
  element.append(dot);
  return element;
}

/** The marker's element for a place the customer stayed: a small grey dot named by `label`. */
export function createStayDot(stay: StayPoint): HTMLDivElement {
  const element = box(STAY_BOX);
  element.dataset.stayPoint = "";
  element.setAttribute("role", "img");
  element.setAttribute("aria-label", stay.label);
  element.title = stay.label;
  const dot = document.createElement("span");
  Object.assign(dot.style, {
    position: "absolute", left: `${(STAY_BOX - STAY_DOT) / 2}px`, top: `${(STAY_BOX - STAY_DOT) / 2}px`, width: `${STAY_DOT}px`, height: `${STAY_DOT}px`, boxSizing: "border-box",
    borderRadius: "50%", border: "2px solid #fff", background: STAY_GREY, boxShadow: "0 0 0 1px color-mix(in srgb, #000 15%, transparent)", pointerEvents: "none",
  });
  element.append(dot);
  return element;
}

/** How the accuracy circle is painted (all three providers). */
export const ACCURACY_STYLE = { color: ME_BLUE, weight: 1, opacity: 0.45, fillOpacity: 0.12 } as const;
