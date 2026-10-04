/** Provider-neutral WGS84 coordinates. Never infer these from a place label. */
export interface Coordinates {
  lat: number;
  lng: number;
}

/**
 * How a pin looks besides selected: `muted` — shown for context, not pressable (the other stops while one is being
 * changed); `current` — the stop being changed; `candidate` — a place it could change to.
 */
export type PinTone = "muted" | "current" | "candidate";

/** A pin's own label and look, by stop id (plan check's change screen: 「A · B · C」 candidates, the rest greyed). */
export interface PinLook { label?: string; tone?: PinTone }

export interface MapPoint {
  id: string;
  title: string;
  date: string;
  time: string;
  endTime?: string;
  /** One-based itinerary order for the selected date, including unlocated stops. */
  order: number;
  coordinates: Coordinates;
  /** Shown on the pin instead of `order`. */
  label?: string;
  tone?: PinTone;
}

/**
 * A route line between two stops (`GET /v1/web/trips/{id}/route-shapes`). `dashed` = the road was not known and the places were joined
 * by a straight line — drawn dashed and pale so it never reads as a real road.
 */
export interface MapLine {
  id: string;
  points: Coordinates[];
  dashed: boolean;
  /** Said to a screen reader and as the line's tooltip: 「A → B · 지하철」. */
  title: string;
}

export interface MapViewProps {
  points: MapPoint[];
  selectedId?: string;
  onSelect: (stopId: string) => void;
  /** Route lines under the pins; they never move the camera (the camera fits the pins). */
  lines?: MapLine[];
}

export interface MapController {
  update(points: MapPoint[], selectedId?: string, lines?: MapLine[]): void;
  resize(): void;
  destroy(): void;
}

export interface MapAdapter {
  create(container: HTMLElement, options: MapViewProps & {
    onError: (error: Error) => void;
  }): Promise<MapController>;
}
