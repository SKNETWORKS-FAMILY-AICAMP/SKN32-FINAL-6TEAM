import type { MapAdapter, MapLine, MapPoint } from "../model";
import { lineStyle, linesKey } from "./lines";
import { createPin, geometryKey, pointLabel, setPinSelected } from "./pin";

/**
 * Free map: OpenStreetMap standard tiles drawn with Leaflet.
 *
 * ★OSM tile policy (operations.osmfoundation.org/policies/tiles, read 2026-09-29):
 *   - visible attribution「© OpenStreetMap contributors」 — Leaflet's attribution control, never hidden;
 *   - https only; the browser's normal Referer/User-Agent go through (we set no Referrer-Policy);
 *   - only the tiles in view are fetched — no prefetching, no "download for offline", no cache-busting headers;
 *   - no SLA: the service may block or slow us. That is why this is the development default, not a promise to customers.
 */
export const OSM_ATTRIBUTION = '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors'
  + ' · <a href="https://www.openstreetmap.org/fixthemap" target="_blank" rel="noopener">지도 오류 신고</a>';

const SEOUL = { lat: 37.5665, lng: 126.978 };

export function createOsmAdapter(tileUrl: string): MapAdapter {
  return {
    async create(container, options) {
      const L = (await import("leaflet")).default;
      const map = L.map(container, { center: options.points[0]?.coordinates ?? SEOUL, zoom: 14, minZoom: 3, maxZoom: 18, zoomControl: true });
      const layer = L.tileLayer(tileUrl, { maxZoom: 19, attribution: OSM_ATTRIBUTION, crossOrigin: false });
      // ★One missing tile is not a broken map (the pins still show). Only when nothing has loaded after a few failures
      //   does the screen say the map could not be shown — never a blank grey box that looks like a map.
      let loaded = false;
      let failures = 0;
      layer.on("tileload", () => { loaded = true; });
      layer.on("tileerror", () => {
        failures += 1;
        if (!loaded && failures === 3) options.onError(new Error("무료 지도 타일을 불러오지 못했어요. 잠시 뒤 다시 시도해 주세요."));
      });
      layer.addTo(map);

      let destroyed = false;
      let points: MapPoint[] = [];
      let previousData = "";
      let previousGeometry = "";
      let selectedId: string | undefined;
      let needsFit = false;
      // ★The box can change size after the first fit (the sheet over the map goes up and down, a tab opens). Until the customer
      //   moves or zooms the map themselves, a new size fits the pins again; after that the map stays where they put it.
      let userMoved = false;
      let programmatic = false;
      map.on("dragstart", () => { userMoved = true; });
      map.on("zoomstart", () => { if (!programmatic) userMoved = true; });
      let markers: { id: string; marker: ReturnType<typeof L.marker>; pin: HTMLElement }[] = [];
      // Route lines sit in their own pane under the pins, so a pin is always pressable and a line never covers one.
      map.createPane("routes").style.zIndex = "350";
      const routes = L.layerGroup().addTo(map);
      let previousLines = "";

      function clearMarkers() {
        markers.forEach(({ marker }) => marker.remove());
        markers = [];
      }

      function fit() {
        if (!needsFit || !container.clientWidth || !container.clientHeight || !points.length) return;
        needsFit = false;
        programmatic = true;
        try {
          if (points.length === 1) map.setView(points[0].coordinates, 15);
          else map.fitBounds(L.latLngBounds(points.map(({ coordinates }) => [coordinates.lat, coordinates.lng] as [number, number])), { padding: [50, 50] });
        } finally { programmatic = false; }
      }

      function drawLines(nextLines: MapLine[]) {
        const key = linesKey(nextLines);
        if (key === previousLines) return;
        previousLines = key;
        routes.clearLayers();
        nextLines.forEach((line) => {
          const style = lineStyle(container, line);
          // `className` hooks the screen own CSS and the tests; the options are what Leaflet draws.
          L.polyline(line.points.map(({ lat, lng }) => [lat, lng] as [number, number]), {
            pane: "routes", color: style.color, weight: style.weight, opacity: style.opacity, lineCap: "round", lineJoin: "round",
            ...(style.dash ? { dashArray: style.dash.join(" ") } : {}), interactive: false, className: `trip-route-line${line.dashed ? " trip-route-line--dashed" : ""}`,
          }).bindTooltip(line.title, { sticky: true }).addTo(routes);
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
            const icon = L.divIcon({ html: pin, className: "", iconSize: [44, 44], iconAnchor: [6, 44] });
            const marker = L.marker(point.coordinates, { icon, title: pointLabel(point), alt: pointLabel(point), keyboard: true, riseOnHover: true });
            marker.on("click", () => options.onSelect(point.id));
            marker.addTo(map);
            markers.push({ id: point.id, marker, pin });
          });
          previousData = data;
        }
        markers.forEach(({ id, pin, marker }) => {
          const selected = id === nextSelectedId;
          setPinSelected(pin, selected);
          marker.getElement()?.setAttribute("aria-pressed", String(selected));
          marker.setZIndexOffset(selected ? 1000 : 0);
        });
        if (changed) {
          previousGeometry = geometry;
          needsFit = true;
          userMoved = false;            // different pins: the old view means nothing
          fit();
        } else if (nextSelectedId !== selectedId) {
          const selected = points.find(({ id }) => id === nextSelectedId);
          if (selected) map.panTo(selected.coordinates);
        }
        selectedId = nextSelectedId;
      }

      try { update(options.points, options.selectedId, options.lines); }
      catch (error) { clearMarkers(); map.remove(); throw error; }

      return {
        update,
        resize() {
          if (destroyed || !container.clientWidth || !container.clientHeight) return;
          map.invalidateSize();
          if (!userMoved) needsFit = true;
          fit();
        },
        destroy() {
          if (destroyed) return;
          destroyed = true;
          clearMarkers();
          map.remove();
          container.replaceChildren();
        },
      };
    },
  };
}
