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
  return { default: { map: () => state.map, tileLayer: layer, layerGroup: layer, divIcon: vi.fn(), marker, latLngBounds: () => ({}) } };
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
    setView: vi.fn(), panTo: vi.fn(), setZoom: vi.fn(), flyTo: vi.fn(), invalidateSize: vi.fn(), fitBounds: vi.fn(), flyToBounds: vi.fn(),
    project: vi.fn(() => ({ x: 1000, y: 2000 })), unproject: vi.fn(([x, y]: [number, number]) => ({ lat: y, lng: x })),
  };
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const create = (points: MapPoint[] = [], insets: { topInset?: number; bottomInset?: number } = {}) => createOsmAdapter("https://example.invalid/{z}/{x}/{y}.png").create(
  { clientWidth: 375, clientHeight: 300, replaceChildren: vi.fn() } as unknown as HTMLElement,
  { points, onSelect: vi.fn(), onError: vi.fn(), ...insets },
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

// `[2026-10-22 ST4F-722 D안]` 목록에서 누름 · 상세 보기: 보이는 칸(머리줄 아래 · 시트 위) 가운데에 그 줌으로
const one: MapPoint[] = [{ id: "first", title: "첫 일정", date: "", time: "", order: 1, coordinates: { lat: 37.574, lng: 126.9855 } }];
it("초점은 보이는 칸 가운데로 날아가고 지도가 가는 줌을 넘지 않는다", async () => {
  const controller = await create(one, { topInset: 64, bottomInset: 24 });
  controller.focus(one[0].coordinates, 19);
  expect(state.map.project).toHaveBeenCalledWith([37.574, 126.9855], 18);
  expect(state.map.unproject).toHaveBeenCalledWith([1000, 1980], 18);            // 중심은 20px 위: 핀이 지도 가운데보다 20px 아래(보이는 칸 가운데)
  expect(state.map.flyTo).toHaveBeenCalledWith({ lat: 1980, lng: 1000 }, 18, expect.anything());
  controller.destroy();
});
it("움직임 줄이기에서는 초점도 바로 그 자리 · 그 줌으로", async () => {
  state.reduced = true;
  const controller = await create(one);
  state.map.setView.mockClear();
  controller.focus(one[0].coordinates, 18);
  expect(state.map.setView).toHaveBeenCalledWith({ lat: 2000, lng: 1000 }, 18, { animate: false });
  expect(state.map.flyTo).not.toHaveBeenCalled();
  controller.destroy();
});
it("초점을 맞춘 뒤에는 지도 크기가 바뀌어도 모든 핀 맞춤으로 돌아가지 않는다", async () => {
  const two: MapPoint[] = [...one, { id: "second", title: "둘째 일정", date: "", time: "", order: 2, coordinates: { lat: 37.58, lng: 126.98 } }];
  const controller = await create(two);
  controller.resize();
  expect(state.map.flyToBounds).toHaveBeenCalledTimes(1);                         // 아직 고객 카메라가 아니면 새 크기에 다시 맞춘다(그대로)
  controller.focus(two[0].coordinates, 18);
  state.map.flyToBounds.mockClear(); state.map.fitBounds.mockClear();
  controller.resize();
  expect(state.map.flyToBounds).not.toHaveBeenCalled();
  expect(state.map.fitBounds).not.toHaveBeenCalled();
  controller.destroy();
});
