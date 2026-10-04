import type { Coordinates, MapAdapter, MapLine, MapPoint } from "../model";
import { lineStyle, linesKey } from "./lines";
import { createPin, geometryKey, layoutPins, placePin, pointLabel, setPinSelected, type PinSlot } from "./pin";
import { createSdkLoader } from "./sdk-loader";

interface GoogleBounds { extend(position: Coordinates): void }
interface GoogleLatLng { lat(): number; lng(): number }
/** The world-coordinate projection of the map (Mercator, 256 px at zoom 0): enough to work out where a coordinate stands on screen. */
interface GoogleProjection { fromLatLngToPoint(position: Coordinates | GoogleLatLng): { x: number; y: number } | null }
interface GoogleMap {
  panTo(position: Coordinates): void;
  setCenter(position: Coordinates | GoogleLatLng): void;
  getCenter(): GoogleLatLng | undefined;
  setZoom(zoom: number): void;
  /** Optional: a build of the SDK without them still shows the pins (they then keep their first side). */
  getZoom?(): number | undefined;
  getProjection?(): GoogleProjection | undefined;
  fitBounds(bounds: GoogleBounds, padding: number | { top: number; right: number; bottom: number; left: number }): void;
  unbindAll(): void;
}
interface GoogleMarker extends HTMLElement { map: GoogleMap | null; zIndex: number }
interface GooglePolyline { setMap(map: GoogleMap | null): void }
interface GooglePolylineOptions {
  map: GoogleMap; path: Coordinates[]; strokeColor: string; strokeOpacity: number; strokeWeight: number; clickable: boolean;
  icons?: { icon: { path: string; strokeOpacity: number; scale: number }; offset: string; repeat: string }[];
}
interface GoogleSdk {
  Map: new (container: HTMLElement, options: {
    center: Coordinates; zoom: number; minZoom: number; maxZoom: number; mapId: string;
    mapTypeControl: boolean; streetViewControl: boolean; fullscreenControl: boolean; gestureHandling: string;
  }) => GoogleMap;
  LatLngBounds: new () => GoogleBounds;
  /** Optional: a build of the SDK without lines still shows the pins. */
  Polyline?: new (options: GooglePolylineOptions) => GooglePolyline;
  marker: {
    AdvancedMarkerElement: new (options: { map: GoogleMap; position: Coordinates; title: string; gmpClickable: boolean }) => GoogleMarker;
  };
  event: { trigger(target: GoogleMap, event: "resize"): void; clearInstanceListeners(target: GoogleMap): void; addListener?(target: GoogleMap, event: "idle", callback: () => void): unknown };
}

const loader = createSdkLoader<GoogleSdk>({
  provider: "google", label: "Google 지도", authCallback: "gm_authFailure",
  read: () => {
    const sdk = (window as Window & { google?: { maps?: GoogleSdk } }).google?.maps;
    return sdk?.Map && sdk.LatLngBounds && sdk.marker?.AdvancedMarkerElement && sdk.event ? sdk : undefined;
  },
  url: (key, callback) => `https://maps.googleapis.com/maps/api/js?${new URLSearchParams({
    key, callback, loading: "async", libraries: "marker", v: "weekly", language: "ko", region: "KR",
  })}`,
});

