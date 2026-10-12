import { afterEach, expect, it, vi } from "vitest";
import type { MapView } from "../model";
import { createGoogleAdapter } from "./google";
import { createNaverAdapter } from "./naver";

const state = vi.hoisted(() => ({ sdk: {} as object }));
vi.mock("./sdk-loader", () => ({ createSdkLoader: () => ({ load: async () => state.sdk, watchAuthFailure: () => () => {} }) }));
afterEach(() => vi.restoreAllMocks());

for (const provider of ["google", "naver"] as const) {
  it(`${provider}: bounds changes publish the current viewport before idle and stop after destroy`, async () => {
    let bounds = { south: 37.5, west: 126.9, north: 37.6, east: 127.0 };
    const listeners = new Set<{ target: object; event: string; call: () => void }>();
    class FakeMap {
      getBounds() { return { ...Object.fromEntries(Object.entries(bounds).map(([key, value]) => [key, () => value])), toJSON: () => ({ ...bounds }) }; }
      getZoom() { return 14; }
      getCenter() { return { lat: 37.55, lng: 126.95 }; }
      unbindAll() {}
      destroy() {}
    }
    class LatLng { constructor(public latitude: number, public longitude: number) {} lat() { return this.latitude; } lng() { return this.longitude; } }
    const events = {
      addListener(target: object, event: string, call: () => void) { const listener = { target, event, call }; listeners.add(listener); return listener; },
      removeListener(listener: { target: object; event: string; call: () => void }) { listeners.delete(listener); },
      clearInstanceListeners(target: object) { for (const listener of listeners) if (listener.target === target) listeners.delete(listener); },
    };
    state.sdk = { Map: FakeMap, LatLng, event: events, Event: events };
    const container = { clientWidth: 375, clientHeight: 300, replaceChildren: vi.fn() } as unknown as HTMLElement;
    const onView = vi.fn<(view: MapView) => void>();
    const adapter = provider === "google" ? createGoogleAdapter("test-key", "test-map") : createNaverAdapter("test-client");
    const controller = await adapter.create(container, { points: [], onSelect: vi.fn(), onError: vi.fn(), onView });
    const move = () => { for (const listener of listeners) if (listener.event === "bounds_changed") listener.call(); };
    bounds = { south: 37.55, west: 126.95, north: 37.65, east: 127.05 };
    move();
    expect(onView).toHaveBeenLastCalledWith({ ...bounds, width: 375, height: 300, zoom: 14 });
    bounds = { ...bounds, west: 127.0, east: 127.1 };
    move();
    expect(onView).toHaveBeenLastCalledWith({ ...bounds, width: 375, height: 300, zoom: 14 });
    controller.destroy();
    const calls = onView.mock.calls.length;
    move();
    expect(onView).toHaveBeenCalledTimes(calls);
    expect(listeners.size).toBe(0);
  });
}
