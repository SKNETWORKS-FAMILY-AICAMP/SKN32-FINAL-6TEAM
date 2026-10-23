import { afterEach, expect, it, vi } from "vitest";
import { createGoogleAdapter } from "./google";
import { createNaverAdapter } from "./naver";

// `[2026-10-22 ST4F-722 D안]` 「목록에서 누름 · 상세 보기」 — the pin in the middle of the visible part (under the 64 px bar, over the 24 px of sheet), at the zoom asked for.
const state = vi.hoisted(() => ({ sdk: {} as object }));
vi.mock("./sdk-loader", () => ({ createSdkLoader: () => ({ load: async () => state.sdk, watchAuthFailure: () => () => {} }) }));
afterEach(() => vi.restoreAllMocks());

for (const provider of ["google", "naver"] as const) {
  it(`${provider}: focus centres the pin in the visible part at the zoom asked for`, async () => {
    const calls: [string, ...unknown[]][] = [];
    class FakeMap {
      setCenter(at: unknown) { calls.push(["setCenter", at]); }
      setZoom(zoom: number) { calls.push(["setZoom", zoom]); }
      panBy(...offset: unknown[]) { calls.push(["panBy", ...offset]); }
      getZoom() { return 12; }
      getCenter() { return { lat: 37.55, lng: 126.95 }; }
      unbindAll() {}
      destroy() {}
    }
    class LatLng { constructor(public latitude: number, public longitude: number) {} lat() { return this.latitude; } lng() { return this.longitude; } }
    class Point { constructor(public x: number, public y: number) {} }
    const events = { addListener: () => ({ eventName: "" }), removeListener() {}, clearInstanceListeners() {} };
    state.sdk = { Map: FakeMap, LatLng, Point, event: events, Event: events };
    const container = { clientWidth: 375, clientHeight: 392, replaceChildren: vi.fn() } as unknown as HTMLElement;
    const adapter = provider === "google" ? createGoogleAdapter("test-key", "test-map") : createNaverAdapter("test-client");
    const controller = await adapter.create(container, { points: [], onSelect: vi.fn(), onError: vi.fn(), topInset: 64, bottomInset: 24 });
    calls.length = 0;
    const at = { lat: 37.5740, lng: 126.9855 };
    controller.focus(at, 18);
    expect(calls.map(([name]) => name)).toEqual(["setCenter", "setZoom", "panBy"]);
    expect(calls[1]).toEqual(["setZoom", 18]);
    if (provider === "google") {
      expect(calls[0]).toEqual(["setCenter", at]);
      expect(calls[2]).toEqual(["panBy", 0, -20]);                      // the centre goes 20 px up: the pin stands 20 px below the middle of the map
    } else {
      expect(calls[0][1]).toMatchObject({ latitude: at.lat, longitude: at.lng });
      expect(calls[2][1]).toMatchObject({ x: 0, y: -20 });
    }
    controller.destroy();
  });
}
