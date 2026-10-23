"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { ArrowRight, Layers, ChevronRight, LocateFixed, Minus, Plus, Scan } from "lucide-react";
import { formatDistance, niceScale, type EdgeChip } from "./map-geometry";
import type { MapView } from "./model";
import styles from "./map.module.css";

export const FIT_LABEL = "모든 일정 보기";

/** Room (px) a vertical column of the buttons needs; below it the same buttons stand in a row, and a map too small even for that shows only the fold tab. */
const BUTTON = 44, FOLD = 44, GAP = 8;
export type ControlsLayout = "column" | "row" | "tab";

/**
 * How the buttons stand, for the room the map has above the sheet. ★`[2026-10-05 사용자 선택 — 지도 단추 접기 · 높이에 따라 자동]` The same buttons, the same places in the order: a column while
 * there is height for it, a single row when the customer has made the list tall (the map is low), and only the fold tab when there is no room at all. (Switching does not change the map's own size,
 * so the choice cannot flicker at the border.) Not measured yet: a column.
 * ★`[2026-10-22 사용자 지시 — ST4F-721]` 「내 위치로」 is not one of `count`: it stands on its own at the bottom right (`locatePlace`), so a column or a row also leaves it its room above `bottom`.
 */
export function controlsLayout(room: { width: number; height: number }, top: number, count: number, bottom = 0): ControlsLayout {
  if (!room.width || !room.height) return "column";
  const locate = GAP + BUTTON + bottom;
  const column = BUTTON + count * BUTTON + GAP * count + 24 + top + locate;
  const row = FOLD + count * BUTTON + GAP * count + 24;
  if (room.height >= column) return "column";
  if (room.width >= row && room.height >= top + BUTTON + 24 + locate) return "row";
  return "tab";
}

/**
 * `[2026-10-22 사용자 지시 — ST4F-721]` Where 「내 위치로」 stands: the bottom right corner, above the sheet, while there is height for it under the fold tab; on a map lower than that it stands
 * beside the fold tab (left of it), so the two never cover each other. Not measured yet: the corner.
 */
export function locatePlace(room: { width: number; height: number }, top: number, bottom = 0): "corner" | "beside" {
  if (!room.height) return "corner";
  return room.height >= top + 12 + BUTTON + GAP + BUTTON + 12 + bottom ? "corner" : "beside";
}

export interface MapControlsProps {
  view: MapView | null;
  topInset: number;
  layout: ControlsLayout;
  folded: boolean;
  onFold: (folded: boolean) => void;
  canFit: boolean;
  onZoom: (delta: 1 | -1) => void;
  onFit: () => void;
}

/**
 * `[2026-10-05 사용자 선택]` The map's own buttons, the same over every provider: ＋ · the scale ruler · － · 「모든 일정 보기」, and a small tab that folds them away.
 * The ruler says how far a stretch of the map is (it replaces a zoom number nobody can read); it is left out when the provider cannot say what it shows.
 * 「내 위치로」 is not in the group since 2026-10-22 (ST4F-721) — `LocateControl`.
 */
export function MapControls({ view, topInset, layout, folded, onFold, canFit, onZoom, onFit }: MapControlsProps) {
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const group = useRef<HTMLDivElement>(null);
  const held = useRef(false);
  const folding = useRef(onFold);
  useEffect(() => { folding.current = onFold; }, [onFold]);
  const arm = useCallback(() => {
    clearTimeout(timer.current);
    if (document.querySelector("dialog[open]")) return;
    if (group.current && !folded && !held.current && !group.current?.querySelector(":focus-visible")) timer.current = setTimeout(() => folding.current(true), 5_000);
  }, [folded]);
  useEffect(() => { arm(); return () => clearTimeout(timer.current); }, [arm]);
  const scale = view ? niceScale(view, layout === "row" ? 44 : 32) : null;
  const closed = folded || layout === "tab";
  return <div ref={group} className={styles.controls} data-map-controls data-direction={layout} onPointerEnter={() => { held.current = true; clearTimeout(timer.current); }} onPointerLeave={() => { held.current = false; arm(); }} onPointerDown={arm} onFocusCapture={() => clearTimeout(timer.current)} onBlurCapture={() => { setTimeout(arm, 0); }} data-layout={layout === "row" && !closed ? "row" : "column"} data-folded={closed || undefined} role="group" aria-label="지도 단추" style={{ top: `${topInset + 12}px` }}>
    <MapTool className={styles.fold} label={closed ? "지도 단추 펼치기" : "지도 단추 접기"} expanded={!closed} onClick={() => onFold(!folded)}>
      <span className={styles.foldArrow} aria-hidden="true"><ChevronRight size={14} /></span>
      {scale && <span className={styles.scaleValue} role="img" aria-label={`거리 눈금 ${scale.label}`}>{scale.label}</span>}</MapTool>
    {!closed && <>
      <MapTool className={styles.round} label="확대" onClick={() => onZoom(1)}><Plus size={19} strokeWidth={2.2} aria-hidden="true" /></MapTool>
      <MapTool className={styles.round} label="축소" onClick={() => onZoom(-1)}><Minus size={19} strokeWidth={2.2} aria-hidden="true" /></MapTool>
      {canFit && <MapTool className={styles.round} label={FIT_LABEL} onClick={onFit}><Scan size={18} strokeWidth={2} aria-hidden="true" /></MapTool>}
    </>}
  </div>;
}

