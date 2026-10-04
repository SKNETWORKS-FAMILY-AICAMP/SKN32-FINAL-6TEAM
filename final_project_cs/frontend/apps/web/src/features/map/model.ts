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

/**
 * `[2026-10-05 사용자 지시]` Where the customer is (the browser's fix — only with their location consent): a blue dot, and a pale circle of
 * `accuracyM` metres when the browser says how sure it is. Never a pin: it takes no press and does not move the camera, except on a map with no pins.
 */
export interface MyLocation {
  coordinates: Coordinates;
  accuracyM: number | null;
}

/**
 * `[2026-10-05]` A place where the server found the customer stayed (`GET /v1/web/trips/{id}/location/stops`): a small grey dot. ★Called a "stay"
 * here so it is never mixed up with a stop of the plan (a pin). Only what the server gave is drawn — nothing is worked out on the page.
 */
export interface StayPoint {
  id: string;
  coordinates: Coordinates;
  /** Said to a screen reader and as the dot's tooltip: 「머문 곳 · 14:05–14:20」. */
  label: string;
}

export interface MapViewProps {
  points: MapPoint[];
  selectedId?: string;
  onSelect: (stopId: string) => void;
  /** Route lines under the pins; they never move the camera (the camera fits the pins). */
  lines?: MapLine[];
  /** `[2026-10-04]` Px at the top of the map that a bar floats over: the camera fits the pins below it and no pin is put under it. */
  topInset?: number;
  /** `[2026-10-05]` 「내 위치」 — null/absent: nothing is drawn. */
  me?: MyLocation | null;
  /** `[2026-10-05]` Where the server says the customer stayed — absent/empty: nothing is drawn. */
  stays?: StayPoint[];
  /** `[2026-10-05 사용자 지시]` The zoom level, said once the map is up and each time it changes - a screen asks for the detailed route lines when it is zoomed in (`use-route-detail.ts`). Keep it the same function between renders. */
  onZoom?: (zoom: number) => void;
}

export interface MapController {
  update(points: MapPoint[], selectedId?: string, lines?: MapLine[]): void;
  /**
   * `[2026-10-04 사용자 지시]` Back to the whole picture: the place and the zoom where every pin shows (what the map did when the pins first came).
   * ★`[2026-10-05]` Pins only — 「내 위치」 is left out (far away, it would shrink the pins to nothing). A map with no pins centres on 「내 위치」 instead.
   */
  fit(): void;
  /** `[2026-10-05 사용자 지시]` Draw, move or take away 「내 위치」. A map with no pins centres on it once (it never chases the customer). */
  setMe(me: MyLocation | null): void;
  /** `[2026-10-05]` Draw the places the server says the customer stayed (replaces what was there). */
  setStays(stays: StayPoint[]): void;
  resize(): void;
  destroy(): void;
}

export interface MapAdapter {
  create(container: HTMLElement, options: MapViewProps & {
    onError: (error: Error) => void;
  }): Promise<MapController>;
}
