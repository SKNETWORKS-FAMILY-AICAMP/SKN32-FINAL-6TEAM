import { describe, expect, it } from "vitest";
import { createDemoGateway, DEMO_STORAGE_PREFIX, DEMO_VERIFICATION_DURATION } from "@/lib/demo";
import { parseDemoPlan } from "@/lib/demo/parse-plan";
import { SAMPLE_PLANS } from "@/lib/demo/sample";
import { translator } from "@/lib/i18n";
import { resolveMapConfiguration } from "./config";
import { hasValidCoordinates, toMapPoints } from "./map-points";

const t = translator("ko");

describe("map provider selection", () => {
  it("keeps diagram mode explicit and needs only the selected provider's settings", () => {
    expect(resolveMapConfiguration({})).toEqual({ provider: "demo" });
    expect(resolveMapConfiguration({ provider: "demo", googleApiKey: "unused" })).toEqual({ provider: "demo" });
    expect(resolveMapConfiguration({ provider: "naver", naverClientId: " web-id " })).toEqual({ provider: "naver", clientId: "web-id" });
    expect(resolveMapConfiguration({ provider: "google", googleApiKey: "web-key", googleMapId: "map-id" })).toEqual({ provider: "google", apiKey: "web-key", mapId: "map-id" });
  });

  it.each([
    { provider: "naver", googleApiKey: "not-a-naver-key" },
    { provider: "google", googleApiKey: "key-with-no-map-id" },
    { provider: "google", googleMapId: "id-with-no-key" },
    { provider: "misspelled-provider" },
  ])("does not silently replace invalid live configuration with diagram: %o", (config) => {
    expect(resolveMapConfiguration(config).provider).toBe("unavailable");
  });
});

describe("backend-neutral coordinates", () => {
  it("skips missing/invalid coordinates without changing stop IDs, visit times or itinerary numbers", () => {
    const stops = parseDemoPlan("1일차 · 2026-10-10\n09:00 장소 A · [좌표: 37.5, 127]\n10:00 좌표 없는 장소\n12:00 장소 C · [좌표: 37.6, 127.1]", t);
    const points = toMapPoints(stops);
    expect(points.map(({ id, order, time }) => ({ id, order, time }))).toEqual([
      { id: stops[0].id, order: 1, time: "09:00" },
      { id: stops[2].id, order: 3, time: "12:00" },
    ]);
    expect(points[0].coordinates).toEqual({ lat: 37.5, lng: 127 });
    expect(points[0].title).toBe("장소 A");
    stops[0].coordinates = { lat: 127, lng: 37.5 };
    expect(toMapPoints(stops).map((point) => point.order)).toEqual([3]);
  });

  it("accepts explicit zero and negative coordinates but never invents coordinates for sample place names", () => {
    expect(hasValidCoordinates({ lat: 0, lng: 0 })).toBe(true);
    expect(hasValidCoordinates({ lat: -33.8, lng: 151.2 })).toBe(true);
    for (const value of [undefined, null, { lat: NaN, lng: 0 }, { lat: 0, lng: Infinity }, { lat: 91, lng: 0 }, { lat: 0, lng: -181 }]) {
      expect(hasValidCoordinates(value)).toBe(false);
    }
    expect(toMapPoints(parseDemoPlan(SAMPLE_PLANS.ko, t))).toEqual([]);
  });

  it.each(["[좌표: 91, 0]", "[좌표: 0, 181]", "[좌표: abc, 127]", "[좌표: , ]"])("rejects malformed manual demo coordinate %s", (tag) => {
    expect(() => parseDemoPlan(`1일차 · 2026-10-10\n09:00 장소 ${tag}`, t)).toThrow();
  });

  it("preserves received coordinates through verification, storage reload and management start", async () => {
    const data = new Map<string, string>();
    const storage = { getItem: (key: string) => data.get(key) ?? null, setItem: (key: string, value: string) => { data.set(key, value); } };
    let now = 0;
    const gateway = createDemoGateway({ storage, now: () => now });
    const trip = await gateway.createTrip({ source: "1일차 · 2026-10-10\n09:00 장소 · [좌표: 37.5, 127]" }, "ko");
    now = DEMO_VERIFICATION_DURATION;
    const active = await gateway.startTrip(trip.id, "ko");
    expect(active.stops[0].coordinates).toEqual({ lat: 37.5, lng: 127 });
    const reloaded = createDemoGateway({ storage, now: () => now });
    expect((await reloaded.getTrip(trip.id, "ko")).stops[0].coordinates).toEqual(active.stops[0].coordinates);
    const key = DEMO_STORAGE_PREFIX + trip.id;
    const stored = JSON.parse(data.get(key)!);
    stored.trip.stops[0].coordinates = { lat: 200, lng: 127 };
    data.set(key, JSON.stringify(stored));
    await expect(reloaded.getTrip(trip.id, "ko")).rejects.toMatchObject({ code: "CORRUPT_STORAGE" });
  });
});
