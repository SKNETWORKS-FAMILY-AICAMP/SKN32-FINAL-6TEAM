"use client";

import type { RouteShapes } from "@/lib/live/route-shapes";
import { locationFailureText } from "@/lib/location";
import { useT } from "@/lib/settings";
import { useAppToast } from "@/components/app-toast";
import { LocationConsent } from "./location-consent";
import type { TripStop } from "../trip/model";
import type { MapViewProps, MyLocation, PinLook } from "./model";
import { mapConfiguration } from "./config";
import { useEffect, useMemo, useRef, useState } from "react";
import { GoogleMap, type GoogleDecision } from "./google-map";
import { MapUnavailable } from "./live-map";
import { toMapPoints } from "./map-points";
import { routeNotes, toMapLines, visibleShapes } from "./route-lines";
import { NaverMap } from "./naver-map";
import { OsmMap } from "./osm-map";
import { useLocationSamples, useLocationStays, useMeOnMap, useMyLocation } from "./use-my-location";
import styles from "./map.module.css";

export interface TripMapProps {
  coordinatePick?: MapViewProps["coordinatePick"];
  stops: TripStop[];
  selectedId?: string;
  dayNumber: number;
  onSelect: (stopId: string) => void;
  /** Pins with their own label or look, by stop id (`PinLook`). */
  looks?: Record<string, PinLook>;
  /** `fill` — fills its box with no caption (a screen that says what is unplaced itself); default — framed with a caption. */
  variant?: "framed" | "fill";
  /** `[2026-10-04]` Route lines from the server (`route-shapes`) — drawn for the stops shown; the caption says what they mean (and the data source, ODbL). */
  routes?: RouteShapes | null;
  /** The lines could not be read (not "there are none"): said in the caption, the pins still show. */
  routesError?: string;
  /** `[2026-10-04]` Px at the top of the map that a bar floats over (`MapViewProps.topInset`). */
  topInset?: number;
  /** `[2026-10-05]` Px at the bottom that a sheet floats over (`MapViewProps.bottomInset`). */
  bottomInset?: number;
  /**
   * `[2026-10-05 사용자 지시]` The trip this map belongs to — only a trip's own screen gives it. With it (and the location consent) the positions the
   * map reads go to the server, and the places the server found the customer stayed are drawn. Without it (the plan check) only 「내 위치」 shows.
   */
  tripId?: string;
  /** `[2026-10-05]` The day shown ("YYYY-MM-DD"): only the stays of that day are drawn. */
  date?: string;
  /** `[2026-10-05 사용자 지시]` The zoom level of the map (see `MapViewProps.onZoom`): the screen asks for the detailed route lines when it is zoomed in. */
  onZoom?: (zoom: number) => void;
  onInteractionChange?: (active: boolean) => void;
  /** `[2026-10-06 사용자 지시]` A route line was pressed (the id of its `RouteShape.itemId`) and which one the screen shows as picked. */
  onSelectLine?: (lineId: string) => void;
  selectedLineId?: string;
}

