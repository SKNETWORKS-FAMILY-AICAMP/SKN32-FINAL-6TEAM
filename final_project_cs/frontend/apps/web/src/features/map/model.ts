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

export interface MapViewProps {
  points: MapPoint[];
  selectedId?: string;
  onSelect: (stopId: string) => void;
}

export interface MapController {
  update(points: MapPoint[], selectedId?: string): void;
  resize(): void;
  destroy(): void;
}

export interface MapAdapter {
  create(container: HTMLElement, options: MapViewProps & {
    onError: (error: Error) => void;
  }): Promise<MapController>;
}
