import type { MapPoint } from "../model";

export function pointLabel(point: MapPoint) {
  const time = point.endTime ? `${point.time}–${point.endTime}` : point.time;
  return `${point.order}. ${point.title} · ${point.date} ${time}`;
}

/** Pins live in the page, so they take the theme's roles (`styles/tokens.css`) like any other element. */
const shadow = "color-mix(in srgb, var(--color-text) 25%, transparent)";

export function createPin(point: MapPoint): HTMLDivElement {
  const pin = document.createElement("div");
  pin.textContent = String(point.order);
  pin.title = pointLabel(point);
  Object.assign(pin.style, {
    display: "grid", placeItems: "center", width: "44px", height: "44px",
    borderRadius: "50% 50% 50% 6px", border: "3px solid var(--color-surface)",
    font: "700 15px/1 system-ui, sans-serif", boxShadow: `0 2px 10px ${shadow}`,
    cursor: "pointer", boxSizing: "border-box", userSelect: "none",
  });
  return pin;
}

export function setPinSelected(pin: HTMLElement, selected: boolean) {
  pin.style.background = selected ? "var(--color-selected)" : "var(--color-soft)";
  pin.style.color = selected ? "var(--color-on-primary)" : "var(--color-text)";
  pin.style.boxShadow = selected ? `0 0 0 3px color-mix(in srgb, var(--color-selected) 45%, var(--color-surface)), 0 3px 12px ${shadow}` : `0 2px 10px ${shadow}`;
}

/** Presentation-only updates must not reset the user's camera. */
export function geometryKey(points: MapPoint[]) {
  return JSON.stringify(points.map(({ id, coordinates }) => [id, coordinates.lat, coordinates.lng]));
}
