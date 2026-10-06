import type { MapAdapter, MapLine, MapPoint, MyLocation, StayPoint } from "../model";
import { lineStyle, linesKey } from "./lines";
import { ACCURACY_STYLE, accuracyRadius, createMeDot, createStayDot, ME_BOX, meKey, STAY_BOX, staysKey } from "./me";
import { createPin, geometryKey, layoutPins, PIN_BOX, placePin, pointLabel, pulsePin, setPinSelected, type PinSlot } from "./pin";

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
      // ★`[2026-10-05 사용자 선택]` The map's buttons (+ − the scale ruler, all stops, my place) are drawn by the page over every provider the same way (`map-controls.tsx`): no Leaflet control here.
      const map = L.map(container, { center: options.points[0]?.coordinates ?? SEOUL, zoom: 14, minZoom: 3, maxZoom: 18, zoomControl: false });
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
      let centredOnMe = false;           // [2026-10-05] an empty map is centred on the customer once; pins (a different set of them) reset it
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
      // [2026-10-05] The zoom level goes to the screen (it asks for the detailed route lines when zoomed in).
      const sayZoom = () => options.onZoom?.(map.getZoom());
      map.on("zoomend", sayZoom);
      sayZoom();
      // [2026-10-05] What the map shows goes to the screen, for the scale ruler and the chips of the stops out of view.
      const sayView = () => {
        if (destroyed || !container.clientWidth || !container.clientHeight) return;
        const bounds = map.getBounds();
        options.onView?.({ south: bounds.getSouth(), west: bounds.getWest(), north: bounds.getNorth(), east: bounds.getEast(), width: container.clientWidth, height: container.clientHeight, zoom: map.getZoom() });
      };
      map.on("moveend zoomend resize", sayView);

      // ★`[2026-10-05 사용자 지시]` 「내 위치」: a dot under the pins (a marker that takes no press) and the accuracy circle in the vector layer.
      let me: MyLocation | null = null;
      let meMarker: ReturnType<typeof L.marker> | null = null;
      let meCircle: ReturnType<typeof L.circle> | null = null;
      let previousMe = "";
      const stayLayer = L.layerGroup().addTo(map);
      let previousStays = "";

      function fit() {
        if (!needsFit || !container.clientWidth || !container.clientHeight) return;
        // ★`[2026-10-05]` Leaflet drops a new view while a zoom animation runs (`_animatingZoom`), and a map's first fit is such an animation (zoom 14 → the pins' zoom):
        //   a day opened in the quarter second after it kept the old view. A fit that comes then waits for the animation to end (found with an empty day that never
        //   centred on 「내 위치」 - its `setView` had been dropped).
        if ((map as unknown as { _animatingZoom?: boolean })._animatingZoom) { map.once("zoomend", () => { if (!destroyed) fit(); }); return; }
        // `[2026-10-05]` No pins:the customer's own position is the picture (once — the map does not chase them); nothing at all: wait.
        if (!points.length) {
          if (!me) return;
          needsFit = false;
          centredOnMe = true;
          programmatic = true;
          try { map.setView(me.coordinates, 15); } finally { programmatic = false; }
          return;
        }
        needsFit = false;
        programmatic = true;
        try {
          if (points.length === 1) map.setView(points[0].coordinates, 15);
          else map.fitBounds(L.latLngBounds(points.map(({ coordinates }) => [coordinates.lat, coordinates.lng] as [number, number])), { paddingTopLeft: [50, 50 + (options.topInset ?? 0)], paddingBottomRight: [50, 50] });
        } finally { programmatic = false; }
      }

      // ★`[2026-10-04 사용자 지시]` 「모든 일정 보기」: every pin back in view, at the place and zoom the map first showed them.
      //   ★Leaflet silently drops a new view while a zoom animation is running (`_animatingZoom`; `fitBounds` answers "done" without moving), so a press that comes a quarter
      //   of a second after +/- would do nothing - it waits for the zoom to end and then fits.
      function fitAll() {
        userMoved = false; needsFit = true;
        fit();                                                       // (it waits by itself while a zoom animation runs)
      }
      // `[2026-10-05 사용자 선택 — 첫 지도 시점 안 C]` A day is shown whole and its first stop is pointed out once, when the camera has come to rest.
      let pulseTimer: ReturnType<typeof setTimeout> | undefined;
      function pulseFirst() {
        clearTimeout(pulseTimer);
        pulseTimer = setTimeout(() => {
          if (destroyed) return;
          const first = points.find((point) => point.order === 1 && !point.tone);
          const marker = first && markers.find((entry) => entry.id === first.id);
          if (marker) pulsePin(marker.pin);
        }, 900);
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
          centredOnMe = false;          // [2026-10-05] a different set of pins: an empty day after it centres on the customer again
          userMoved = false;            // different pins: the old view means nothing
          fit();
          relayout();
          pulseFirst();
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
        if (!next) {
          meMarker?.remove(); meCircle?.remove();
          meMarker = meCircle = null;
          return;
        }
        const at: [number, number] = [next.coordinates.lat, next.coordinates.lng];
        if (meMarker) meMarker.setLatLng(at);
        else {
          const icon = L.divIcon({ html: createMeDot(), className: "", iconSize: [ME_BOX, ME_BOX], iconAnchor: [ME_BOX / 2, ME_BOX / 2] });
          // Not interactive and far under the pins (`zIndexOffset`): a pin on top of it is pressed, never the dot.
          meMarker = L.marker(at, { icon, interactive: false, keyboard: false, zIndexOffset: -1000 }).addTo(map);
          const element = meMarker.getElement();
          if (element) element.style.pointerEvents = "none";
        }
        const radius = accuracyRadius(next);
        if (radius === null) { meCircle?.remove(); meCircle = null; }
        else if (meCircle) { meCircle.setLatLng(at); meCircle.setRadius(radius); }
        else {
          meCircle = L.circle(at, { radius, interactive: false, color: ACCURACY_STYLE.color, weight: ACCURACY_STYLE.weight, opacity: ACCURACY_STYLE.opacity,
            fillColor: ACCURACY_STYLE.color, fillOpacity: ACCURACY_STYLE.fillOpacity, className: "my-location-accuracy" }).addTo(map);
        }
        if (!points.length && !centredOnMe) needsFit = true;          // [2026-10-05] a map that never had pins was never fitted: the first position it learns centres it, once
        if (!points.length && needsFit) fit();
      }

      function setStays(stays: StayPoint[]) {
        if (destroyed) return;
        const key = staysKey(stays);
        if (key === previousStays) return;
        previousStays = key;
        stayLayer.clearLayers();
        stays.forEach((stay) => {
          const icon = L.divIcon({ html: createStayDot(stay), className: "", iconSize: [STAY_BOX, STAY_BOX], iconAnchor: [STAY_BOX / 2, STAY_BOX / 2] });
          const marker = L.marker(stay.coordinates, { icon, interactive: false, keyboard: false, zIndexOffset: -2000 }).addTo(stayLayer);
          const element = marker.getElement();
          if (element) element.style.pointerEvents = "none";
        });
      }

      // `[2026-10-05]` 「내 위치」 button: the camera to the customer, at least street level, and from then on the customer's own camera.
      function centerOn(at: { lat: number; lng: number }, keepZoom = false) {
        if (destroyed) return;
        // Leaflet drops a new view while a zoom animation runs: wait for it to end.
        if ((map as unknown as { _animatingZoom?: boolean })._animatingZoom) { map.once("zoomend", () => centerOn(at, keepZoom)); return; }
        userMoved = true;
        if (keepZoom) map.panTo([at.lat, at.lng]);
        else map.setView([at.lat, at.lng], Math.max(map.getZoom(), 15));
      }

      try { update(options.points, options.selectedId, options.lines); setMe(options.me ?? null); setStays(options.stays ?? []); }
      catch (error) { clearMarkers(); map.remove(); throw error; }
      sayView();

      return {
        update,
        setMe,
        setStays,
        fit: fitAll,
        zoomBy(delta) { if (!destroyed) { if (delta > 0) map.zoomIn(); else map.zoomOut(); } },
        centerOn,
        resize() {
          if (destroyed || !container.clientWidth || !container.clientHeight) return;
          map.invalidateSize();
          if (!userMoved) needsFit = true;
          fit();
        },
        destroy() {
          if (destroyed) return;
          destroyed = true;
          clearTimeout(pulseTimer);
          clearMarkers();
          map.remove();
          container.replaceChildren();
        },
      };
    },
  };
}
