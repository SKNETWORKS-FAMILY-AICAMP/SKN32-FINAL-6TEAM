"use client";

import type { TripStop } from "../trip/model";
import { mapConfiguration } from "./config";
import { DemoMap } from "./demo-map";
import { GoogleMap } from "./google-map";
import { MapUnavailable } from "./live-map";
import { toMapPoints } from "./map-points";
import { NaverMap } from "./naver-map";
import styles from "./map.module.css";

export interface TripMapProps {
  stops: TripStop[];
  selectedId?: string;
  dayNumber: number;
  onSelect: (stopId: string) => void;
}

export function TripMap(props: TripMapProps) {
  if (mapConfiguration.provider === "demo") return <DemoMap {...props} />;
  if (mapConfiguration.provider === "unavailable") return <MapUnavailable message={mapConfiguration.message} />;
  const points = toMapPoints(props.stops);
  const missing = props.stops.length - points.length;
  const selectedMissing = props.selectedId && props.stops.some((stop) => stop.id === props.selectedId) && !points.some((point) => point.id === props.selectedId);
  const viewProps = { points, selectedId: props.selectedId, onSelect: props.onSelect };
  return <div className={styles.frame}>
    {mapConfiguration.provider === "naver"
      ? <NaverMap {...viewProps} clientId={mapConfiguration.clientId} />
      : <GoogleMap {...viewProps} apiKey={mapConfiguration.apiKey} mapId={mapConfiguration.mapId} />}
    <p className={styles.caption}>
      <span>{mapConfiguration.provider === "naver" ? "네이버지도" : "Google Maps"} · {props.dayNumber}일차 · {points.length}개 장소 표시</span>
      {missing > 0 && <span className={styles.notice}>좌표가 없는 {missing}개 일정은 핀으로 표시하지 않았어요.</span>}
      {selectedMissing && <span className={styles.notice}>선택한 일정의 위치 정보가 없어요.</span>}
    </p>
  </div>;
}
