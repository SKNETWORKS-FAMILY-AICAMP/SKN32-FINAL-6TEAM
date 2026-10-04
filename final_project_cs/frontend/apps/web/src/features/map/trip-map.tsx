"use client";

import type { RouteShapes } from "@/lib/live/route-shapes";
import type { TripStop } from "../trip/model";
import type { PinLook } from "./model";
import { mapConfiguration } from "./config";
import { useState } from "react";
import { GoogleMap, type GoogleDecision } from "./google-map";
import { MapUnavailable } from "./live-map";
import { toMapPoints } from "./map-points";
import { routeNotes, toMapLines, visibleShapes } from "./route-lines";
import { NaverMap } from "./naver-map";
import { OsmMap } from "./osm-map";
import styles from "./map.module.css";

export interface TripMapProps {
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
}

export function TripMap(props: TripMapProps) {
  const [google, setGoogle] = useState<GoogleDecision>("checking");
  if (mapConfiguration.provider === "unavailable") return <MapUnavailable message={mapConfiguration.message} />;
  const points = toMapPoints(props.stops, props.looks);
  const missing = props.stops.length - points.length;
  const selectedMissing = props.selectedId && props.stops.some((stop) => stop.id === props.selectedId) && !points.some((point) => point.id === props.selectedId);
  const shapes = visibleShapes(props.routes?.shapes, props.stops);
  const lines = toMapLines(shapes);
  const viewProps = { points, selectedId: props.selectedId, onSelect: props.onSelect, lines, topInset: props.topInset };
  const fill = props.variant === "fill";
  return <div className={`${styles.frame} ${fill ? styles.fill : ""}`}>
    {mapConfiguration.provider === "naver" ? <NaverMap {...viewProps} clientId={mapConfiguration.clientId} />
      : mapConfiguration.provider === "osm" ? <OsmMap {...viewProps} tileUrl={mapConfiguration.tileUrl} />
      : <GoogleMap {...viewProps} apiKey={mapConfiguration.apiKey} mapId={mapConfiguration.mapId} tileUrl={mapConfiguration.tileUrl} onDecided={setGoogle} />}
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