export function createGoogleAdapter(apiKey: string, mapId: string): MapAdapter {
  return {
    async create(container, options) {
      if (!mapId.trim()) throw new Error("Google 지도 Map ID가 설정되지 않았습니다.");
      const sdk = await loader.load(apiKey);
      const map = new sdk.Map(container, {
        center: options.points[0]?.coordinates ?? { lat: 37.5665, lng: 126.978 },
        zoom: 14, minZoom: 3, maxZoom: 18, mapId,
        mapTypeControl: false, streetViewControl: false, fullscreenControl: false, gestureHandling: "cooperative",
      });
      let destroyed = false;
      let points: MapPoint[] = [];
      let previousData = "";
      let previousGeometry = "";
      let selectedId: string | undefined;
      let needsFit = false;
      let markers: { id: string; marker: GoogleMarker; pin: HTMLElement; onClick: () => void }[] = [];
      let routes: GooglePolyline[] = [];
      let previousLines = "";
      const unwatch = loader.watchAuthFailure(options.onError);

      // ★`[2026-10-04]` Each pin stands on the side of its coordinate where it overlaps the fewest others (`layoutPins`); worked out again when the map comes to rest.
      let slots: Record<string, PinSlot> = {};
      function relayout() {
        const projection = map.getProjection?.(), center = map.getCenter(), zoom = map.getZoom?.();
        const middle = projection && center ? projection.fromLatLngToPoint(center) : null;
        if (destroyed || !projection || !middle || typeof zoom !== "number" || !markers.length || !container.clientWidth || !container.clientHeight) return;
        const scale = 2 ** zoom;
        const placed = points.flatMap((point) => {
          const world = projection.fromLatLngToPoint(point.coordinates);
          return world ? [{ id: point.id, x: (world.x - middle.x) * scale + container.clientWidth / 2, y: (world.y - middle.y) * scale + container.clientHeight / 2 }] : [];
        });
        slots = layoutPins(placed, { width: container.clientWidth, height: container.clientHeight, top: options.topInset ?? 0 }, slots);
        markers.forEach(({ id, pin }) => { if (slots[id]) placePin(pin, slots[id]); });
      }
      sdk.event.addListener?.(map, "idle", relayout);

      function clearMarkers() {
        markers.forEach(({ marker, onClick }) => {
          marker.removeEventListener("gmp-click", onClick);
          marker.map = null;
          marker.remove();
        });
        markers = [];
      }

      function fit() {
        if (!needsFit || !container.clientWidth || !container.clientHeight || !points.length) return;
        needsFit = false;
        if (points.length === 1) {
          map.setCenter(points[0].coordinates);
          map.setZoom(15);
        } else {
          const bounds = new sdk.LatLngBounds();
          points.forEach(({ coordinates }) => bounds.extend(coordinates));
          map.fitBounds(bounds, { top: 50 + (options.topInset ?? 0), right: 50, bottom: 50, left: 50 });
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
          // A dashed line is drawn as repeated dots of an icon (the way the SDK does it): the line itself is invisible.
          return new Polyline({
            map, path: line.points, strokeColor: style.color, strokeWeight: style.weight, clickable: false,
            strokeOpacity: style.dash ? 0 : style.opacity,
            ...(style.dash ? { icons: [{ icon: { path: "M 0,-1 0,1", strokeOpacity: style.opacity, scale: 3 }, offset: "0", repeat: `${style.dash[0] + style.dash[1]}px` }] } : {}),
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
            pin.style.transform = "translateY(50%)";          // the marker puts the middle of its bottom edge on the coordinate: the pin's box is centred on it instead
            const marker = new sdk.marker.AdvancedMarkerElement({
              map, position: point.coordinates, title: pointLabel(point), gmpClickable: true,
            });
            marker.append(pin);
            marker.setAttribute("aria-label", pointLabel(point));
            const onClick = () => options.onSelect(point.id);
            marker.addEventListener("gmp-click", onClick);
            markers.push({ id: point.id, marker, pin, onClick });
          });
          previousData = data;
          relayout();
        }
        markers.forEach(({ id, pin, marker }) => {
          const selected = id === nextSelectedId;
          setPinSelected(pin, selected);
          marker.setAttribute("aria-pressed", String(selected));
          marker.zIndex = selected ? 100 : 1;
        });
        if (changed) {
          previousGeometry = geometry;
          needsFit = true;
          fit();
        } else if (nextSelectedId !== selectedId) {
          const selected = points.find(({ id }) => id === nextSelectedId);
          if (selected) map.panTo(selected.coordinates);
        }
        selectedId = nextSelectedId;
      }

      function cleanMap() {
        clearMarkers();
        clearLines();
        unwatch();
        sdk.event.clearInstanceListeners(map);
        map.unbindAll();
        container.replaceChildren();
      }

      try { update(options.points, options.selectedId, options.lines); }
      catch (error) { cleanMap(); throw error; }

      return {
        update,
        fit() { needsFit = true; fit(); },
        resize() {
          if (destroyed || !container.clientWidth || !container.clientHeight) return;
          const center = map.getCenter();
          sdk.event.trigger(map, "resize");
          if (center) map.setCenter(center);
          fit();
        },
        destroy() {
          if (destroyed) return;
          destroyed = true;
          cleanMap();
        },
      };
    },
  };
}
