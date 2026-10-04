import type { MapAdapter, MapLine, MapPoint } from "../model";
import { lineStyle, linesKey } from "./lines";
import { createPin, geometryKey, layoutPins, PIN_BOX, placePin, pointLabel, setPinSelected, type PinSlot } from "./pin";

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
export const FIT_LABEL = "모든 일정 보기";
/** The four corners of a frame (lucide 「scan」): everything in view. */
export const FIT_ICON = '<svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/></svg>';

export function createOsmAdapter(tileUrl: string): MapAdapter {
  return {
    async create(container, options) {
      const L = (await import("leaflet")).default;
      // ★`[2026-10-04]` The zoom buttons stand at the right, under the bar that floats over the map (they were at the top-left, under the home mark).
      const map = L.map(container, { center: options.points[0]?.coordinates ?? SEOUL, zoom: 14, minZoom: 3, maxZoom: 18, zoomControl: false });
      L.control.zoom({ position: "topright" }).addTo(map);
      const topRight = container.querySelector<HTMLElement>(".leaflet-top.leaflet-right");
      if (topRight && options.topInset) topRight.style.top = `${options.topInset}px`;
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

      // ★`[2026-10-04]` Each pin stands on the side of its coordinate where it overlaps the fewest others (`layoutPins`); worked out again when the map moves or zooms.
      let slots: Record<string, PinSlot> = {};
      function relayout() {
        if (destroyed || !markers.length || !container.clientWidth || !container.clientHeight) return;
        const size = map.getSize();
        slots = layoutPins(points.map((point) => {
          const at = map.latLngToContainerPoint([point.coordinates.lat, point.coordinates.lng]);
          return { id: point.id, x: at.x, y: at.y };
        }), { width: size.x, height: size.y, top: options.topInset ?? 0 }, slots);
        markers.forEach(({ id, pin }) => { if (slots[id]) placePin(pin, slots[id]); });
      }
      map.on("moveend zoomend resize", relayout);

      function fit() {
        if (!needsFit || !container.clientWidth || !container.clientHeight || !points.length) return;
        needsFit = false;
        programmatic = true;
        try {
          if (points.length === 1) map.setView(points[0].coordinates, 15);
          else map.fitBounds(L.latLngBounds(points.map(({ coordinates }) => [coordinates.lat, coordinates.lng] as [number, number])), { paddingTopLeft: [50, 50 + (options.topInset ?? 0)], paddingBottomRight: [50, 50] });
        } finally { programmatic = false; }
      }

      // ★`[2026-10-04 사용자 지시]` One more button in the zoom group: every pin back in view, at the place and zoom the map first showed them.
      //   ★Leaflet silently drops a new view while a zoom animation is running (`_animatingZoom`; `fitBounds` answers "done" without moving), so a press that comes a quarter
      //   of a second after +/- would do nothing - it waits for the zoom to end and then fits.
      function fitAll() {
        userMoved = false; needsFit = true;
        if ((map as unknown as { _animatingZoom?: boolean })._animatingZoom) { map.once("zoomend", () => { if (!destroyed) fit(); }); return; }
        fit();
      }
      const zoomBox = container.querySelector<HTMLElement>(".leaflet-control-zoom");
      if (zoomBox) {
        const link = L.DomUtil.create("a", "leaflet-control-zoom-fit", zoomBox);
        link.href = "#";
        link.setAttribute("role", "button");
        link.setAttribute("aria-label", FIT_LABEL);
        link.title = FIT_LABEL;
        link.innerHTML = FIT_ICON;
        L.DomEvent.disableClickPropagation(link);
        L.DomEvent.on(link, "click", (event) => { L.DomEvent.preventDefault(event); fitAll(); });
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
            const icon = L.divIcon({ html: pin, className: "", iconSize: [PIN_BOX, PIN_BOX], iconAnchor: [PIN_BOX / 2, PIN_BOX / 2] });
            const marker = L.marker(point.coordinates, { icon, title: pointLabel(point), alt: pointLabel(point), keyboard: true, riseOnHover: true });
            marker.on("click", () => options.onSelect(point.id));
            marker.addTo(map);
            // The marker's box is wider than the pin: only the pin takes presses (the rest of the box leaves the map draggable).
            const element = marker.getElement();
            if (element) element.style.pointerEvents = "none";
            markers.push({ id: point.id, marker, pin });
          });
          previousData = data;
          relayout();
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
          relayout();
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
        fit: fitAll,
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
