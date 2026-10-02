import type { MapPoint } from "../model";

export function pointLabel(point: MapPoint) {
  const time = point.endTime ? `${point.time}–${point.endTime}` : point.time;
  const when = [point.date, time].filter(Boolean).join(" ");
  return `${point.label ?? point.order}. ${point.title}${when ? ` · ${when}` : ""}`;
}

/** Pins live in the page, so they take the theme's roles (`styles/tokens.css`) like any other element. */
const shadow = "color-mix(in srgb, var(--color-text) 25%, transparent)";

export function createPin(point: MapPoint): HTMLDivElement {
  const pin = document.createElement("div");
  pin.textContent = point.label ?? String(point.order);
  pin.title = pointLabel(point);
  if (point.tone) pin.dataset.tone = point.tone;
  Object.assign(pin.style, {
    display: "grid", placeItems: "center", width: "44px", height: "44px",
    borderRadius: "50% 50% 50% 6px", border: "3px solid var(--color-surface)",
    font: "700 15px/1 system-ui, sans-serif", boxShadow: `0 2px 10px ${shadow}`,
    cursor: "pointer", boxSizing: "border-box", userSelect: "none",
  });
  return pin;
}

export function setPinSelected(pin: HTMLElement, selected: boolean) {
  const tone = pin.dataset.tone;
  // A muted pin is context only: it never takes the selection and is not pressed.
  if (tone === "muted") {
    Object.assign(pin.style, { background: "var(--color-subtle)", color: "var(--color-faint)", borderColor: "var(--color-border-strong)", boxShadow: "none", pointerEvents: "none" });
    return;
  }
  pin.style.background = selected ? "var(--color-selected)" : tone === "current" ? "var(--color-text)" : tone === "candidate" ? "var(--color-surface)" : "var(--color-soft)";
  pin.style.color = selected || tone === "current" ? "var(--color-on-primary)" : tone === "candidate" ? "var(--color-success)" : "var(--color-text)";
  pin.style.borderColor = selected ? "var(--color-surface)" : tone === "candidate" ? "var(--color-success)" : "var(--color-surface)";
  pin.style.boxShadow = selected ? `0 0 0 3px color-mix(in srgb, var(--color-selected) 45%, var(--color-surface)), 0 3px 12px ${shadow}` : `0 2px 10px ${shadow}`;
}

/** Presentation-only updates must not reset the user's camera. */
export function geometryKey(points: MapPoint[]) {
  return JSON.stringify(points.map(({ id, coordinates }) => [id, coordinates.lat, coordinates.lng]));
}