/**
 * `[2026-10-22 사용자 지시 — ST4F-721]` 「내 위치로」 on its own, out of the folding group: always shown at the bottom right of the map above the sheet (`locatePlace`), however the group stands.
 * Pins, edge chips and route labels keep clear of it (`data-map-obstacle`). The entry stays available before consent and after a failed fix.
 */
export function LocateControl({ place, topInset, bottomInset, me, onLocate }: { place: "corner" | "beside"; topInset: number; bottomInset: number; me: "off" | "waiting" | "ready"; onLocate: () => void }) {
  const spot = place === "corner" ? { bottom: `${bottomInset + 12}px` } : { top: `${topInset + 12}px`, marginRight: `${FOLD + GAP}px` };
  return <div className={styles.locate} data-map-locate data-map-obstacle data-place={place} style={spot}>
    <MapTool className={styles.round} label="내 위치로" hint={me === "off" ? "내 위치로 · 위치 이용 동의" : me === "waiting" ? "내 위치로 · 위치 다시 찾기" : undefined} onClick={onLocate}><LocateFixed size={18} strokeWidth={2} aria-hidden="true" /></MapTool>
  </div>;
}

/**
 * `[2026-10-05 사용자 선택 — 가장자리 마커 안 B]` A stop that is out of view stands at the edge of the map as a chip pointing at it, with the distance (stops close together share one chip: 「③ ④ · 1.2km」).
 * Pressing it takes the map there and selects the stop.
 */
export function EdgeChips({ chips, width, moving = false, onGo, onLayout }: { chips: readonly EdgeChip[]; width: number; moving?: boolean; onGo: (ids: string[]) => void; onLayout?: () => void }) {
  return <>{chips.map((chip) => <EdgeChipButton key={chip.ids.join(",")} chip={chip} width={width} moving={moving} onGo={onGo} onLayout={onLayout} />)}</>;
}

/** The air (px) a chip keeps from the sides of the map. */
const CHIP_AIR = 0;

/**
 * One chip. ★`[2026-10-07 사용자 지적]` A chip that names several stops (「2 · 3 · 4 · 5 · 62km」) is wider than the 92 px the geometry reserves for one, and stood half out of the map at its left or right edge (the frame cuts what
 * passes the edge): its own width is measured and it is moved in until all of it shows. The chip stays where the geometry put it in the other direction.
 */
function EdgeChipButton({ chip, width, moving, onGo, onLayout }: { chip: EdgeChip; width: number; moving: boolean; onGo: (ids: string[]) => void; onLayout?: () => void }) {
  const button = useRef<HTMLButtonElement>(null);
  const [half, setHalf] = useState(0);
  const names = chip.labels.join(" · ");
  const far = formatDistance(chip.distanceM);
  const side = chip.x < width / 2 ? "left" : "right";
  useLayoutEffect(() => { const measured = button.current?.getBoundingClientRect().width ?? 0; if (measured / 2 !== half) setHalf(measured / 2); else onLayout?.(); }, [names, far, half, moving, chip.crowded, onLayout]);
  const edgeX = chip.x >= width - 47 ? width - half - CHIP_AIR : chip.x <= 47 ? half + CHIP_AIR : chip.x;
  const left = half > 0 && width > half * 2 + CHIP_AIR * 2 ? Math.min(width - half - CHIP_AIR, Math.max(half + CHIP_AIR, edgeX)) : chip.x;
  return <button ref={button} type="button" className={styles.edgeChip} style={{ left: `${left}px`, top: `${chip.y}px` }} data-edge-chip data-side={side} data-crowded={chip.crowded || undefined} data-multiple={chip.ids.length >= 3 || undefined}
    title={chip.crowded ? `${names}번 일정 · ${far}` : undefined}
    aria-label={`${names}번 일정이 화면 밖에 있어요 · ${far} · 누르면 그곳으로 가요`} onClick={() => onGo(chip.ids)}>
    <ArrowRight size={13} strokeWidth={2.4} style={{ transform: `rotate(${Math.round(chip.angle)}deg)` }} aria-hidden="true" />
    <span className={styles.edgeNumbers} aria-hidden="true">{chip.ids.length >= 3 ? <><Layers size={14} strokeWidth={1.8} /><span>×{chip.ids.length}</span></> : names}</span>{!moving && <small aria-hidden="true">{far}</small>}
  </button>;
}


function MapTool({ label, hint, children, className, onClick, expanded, disabled }: {
  label: string; hint?: string; children: ReactNode; className: string; onClick: () => void; expanded?: boolean; disabled?: boolean;
}) {
  const id = useId();
  return <button type="button" className={className} data-map-obstacle={expanded !== undefined || undefined} aria-label={label} aria-describedby={id} aria-expanded={expanded} aria-disabled={disabled || undefined} onClick={onClick}>
    {children}<span id={id} role="tooltip" className={styles.toolTip}>{hint ?? label}</span>
  </button>;
}
