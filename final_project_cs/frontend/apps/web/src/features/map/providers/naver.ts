import type { MapAdapter, MapPoint } from "../model";
import { createPin, geometryKey, pointLabel, setPinSelected } from "./pin";
import { createSdkLoader } from "./sdk-loader";

interface NaverLatLng { lat(): number; lng(): number }
interface NaverSize { width: number; height: number }
interface NaverMap {
  panTo(position: NaverLatLng): void;
  setCenter(position: NaverLatLng): void;
  getCenter(): NaverLatLng;
  setZoom(zoom: number): void;
  fitBounds(points: NaverLatLng[], margins: { top: number; right: number; bottom: number; left: number; maxZoom: number }): void;
  setSize(size: NaverSize): void;
  destroy(): void;
}
interface NaverMarker { setMap(map: NaverMap | null): void; setZIndex(zIndex: number): void }
interface NaverListener { eventName: string }
interface NaverSdk {
  Map: new (container: HTMLElement, options: { center: NaverLatLng; zoom: number; minZoom: number; maxZoom: number; zoomControl: boolean }) => NaverMap;
  LatLng: new (lat: number, lng: number) => NaverLatLng;
  Size: new (width: number, height: number) => NaverSize;
  Marker: new (options: {
    map: NaverMap; position: NaverLatLng; title: string;
    icon: { content: HTMLElement; size: NaverSize; anchor: { x: number; y: number } };
  }) => NaverMarker;
  Event: {
    addListener(target: NaverMarker, event: "click", callback: () => void): NaverListener;
    removeListener(listener: NaverListener): void;
  };
}

const loader = createSdkLoader<NaverSdk>({
  provider: "naver", label: "네이버지도", authCallback: "navermap_authFailure",
  read: () => {
    const sdk = (window as Window & { naver?: { maps?: NaverSdk } }).naver?.maps;
    return sdk?.Map && sdk.Marker && sdk.LatLng && sdk.Size && sdk.Event ? sdk : undefined;
  },
  url: (key, callback) => `https://oapi.map.naver.com/openapi/v3/maps.js?${new URLSearchParams({ ncpKeyId: key, callback })}`,
});

export function createNaverAdapter(clientId: string): MapAdapter {
  return {
    async create(container, options) {
      const sdk = await loader.load(clientId);
      const initial = options.points[0]?.coordinates ?? { lat: 37.5665, lng: 126.978 };
      const map = new sdk.Map(container, {
        center: new sdk.LatLng(initial.lat, initial.lng), zoom: 14, minZoom: 3, maxZoom: 18, zoomControl: true,
      });
      let destroyed = false;
      let points: MapPoint[] = [];
      let previousData = "";
      let previousGeometry = "";
      let selectedId: string | undefined;
      let needsFit = false;
      let markers: { id: string; marker: NaverMarker; pin: HTMLElement; listener: NaverListener; onKey: (event: KeyboardEvent) => void }[] = [];
      const unwatch = loader.watchAuthFailure(options.onError);

      function clearMarkers() {
        markers.forEach(({ marker, pin, listener, onKey }) => {
          sdk.Event.removeListener(listener);
          pin.removeEventListener("keydown", onKey);
          marker.setMap(null);
        });
        markers = [];
      }

      function fit() {
        if (!needsFit || !container.clientWidth || !container.clientHeight || !points.length) return;
        needsFit = false;
        const positions = points.map(({ coordinates }) => new sdk.LatLng(coordinates.lat, coordinates.lng));
        if (positions.length === 1) {
          map.setCenter(positions[0]);
          map.setZoom(15);
        } else {
          map.fitBounds(positions, { top: 80, right: 80, bottom: 80, left: 80, maxZoom: 16 });
        }
      }

      function update(nextPoints: MapPoint[], nextSelectedId?: string) {
        if (destroyed) return;
        const data = JSON.stringify(nextPoints);
        const geometry = geometryKey(nextPoints);
        const changed = geometry !== previousGeometry;
        points = nextPoints;
        if (data !== previousData) {
          clearMarkers();
          points.forEach((point) => {
            const pin = createPin(point);
            pin.setAttribute("role", "button");
            pin.setAttribute("aria-label", pointLabel(point));
            pin.tabIndex = 0;
            const marker = new sdk.Marker({
              map, position: new sdk.LatLng(point.coordinates.lat, point.coordinates.lng), title: pointLabel(point),
              icon: { content: pin, size: new sdk.Size(44, 44), anchor: { x: 22, y: 44 } },
            });
            const listener = sdk.Event.addListener(marker, "click", () => options.onSelect(point.id));
            const onKey = (event: KeyboardEvent) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                event.stopPropagation();
                options.onSelect(point.id);
              }
            };
            pin.addEventListener("keydown", onKey);
            markers.push({ id: point.id, marker, pin, listener, onKey });
          });
          previousData = data;
        }
        markers.forEach(({ id, pin, marker }) => {
          const selected = id === nextSelectedId;
          setPinSelected(pin, selected);
          pin.setAttribute("aria-pressed", String(selected));
          marker.setZIndex(selected ? 100 : 1);
        });
        if (changed) {
          previousGeometry = geometry;
          needsFit = true;
          fit();
        } else if (nextSelectedId !== selectedId) {
          const selected = points.find(({ id }) => id === nextSelectedId);
          if (selected) map.panTo(new sdk.LatLng(selected.coordinates.lat, selected.coordinates.lng));
        }
        selectedId = nextSelectedId;
      }

      try { update(options.points, options.selectedId); }
      catch (error) { clearMarkers(); unwatch(); map.destroy(); throw error; }

      return {
        update,
        resize() {
          if (destroyed || !container.clientWidth || !container.clientHeight) return;
          const center = map.getCenter();
          map.setSize(new sdk.Size(container.clientWidth, container.clientHeight));
          map.setCenter(center);
          fit();
        },
        destroy() {
          if (destroyed) return;
          destroyed = true;
          clearMarkers();
          unwatch();
          map.destroy();
        },
      };
    },
  };
}
