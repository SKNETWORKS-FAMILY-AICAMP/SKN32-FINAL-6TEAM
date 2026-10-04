import type { MapAdapter, MapLine, MapPoint } from "../model";
import { lineStyle, linesKey } from "./lines";
import { createPin, geometryKey, layoutPins, PIN_BOX, placePin, pointLabel, setPinSelected, type PinSlot } from "./pin";
import { createSdkLoader } from "./sdk-loader";

interface NaverLatLng { lat(): number; lng(): number }
interface NaverSize { width: number; height: number }
/** Optional: a build of the SDK without it still shows the pins (they then keep their first side). */
interface NaverProjection { fromCoordToOffset(position: NaverLatLng): { x: number; y: number } }
interface NaverMap {
  getProjection?(): NaverProjection | undefined;
  panTo(position: NaverLatLng): void;
  setCenter(position: NaverLatLng): void;
  getCenter(): NaverLatLng;
  setZoom(zoom: number): void;
  fitBounds(points: NaverLatLng[], margins: { top: number; right: number; bottom: number; left: number; maxZoom: number }): void;
  setSize(size: NaverSize): void;
  destroy(): void;
}
interface NaverMarker { setMap(map: NaverMap | null): void; setZIndex(zIndex: number): void }
interface NaverPolyline { setMap(map: NaverMap | null): void }
interface NaverPolylineOptions {
  map: NaverMap; path: NaverLatLng[]; strokeColor: string; strokeOpacity: number; strokeWeight: number;
  strokeStyle: "solid" | "shortdash"; strokeLineCap: "round"; strokeLineJoin: "round"; clickable: boolean;
}
interface NaverListener { eventName: string }
interface NaverSdk {
  Map: new (container: HTMLElement, options: { center: NaverLatLng; zoom: number; minZoom: number; maxZoom: number; zoomControl: boolean }) => NaverMap;
  LatLng: new (lat: number, lng: number) => NaverLatLng;
  /** Optional: a build of the SDK without lines still shows the pins. */
  Polyline?: new (options: NaverPolylineOptions) => NaverPolyline;
  Size: new (width: number, height: number) => NaverSize;
  Marker: new (options: {
    map: NaverMap; position: NaverLatLng; title: string;
    icon: { content: HTMLElement; size: NaverSize; anchor: { x: number; y: number } };
  }) => NaverMarker;
  Event: {
    addListener(target: NaverMarker | NaverMap, event: "click" | "idle", callback: () => void): NaverListener;
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
      let routes: NaverPolyline[] = [];
      let previousLines = "";
      const unwatch = loader.watchAuthFailure(options.onError);

      // ★`[2026-10-04]` Each pin stands on the side of its coordinate where it overlaps the fewest others (`layoutPins`); worked out again when the map comes to rest.
      let slots: Record<string, PinSlot> = {};
      function relayout() {
        const projection = map.getProjection?.();
        if (destroyed || !projection || !markers.length || !container.clientWidth || !container.clientHeight) return;
        const placed = points.map((point) => {
          const at = projection.fromCoordToOffset(new sdk.LatLng(point.coordinates.lat, point.coordinates.lng));
          return { id: point.id, x: at.x, y: at.y };
        });
        slots = layoutPins(placed, { width: container.clientWidth, height: container.clientHeight, top: options.topInset ?? 0 }, slots);
        markers.forEach(({ id, pin }) => { if (slots[id]) placePin(pin, slots[id]); });
      }
      const idleListener = sdk.Event.addListener(map, "idle", relayout);

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
          map.fitBounds(positions, { top: 80 + (options.topInset ?? 0), right: 80, bottom: 80, left: 80, maxZoom: 16 });
        }
      }

      function clearLines() {
        routes.forEach((route) => route.setMap(null));
        routes = [];
      }

      function drawLines(nextLines: MapLine[]) {
        const key = linesKey(nextLines);
        if (key === previousLines) return;
        previousLines = key;
        clearLines();
        const Polyline = sdk.Polyline;
        if (!Polyline) return;
        routes = nextLines.map((line) => {
          const style = lineStyle(container, line);
          return new Polyline({
            map, path: line.points.map(({ lat, lng }) => new sdk.LatLng(lat, lng)), strokeColor: style.color, strokeOpacity: style.opacity, strokeWeight: style.weight,
            strokeStyle: style.dash ? "shortdash" : "solid", strokeLineCap: "round", strokeLineJoin: "round", clickable: false,
          });
        });
      }

      function update(nextPoints: MapPoint[], nextSelectedId?: string, nextLines: MapLine[] = []) {
        if (destroyed) return;
        drawLines(nextLines);
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
              icon: { content: pin, size: new sdk.Size(PIN_BOX, PIN_BOX), anchor: { x: PIN_BOX / 2, y: PIN_BOX / 2 } },
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
          relayout();
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

      try { update(options.points, options.selectedId, options.lines); }
      catch (error) { clearMarkers(); clearLines(); sdk.Event.removeListener(idleListener); unwatch(); map.destroy(); throw error; }

      return {
        update,
        fit() { needsFit = true; fit(); },
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
          clearLines();
          sdk.Event.removeListener(idleListener);
          unwatch();
          map.destroy();
        },
      };
    },
  };
}