export function TripMap(props: TripMapProps) {
  const t = useT();
  const [google, setGoogle] = useState<GoogleDecision>("checking");
  // ★`[2026-10-05 사용자 지시]` 「내 위치」 — read as soon as the map is on the page, only with the location consent (`useMyLocation`).
  const available = mapConfiguration.provider !== "unavailable";
  const { fix, failure, agreed, locate } = useMyLocation(available);
  const { show: showToast, node: toastNode } = useAppToast();
  const [pendingLocate, setPendingLocate] = useState<((location: MyLocation) => void) | null>(null);
  const [askingConsent, setAskingConsent] = useState(false);
  const notifiedFailure = useRef<typeof failure>(null);
  useEffect(() => {
    if (!failure) {
      if (notifiedFailure.current && fix && !pendingLocate) showToast({ text: t("내 위치를 찾았어요", "Your location is ready") });
      notifiedFailure.current = null; return;
    }
    if (pendingLocate || notifiedFailure.current === failure) return;
    notifiedFailure.current = failure;
    showToast({ text: locationFailureText(failure, t, "map"), stay: true });
  }, [failure, fix, pendingLocate, showToast, t]);
  useEffect(() => {
    if (agreed || askingConsent || !pendingLocate) return;
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) setPendingLocate(null); });
    return () => { cancelled = true; };
  }, [agreed, askingConsent, pendingLocate]);
  useEffect(() => {
    if (!agreed || !pendingLocate) return;
    let cancelled = false;
    void locate().then(result => {
      if (cancelled) return;
      if (result?.ok) { pendingLocate({ coordinates: { lat: result.fix.lat, lng: result.fix.lng }, accuracyM: result.fix.accuracyM }); showToast({ text: t("내 위치로 이동했어요", "Moved to your location") }); }
      else if (result) { notifiedFailure.current = result.reason; showToast({ text: locationFailureText(result.reason, t, "map"), stay: true }); }
      setPendingLocate(null);
    });
    return () => { cancelled = true; };
  }, [agreed, pendingLocate, locate, showToast, t]);
  const me = useMeOnMap(fix);
  useLocationSamples(available ? props.tripId : undefined, fix, agreed);
  // The screen makes a new stop list on each render: the names are kept by their content, so the stays are not drawn again for nothing.
  const titlesKey = JSON.stringify(props.stops.map((stop) => [stop.id, stop.title]));
  const titles = useMemo(() => Object.fromEntries(JSON.parse(titlesKey) as [string, string][]), [titlesKey]);
  const stays = useLocationStays(available ? props.tripId : undefined, agreed, props.date, titles);
  if (mapConfiguration.provider === "unavailable") return <MapUnavailable message={mapConfiguration.message} />;
  const points = toMapPoints(props.stops, props.looks);
  const missing = props.stops.length - points.length;
  const selectedMissing = props.selectedId && props.stops.some((stop) => stop.id === props.selectedId) && !points.some((point) => point.id === props.selectedId);
  const shapes = visibleShapes(props.routes?.shapes, props.stops);
  const lines = toMapLines(shapes);
  const viewProps = { points, selectedId: props.selectedId, onSelect: props.onSelect, lines, onSelectLine: props.onSelectLine, selectedLineId: props.selectedLineId, topInset: props.topInset, bottomInset: props.bottomInset, me, stays, onZoom: props.onZoom, onInteractionChange: props.onInteractionChange, meAvailable: agreed,
    onRequestLocation: (onLocated: (location: MyLocation) => void) => { setPendingLocate(() => onLocated); if (!agreed) setAskingConsent(true); } };
  const fill = props.variant === "fill";
  return <div className={`${styles.frame} ${fill ? styles.fill : ""}`} style={fill ? { position: "relative", display: "flex", flexDirection: "column", height: "100%", minHeight: 0, flex: 1 } : undefined}>
    {mapConfiguration.provider === "naver" ? <NaverMap {...viewProps} coordinatePick={props.coordinatePick} clientId={mapConfiguration.clientId} />
      : mapConfiguration.provider === "osm" ? <OsmMap {...viewProps} coordinatePick={props.coordinatePick} tileUrl={mapConfiguration.tileUrl} />
      : <GoogleMap {...viewProps} coordinatePick={props.coordinatePick} apiKey={mapConfiguration.apiKey} mapId={mapConfiguration.mapId} tileUrl={mapConfiguration.tileUrl} onDecided={setGoogle} />}
    {toastNode}
    {askingConsent && <LocationConsent onAgreed={() => setAskingConsent(false)} onCancel={() => { setAskingConsent(false); setPendingLocate(null); }} />}
    {!fill && <p className={styles.caption}>
      <span>{providerName(mapConfiguration.provider, google)} · {props.dayNumber}일차 · {points.length}개 장소 표시</span>
      {mapConfiguration.provider === "google" && google === "free" && <span className={styles.notice}>구글 지도 사용 한도에 닿았거나 확인하지 못해 무료 지도(OpenStreetMap)로 보여 드려요.</span>}
      {lines.length > 0 && <span className={styles.notice} data-route-attribution>{props.routes?.attribution}</span>}
      {routeNotes(shapes).map((note) => <span key={note} className={styles.notice}>{note}</span>)}
      {props.routesError && <span className={styles.notice} role="status">{props.routesError}</span>}
      {missing > 0 && <span className={styles.notice}>좌표가 없는 {missing}개 일정은 핀으로 표시하지 않았어요.</span>}
      {selectedMissing && <span className={styles.notice}>선택한 일정의 위치 정보가 없어요.</span>}
    </p>}
  </div>;
}

function providerName(provider: "naver" | "osm" | "google", google: GoogleDecision) {
  if (provider === "naver") return "네이버지도";
  if (provider === "osm" || google === "free" || google === "free-setting") return "OpenStreetMap";
  return "Google Maps";
}
