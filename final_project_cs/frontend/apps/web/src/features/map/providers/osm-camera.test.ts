import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createOsmAdapter } from "./osm";
import type { MapPoint } from "../model";

const state = vi.hoisted(() => ({ zoom: 14, reduced: false, map: {} as Record<string, ReturnType<typeof vi.fn>> }));
vi.mock("leaflet", () => {
  const layer = () => ({ addTo: vi.fn().mockReturnThis(), on: vi.fn().mockReturnThis(), clearLayers: vi.fn() });
  const marker = () => {
    const element = { style: {}, dataset: {}, setAttribute: vi.fn(), removeAttribute: vi.fn(), querySelectorAll: () => [] };
    return { ...layer(), getElement: () => element, setZIndexOffset: vi.fn(), remove: vi.fn() };
  };
  return { default: { map: () => state.map, tileLayer: layer, layerGroup: layer, divIcon: vi.fn(), marker } };
});
vi.mock("./pin", async (original) => ({
  ...await original<typeof import("./pin")>(),
  createPin: () => ({}), createPinLeader: () => ({}),
  setPinSelected: vi.fn(), placePin: vi.fn(), paintPinGroups: vi.fn(), popPin: vi.fn(),
  pinArea: () => ({ width: 375, height: 300 }),
}));
beforeEach(() => {
  state.zoom = 14; state.reduced = false;
  vi.stubGlobal("matchMedia", () => ({ matches: state.reduced }));
  state.map = {
    on: vi.fn(), once: vi.fn(), remove: vi.fn(),
    createPane: vi.fn(() => ({ style: {} })),
    getCenter: vi.fn(() => ({ lat: 37.56, lng: 126.98 })),
    getZoom: vi.fn(() => state.zoom), getMinZoom: vi.fn(() => 3), getMaxZoom: vi.fn(() => 18),
    getBounds: vi.fn(() => ({ contains: () => true, getSouth: () => 37.5, getWest: () => 126.9, getNorth: () => 37.6, getEast: () => 127.0 })),
    latLngToContainerPoint: vi.fn(() => ({ x: 120, y: 120 })),
    setView: vi.fn(), panTo: vi.fn(), setZoom: vi.fn(), flyTo: vi.fn(),
  };
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const create = (points: MapPoint[] = []) => createOsmAdapter("https://example.invalid/{z}/{x}/{y}.png").create(
  { clientWidth: 375, clientHeight: 300, replaceChildren: vi.fn() } as unknown as HTMLElement,
  { points, onSelect: vi.fn(), onError: vi.fn() },
);

it.each([true, false])("움직임 줄이기에서 중심 이동은 애니메이션을 끈다: 기존 줌 유지=%s", async (keepZoom) => {
  state.reduced = true;
  const controller = await create();
  const at = { lat: 37.57, lng: 126.99 };
  controller.centerOn(at, keepZoom);
  if (keepZoom) expect(state.map.panTo).toHaveBeenCalledWith([at.lat, at.lng], { animate: false });
  else expect(state.map.setView).toHaveBeenCalledWith([at.lat, at.lng], 15, { animate: false });
  controller.destroy();
});
it("움직임 줄이기에서 선택 일정으로 이동할 때도 패닝 애니메이션을 끈다", async () => {
  state.reduced = true;
  const points: MapPoint[] = [{ id: "first", title: "첫 일정", date: "", time: "", order: 1, coordinates: { lat: 37.56, lng: 126.98 } }];
  const controller = await create(points);
  state.map.panTo.mockClear();
  controller.update(points, "first");
  expect(state.map.panTo).toHaveBeenCalledWith(points[0].coordinates, { animate: false });
  controller.destroy();
});
it.each([[18, 1], [3, -1]] as const)("줌 경계 %s에서 %s 입력은 범위 밖 비행을 시작하지 않는다", async (zoom, delta) => {
  const controller = await create(); state.zoom = zoom;
  controller.zoomBy(delta);
  expect(state.map.flyTo).not.toHaveBeenCalled();
  expect(state.map.setZoom).not.toHaveBeenCalled();
  controller.destroy();
});
it.each([[13.4, 1, 14], [13.6, -1, 13]] as const)("비행 중 소수 줌 %s에서 %s 입력은 정수 %s로 이동한다", async (zoom, delta, target) => {
  const controller = await create(); state.zoom = zoom;
  controller.zoomBy(delta);
  expect(state.map.flyTo).toHaveBeenCalledWith(expect.anything(), target, expect.anything());
  controller.destroy();
});
