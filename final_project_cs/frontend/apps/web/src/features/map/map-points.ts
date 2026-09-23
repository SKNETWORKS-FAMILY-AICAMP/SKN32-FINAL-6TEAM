import type { TripStop } from "../trip/model";
import type { Coordinates, MapPoint } from "./model";

export function hasValidCoordinates(value: Coordinates | null | undefined): value is Coordinates {
  return Boolean(value && Number.isFinite(value.lat) && Number.isFinite(value.lng)
    && value.lat >= -90 && value.lat <= 90 && value.lng >= -180 && value.lng <= 180);
}

export function toMapPoints(stops: TripStop[]): MapPoint[] {
  return stops.flatMap((stop, index) => hasValidCoordinates(stop.coordinates) ? [{
    id: stop.id,
    title: stop.title,
    date: stop.date,
    time: stop.time,
    endTime: stop.endTime,
    order: index + 1,
    coordinates: stop.coordinates,
  }] : []);
}
