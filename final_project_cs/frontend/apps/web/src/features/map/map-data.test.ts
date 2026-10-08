import { describe, expect, it } from "vitest";
import type { TripStop } from "../trip/model";
import { resolveMapConfiguration } from "./config";
import { hasValidCoordinates, toMapPoints } from "./map-points";

describe("map provider selection", () => {
  it("needs only the selected provider's settings; an unset provider is the free map", () => {
    expect(resolveMapConfiguration({})).toEqual({ provider: "osm", tileUrl: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" });
    expect(resolveMapConfiguration({ provider: "naver", naverClientId: " web-id " })).toEqual({ provider: "naver", clientId: "web-id" });
    expect(resolveMapConfiguration({ provider: "google", googleApiKey: "web-key", googleMapId: "map-id" }))
      .toEqual({ provider: "google", apiKey: "web-key", mapId: "map-id", tileUrl: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" });
    expect(resolveMapConfiguration({ provider: "osm" })).toEqual({ provider: "osm", tileUrl: "https://tile.openstreetmap.org/{z}/{x}/{y}.png" });
    expect(resolveMapConfiguration({ provider: "osm", osmTileUrl: " https://tiles.example.org/{z}/{x}/{y}.png " }))
      .toEqual({ provider: "osm", tileUrl: "https://tiles.example.org/{z}/{x}/{y}.png" });
  });

  it("accepts a tile server on this machine over http — a developer's or a test run's own tiles, never OpenStreetMap's", () => {
    expect(resolveMapConfiguration({ provider: "osm", osmTileUrl: "http://127.0.0.1:8043/__test/tile/{z}/{x}/{y}.png" }))
      .toEqual({ provider: "osm", tileUrl: "http://127.0.0.1:8043/__test/tile/{z}/{x}/{y}.png" });
    expect(resolveMapConfiguration({ provider: "osm", osmTileUrl: "http://localhost:9000/{z}/{x}/{y}.png" }).provider).toBe("osm");
    expect(resolveMapConfiguration({ provider: "osm", osmTileUrl: "http://127.0.0.1.example.org/{z}/{x}/{y}.png" }).provider).toBe("unavailable");
  });

  it.each([
    "http://tile.openstreetmap.org/{z}/{x}/{y}.png",   // ★the OSM tile policy forbids http
    "https://tile.openstreetmap.org/tiles.png",        // no {z}/{x}/{y}: every tile would be the same image
  ])("refuses a free-map tile address that breaks the tile policy or cannot draw a map: %s", (osmTileUrl) => {
    expect(resolveMapConfiguration({ provider: "osm", osmTileUrl }).provider).toBe("unavailable");
    expect(resolveMapConfiguration({ provider: "google", googleApiKey: "k", googleMapId: "m", osmTileUrl }).provider).toBe("unavailable");
  });

  it.each([
    { provider: "naver", googleApiKey: "not-a-naver-key" },
    { provider: "google", googleApiKey: "key-with-no-map-id" },
    { provider: "google", googleMapId: "id-with-no-key" },
    { provider: "misspelled-provider" },
    { provider: "demo" },                              // ★the diagram stand-in is gone: the old value is a setting error, not a made-up map
  ])("does not silently replace invalid configuration with another map: %o", (config) => {
    expect(resolveMapConfiguration(config).provider).toBe("unavailable");
  });
});

const stop = (id: string, time: string, title: string, coordinates?: TripStop["coordinates"]): TripStop =>
  ({ id, date: "2026-10-10", time, title, booking: "unknown", notes: "", coordinates });

describe("backend-neutral coordinates", () => {
  it("skips missing/invalid coordinates without changing stop IDs, visit times or itinerary numbers", () => {
    const stops = [
      stop("a", "09:00", "장소 A", { lat: 37.5, lng: 127 }),
      stop("b", "10:00", "좌표 없는 장소"),
      stop("c", "12:00", "장소 C", { lat: 37.6, lng: 127.1 }),
    ];
    const points = toMapPoints(stops);
    expect(points.map(({ id, order, time }) => ({ id, order, time }))).toEqual([
      { id: "a", order: 1, time: "09:00" },
      { id: "c", order: 3, time: "12:00" },
    ]);
    expect(points[0].coordinates).toEqual({ lat: 37.5, lng: 127 });
    expect(points[0].title).toBe("장소 A");
    stops[0].coordinates = { lat: 127, lng: 37.5 };
    expect(toMapPoints(stops).map((point) => point.order)).toEqual([3]);
  });

  it("accepts explicit zero and negative coordinates but never invents coordinates for a stop that has none", () => {
    expect(hasValidCoordinates({ lat: 0, lng: 0 })).toBe(true);
    expect(hasValidCoordinates({ lat: -33.8, lng: 151.2 })).toBe(true);
    for (const value of [undefined, null, { lat: NaN, lng: 0 }, { lat: 0, lng: Infinity }, { lat: 91, lng: 0 }, { lat: 0, lng: -181 }]) {
      expect(hasValidCoordinates(value)).toBe(false);
    }
    expect(toMapPoints([stop("a", "09:00", "경복궁"), stop("b", "10:00", "광장시장", null)])).toEqual([]);
  });
});
