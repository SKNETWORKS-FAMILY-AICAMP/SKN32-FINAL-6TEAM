/** Provider-neutral WGS84 coordinates. Never infer these from a place label. */
export interface Coordinates {
  lat: number;
  lng: number;
}

export interface MapPoint {
  id: string;
  title: string;
  date: string;
  time: string;
  endTime?: string;
  /** One-based itinerary order for the selected date, including unlocated stops. */
  order: number;
  coordinates: Coordinates;
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
