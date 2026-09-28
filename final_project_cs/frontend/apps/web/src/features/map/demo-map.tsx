"use client";

import { useT } from "@/lib/settings";
import type { TripMapProps } from "./trip-map";
import styles from "./demo-map.module.css";

/** Visit-order diagram of the mockup. Explicit provider, never a fallback for a live map. */
export function DemoMap({ stops, selectedId, onSelect }: TripMapProps) {
  const t = useT();
  if (!stops.length) return <p className={styles.empty}>{t("일정을 등록하면 방문 순서가 표시돼요.", "Add stops to see their visit order.")}</p>;
  const height = Math.max(230, Math.ceil(stops.length / 3) * 100 + 24);
  const points = stops.map((stop, index) => {
    const row = Math.floor(index / 3), column = row % 2 ? 2 - index % 3 : index % 3;
    return { stop, index, x: 60 + column * 120, y: 48 + row * 100 };
  });
  return <div className={styles.diagram} style={{ aspectRatio: `360 / ${height}` }}>
    <svg viewBox={`0 0 360 ${height}`} aria-hidden="true" focusable="false"><polyline className={styles.path} points={points.map(({ x, y }) => `${x},${y}`).join(" ")} /></svg>
    <div className={styles.points}>{points.map(({ stop, index, x, y }) => (
      <button key={stop.id} type="button" id={`map-point-${stop.id}`} className={styles.point} style={{ left: `${x / 360 * 100}%`, top: `${y / height * 100}%` }} aria-pressed={selectedId === stop.id} aria-label={`${index + 1}. ${stop.title}`} onClick={() => onSelect(stop.id)}>
        <span className={styles.number}>{index + 1}</span><span className={styles.label}>{stop.title}</span>
      </button>
    ))}</div>
  </div>;
}
