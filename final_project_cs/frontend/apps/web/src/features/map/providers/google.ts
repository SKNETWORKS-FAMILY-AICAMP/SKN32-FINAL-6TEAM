import type { Coordinates, MapAdapter, MapPoint } from "../model";
import { createPin, geometryKey, pointLabel, setPinSelected } from "./pin";
import { createSdkLoader } from "./sdk-loader";

interface GoogleBounds { extend(position: Coordinates): void }
interface GoogleLatLng { lat(): number; lng(): number }
interface GoogleMap {
  panTo(position: Coordinates): void;
  setCenter(position: Coordinates | GoogleLatLng): void;
  getCenter(): GoogleLatLng | undefined;
  setZoom(zoom: number): void;
  fitBounds(bounds: GoogleBounds, padding: number): void;
  unbindAll(): void;
}
interface GoogleMarker extends HTMLElement { map: GoogleMap | null; zIndex: number }
interface GoogleSdk {
  Map: new (container: HTMLElement, options: {
    center: Coordinates; zoom: number; minZoom: number; maxZoom: number; mapId: string;
    mapTypeControl: boolean; streetViewControl: boolean; fullscreenControl: boolean; gestureHandling: string;
  }) => GoogleMap;
  LatLngBounds: new () => GoogleBounds;
  marker: {
    AdvancedMarkerElement: new (options: { map: GoogleMap; position: Coordinates; title: string; gmpClickable: boolean }) => GoogleMarker;
  };
  event: { trigger(target: GoogleMap, event: "resize"): void; clearInstanceListeners(target: GoogleMap): void };
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
      const unwatch = loader.watchAuthFailure(options.onError);

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
          map.fitBounds(bounds, 50);
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
        unwatch();
        sdk.event.clearInstanceListeners(map);
        map.unbindAll();
        container.replaceChildren();
      }

      try { update(options.points, options.selectedId); }
      catch (error) { cleanMap(); throw error; }

      return {
        update,
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
