import type { MapPoint } from "../model";

export function pointLabel(point: MapPoint) {
  const time = point.endTime ? `${point.time}–${point.endTime}` : point.time;
  return `${point.order}. ${point.title} · ${point.date} ${time}`;
}

export function createPin(point: MapPoint): HTMLDivElement {
  const pin = document.createElement("div");
  pin.textContent = String(point.order);
  pin.title = pointLabel(point);
  Object.assign(pin.style, {
    display: "grid", placeItems: "center", width: "44px", height: "44px",
    borderRadius: "50% 50% 50% 6px", border: "3px solid #fff",
    font: "700 15px/1 system-ui, sans-serif", boxShadow: "0 2px 10px #1c312940",
    cursor: "pointer", boxSizing: "border-box", userSelect: "none",
  });
  return pin;
}

export function setPinSelected(pin: HTMLElement, selected: boolean) {
  pin.style.background = selected ? "#203f35" : "#f2f7f3";
  pin.style.color = selected ? "#ffffff" : "#203f35";
  pin.style.boxShadow = selected ? "0 0 0 3px #8eb4a2, 0 3px 12px #1c312940" : "0 2px 10px #1c312940";
}

/** Presentation-only updates must not reset the user's camera. */
export function geometryKey(points: MapPoint[]) {
  return JSON.stringify(points.map(({ id, coordinates }) => [id, coordinates.lat, coordinates.lng]));
}
