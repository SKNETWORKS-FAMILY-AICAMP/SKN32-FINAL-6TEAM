import type { Coordinates, MapAdapter, MapLine, MapPoint, MyLocation, StayPoint } from "../model";
import { lineStyle, linesKey } from "./lines";
import { ACCURACY_STYLE, accuracyRadius, createMeDot, createStayDot, ME_LABEL, meKey, staysKey } from "./me";
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
interface GoogleMarker extends HTMLElement { map: GoogleMap | null; zIndex: number; position?: Coordinates | null }
interface GooglePolyline { setMap(map: GoogleMap | null): void }
/** `[2026-10-05]` The accuracy circle of 「내 위치」 (`google.maps.Circle`, radius in metres). */
interface GoogleCircle { setMap(map: GoogleMap | null): void; setCenter(center: Coordinates): void; setRadius(radius: number): void }
interface GoogleCircleOptions {
  map: GoogleMap; center: Coordinates; radius: number; strokeColor: string; strokeOpacity: number; strokeWeight: number;
  fillColor: string; fillOpacity: number; clickable: boolean; zIndex: number;
}
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
  /** Optional: without it 「내 위치」 is the dot alone. */
  Circle?: new (options: GoogleCircleOptions) => GoogleCircle;
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
      let centredOnMe = false;           // [2026-10-05] an empty map is centred on the customer once; pins (a different set of them) reset it
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
      // [2026-10-05] The zoom level goes to the screen (it asks for the detailed route lines when zoomed in).
      sdk.event.addListener?.(map, "idle", () => { const zoom = map.getZoom?.(); if (typeof zoom === "number") options.onZoom?.(zoom); });

      function clearMarkers() {
        markers.forEach(({ marker, onClick }) => {
          marker.removeEventListener("gmp-click", onClick);
          marker.map = null;
          marker.remove();
        });
        markers = [];
      }

      // ★`[2026-10-05 사용자 지시]` 「내 위치」: a marker that takes no press, under the pins (`zIndex` 0; pins are 1 and 100; stays −1), and its accuracy circle.
      let me: MyLocation | null = null;
      let meMarker: GoogleMarker | null = null;
      let meCircle: GoogleCircle | null = null;
      let previousMe = "";
      let stayMarkers: GoogleMarker[] = [];
      let previousStays = "";

      function quietMarker(position: Coordinates, title: string, content: HTMLElement, zIndex: number): GoogleMarker {
        const marker = new sdk.marker.AdvancedMarkerElement({ map, position, title, gmpClickable: false });
        content.style.transform = "translateY(50%)";        // the marker stands the middle of its bottom edge on the coordinate: centre the dot on it instead
        marker.append(content);
        marker.zIndex = zIndex;
        marker.style.pointerEvents = "none";
        return marker;
      }

      function removeMe() {
        if (meMarker) { meMarker.map = null; meMarker.remove(); }
        meCircle?.setMap(null);
        meMarker = null;
        meCircle = null;
      }

      function clearStays() {
        stayMarkers.forEach((marker) => { marker.map = null; marker.remove(); });
        stayMarkers = [];
      }

      function fit() {
        if (!needsFit || !container.clientWidth || !container.clientHeight) return;
        // `[2026-10-05]` No pins: the customer's own position is the picture (once — the map does not chase them); nothing at all: wait.
        if (!points.length) {
          if (!me) return;
          needsFit = false;
          centredOnMe = true;
          map.setCenter(me.coordinates);
          map.setZoom(15);
          return;
        }
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
          centredOnMe = false;          // [2026-10-05] a different set of pins: an empty day after it centres on the customer again
          fit();
        } else if (nextSelectedId !== selectedId) {
          const selected = points.find(({ id }) => id === nextSelectedId);
          if (selected) map.panTo(selected.coordinates);
        }
        selectedId = nextSelectedId;
      }

      function setMe(next: MyLocation | null) {
        if (destroyed) return;
        me = next;
        const key = meKey(next);
        if (key === previousMe) return;
        previousMe = key;
        if (!next) { removeMe(); return; }
        if (meMarker) meMarker.position = next.coordinates;
        else meMarker = quietMarker(next.coordinates, ME_LABEL, createMeDot(), 0);
        const radius = accuracyRadius(next);
        if (radius === null) { meCircle?.setMap(null); meCircle = null; }
        else if (meCircle) { meCircle.setCenter(next.coordinates); meCircle.setRadius(radius); }
        else if (sdk.Circle) {
          meCircle = new sdk.Circle({
            map, center: next.coordinates, radius, strokeColor: ACCURACY_STYLE.color, strokeOpacity: ACCURACY_STYLE.opacity, strokeWeight: ACCURACY_STYLE.weight,
            fillColor: ACCURACY_STYLE.color, fillOpacity: ACCURACY_STYLE.fillOpacity, clickable: false, zIndex: 0,
          });
        }
        if (!points.length && !centredOnMe) needsFit = true;          // [2026-10-05] a map that never had pins was never fitted: the first position it learns centres it, once
        if (!points.length && needsFit) fit();
      }

      function setStays(stays: StayPoint[]) {
        if (destroyed) return;
        const key = staysKey(stays);
        if (key === previousStays) return;
        previousStays = key;
        clearStays();
        stayMarkers = stays.map((stay) => quietMarker(stay.coordinates, stay.label, createStayDot(stay), -1));
      }

      function cleanMap() {
        clearMarkers();
        clearLines();
        removeMe();
        clearStays();
        unwatch();
        sdk.event.clearInstanceListeners(map);
        map.unbindAll();
        container.replaceChildren();
      }

      try { update(options.points, options.selectedId, options.lines); setMe(options.me ?? null); setStays(options.stays ?? []); }
      catch (error) { cleanMap(); throw error; }

      return {
        update,
        setMe,
        setStays,
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
