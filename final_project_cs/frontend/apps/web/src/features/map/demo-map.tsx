import type { CSSProperties } from "react";
import { MapPin } from "lucide-react";
import type { TripMapProps } from "./trip-map";
import styles from "./demo-map.module.css";

/** Explicit diagram provider. It is never a fallback for an unavailable live map. */
export function DemoMap({ stops, selectedId, dayNumber, onSelect }: TripMapProps) {
  const rows = Math.max(2, Math.ceil(stops.length / 2));
  return <div className={styles.map}>
    <div className={styles.mapheading}><MapPin size={18} aria-hidden="true" /><strong>{dayNumber}일차 장소</strong><small>{stops.length}곳 · 방문 순서 표시</small></div>
    <div className={styles.pins} role="group" aria-label="일정 장소 핀 · 예시 배치" style={{ minHeight: `${Math.max(250, rows * 65)}px` }}>
      {stops.map((stop, index) => {
        const left = index % 2 === 0 ? 24 : 76;
        const top = 10 + Math.floor(index / 2) * (76 / (rows - 1));
        return <button type="button" key={stop.id} className={styles.pin} style={{ "--pin-left": `${left}%`, "--pin-top": `${top}%` } as CSSProperties} aria-label={`${index + 1}. ${stop.title} 지도에서 선택`} aria-pressed={selectedId === stop.id} onClick={() => onSelect(stop.id)}>{index + 1}<span aria-hidden="true">{stop.title}</span></button>;
      })}
      {stops.length === 0 && <p className={styles.empty}>이 날짜에 등록한 장소가 없어요.</p>}
    </div>
    <p className={styles.mapcaption}>위치 개념도 · 실제 지도와 경로가 아닌 예시 배치</p>
  </div>;
}
