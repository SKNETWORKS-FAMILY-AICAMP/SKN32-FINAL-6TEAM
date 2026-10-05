"use client";

import { ArrowRight, ChevronLeft, ChevronRight, LocateFixed, Minus, Plus, Scan } from "lucide-react";
import { edgeChips, formatDistance, niceScale } from "./map-geometry";
import type { MapPoint, MapView } from "./model";
import styles from "./map.module.css";

export const FIT_LABEL = "모든 일정 보기";

/** Room (px) a vertical column of the buttons needs; below it the same buttons stand in a row, and a map too small even for that shows only the fold tab. */
const BUTTON = 40, FOLD = 28, SCALE = 40, GAP = 8;
export type ControlsLayout = "column" | "row" | "tab";

/**
 * How the buttons stand, for the room the map has above the sheet. ★`[2026-10-05 사용자 선택 — 지도 단추 접기 · 높이에 따라 자동]` The same buttons, the same places in the order: a column while
 * there is height for it, a single row when the customer has made the list tall (the map is low), and only the fold tab when there is no room at all. (Switching does not change the map's own size,
 * so the choice cannot flicker at the border.) Not measured yet: a column.
 */
export function controlsLayout(room: { width: number; height: number }, top: number, count: number): ControlsLayout {
  if (!room.width || !room.height) return "column";
  const column = FOLD + count * BUTTON + SCALE + GAP * (count + 1) + 12 + top;
  const row = FOLD + (count + 1) * BUTTON + GAP * (count + 2) + 24;
  if (room.height >= column) return "column";
  if (room.width >= row && room.height >= top + BUTTON + 24) return "row";
  return "tab";
}

export interface MapControlsProps {
  view: MapView | null;
  topInset: number;
  layout: ControlsLayout;
  folded: boolean;
  onFold: (folded: boolean) => void;
  canFit: boolean;
  /** `off`: the customer never agreed to share their place - no button, no word; `waiting`: agreed, no fix yet; `ready`: the button works. */
  me: "off" | "waiting" | "ready";
  onZoom: (delta: 1 | -1) => void;
  onFit: () => void;
  onLocate: () => void;
}

/**
 * `[2026-10-05 사용자 선택]` The map's own buttons, the same over every provider: ＋ · the scale ruler · － · 「모든 일정 보기」 · 「내 위치」, and a small tab that folds them away.
 * The ruler says how far a stretch of the map is (it replaces a zoom number nobody can read); it is left out when the provider cannot say what it shows.
 */
export function MapControls({ view, topInset, layout, folded, onFold, canFit, me, onZoom, onFit, onLocate }: MapControlsProps) {
  const scale = view ? niceScale(view, layout === "row" ? 44 : 32) : null;
  const closed = folded || layout === "tab";
  return <div className={styles.controls} data-layout={layout === "row" && !closed ? "row" : "column"} data-folded={closed || undefined} role="group" aria-label="지도 단추" style={{ top: `${topInset + 12}px` }}>
    <button type="button" className={styles.fold} aria-expanded={!closed} aria-label={closed ? "지도 단추 펼치기" : "지도 단추 접기"} title={closed ? "지도 단추 펼치기" : "지도 단추 접기"} onClick={() => onFold(!folded)}>
      {closed ? <ChevronLeft size={16} strokeWidth={2.2} aria-hidden="true" /> : <ChevronRight size={16} strokeWidth={2.2} aria-hidden="true" />}</button>
    {!closed && <>
      <button type="button" className={styles.round} aria-label="확대" title="확대" onClick={() => onZoom(1)}><Plus size={19} strokeWidth={2.2} aria-hidden="true" /></button>
      {scale && <div className={styles.scale} role="img" aria-label={`거리 눈금 ${scale.label}`} title={`이 막대의 길이가 약 ${scale.label}예요`}>
        <span className={styles.scaleBar} style={{ width: `${Math.max(8, scale.px)}px` }} aria-hidden="true" /><span aria-hidden="true">{scale.label}</span></div>}
      <button type="button" className={styles.round} aria-label="축소" title="축소" onClick={() => onZoom(-1)}><Minus size={19} strokeWidth={2.2} aria-hidden="true" /></button>
      {canFit && <button type="button" className={styles.round} aria-label={FIT_LABEL} title={FIT_LABEL} onClick={onFit}><Scan size={18} strokeWidth={2} aria-hidden="true" /></button>}
      {me !== "off" && <button type="button" className={styles.round} aria-label="내 위치로" title={me === "ready" ? "내 위치로" : "내 위치를 아직 읽지 못했어요"} aria-disabled={me === "waiting" || undefined}
        onClick={() => { if (me === "ready") onLocate(); }}><LocateFixed size={18} strokeWidth={2} aria-hidden="true" /></button>}
    </>}
  </div>;
}

/**
 * `[2026-10-05 사용자 선택 — 가장자리 마커 안 B]` A stop that is out of view stands at the edge of the map as a chip pointing at it, with the distance (stops close together share one chip: 「③ ④ · 1.2km」).
 * Pressing it takes the map there and selects the stop.
 */
export function EdgeChips({ view, points, topInset, bottomInset, keepRight, onGo }: { view: MapView | null; points: readonly MapPoint[]; topInset: number; bottomInset: number; keepRight: number; onGo: (ids: string[]) => void }) {
  if (!view) return null;
  return <>{edgeChips(view, points, { top: topInset, bottom: bottomInset, rightKeep: keepRight }).map((chip) => {
    const names = chip.labels.join(" · ");
    const far = formatDistance(chip.distanceM);
    return <button key={chip.ids.join(",")} type="button" className={styles.edgeChip} style={{ left: `${chip.x}px`, top: `${chip.y}px` }} data-edge-chip
      aria-label={`${names}번 일정이 화면 밖에 있어요 · ${far} · 누르면 그곳으로 가요`} onClick={() => onGo(chip.ids)}>
      <ArrowRight size={13} strokeWidth={2.4} style={{ transform: `rotate(${Math.round(chip.angle)}deg)` }} aria-hidden="true" />
      <span aria-hidden="true">{names}</span><small aria-hidden="true">{far}</small>
    </button>;
  })}</>;
}
