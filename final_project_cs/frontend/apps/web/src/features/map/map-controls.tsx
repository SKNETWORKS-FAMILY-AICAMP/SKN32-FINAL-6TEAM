"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { ArrowRight, ChevronRight, LocateFixed, Minus, Plus, Scan } from "lucide-react";
import { formatDistance, niceScale, type EdgeChip } from "./map-geometry";
import type { MapView } from "./model";
import styles from "./map.module.css";

export const FIT_LABEL = "모든 일정 보기";

/** Room (px) a vertical column of the buttons needs; below it the same buttons stand in a row, and a map too small even for that shows only the fold tab. */
const BUTTON = 40, FOLD = 44, GAP = 8;
export type ControlsLayout = "column" | "row" | "tab";

/**
 * How the buttons stand, for the room the map has above the sheet. ★`[2026-10-05 사용자 선택 — 지도 단추 접기 · 높이에 따라 자동]` The same buttons, the same places in the order: a column while
 * there is height for it, a single row when the customer has made the list tall (the map is low), and only the fold tab when there is no room at all. (Switching does not change the map's own size,
 * so the choice cannot flicker at the border.) Not measured yet: a column.
 */
export function controlsLayout(room: { width: number; height: number }, top: number, count: number): ControlsLayout {
  if (!room.width || !room.height) return "column";
  const column = BUTTON + count * BUTTON + GAP * count + 24 + top;
  const row = FOLD + count * BUTTON + GAP * count + 24;
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
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const group = useRef<HTMLDivElement>(null);
  const held = useRef(false);
  const folding = useRef(onFold);
  useEffect(() => { folding.current = onFold; }, [onFold]);
  const arm = useCallback(() => {
    clearTimeout(timer.current);
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
      {me !== "off" && <MapTool className={styles.round} label="내 위치로" hint={me === "waiting" ? "내 위치를 아직 읽지 못했어요" : undefined} disabled={me === "waiting"} onClick={() => { if (me === "ready") onLocate(); }}><LocateFixed size={18} strokeWidth={2} aria-hidden="true" /></MapTool>}
    </>}
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
  const visibleNames = chip.labels.length > 3 ? `${chip.labels.slice(0, 2).join(" · ")} +${chip.labels.length - 2}` : names;
  useLayoutEffect(() => { const measured = button.current?.offsetWidth ?? 0; if (measured / 2 !== half) setHalf(measured / 2); else onLayout?.(); }, [names, far, half, moving, onLayout]);
  const edgeX = chip.x >= width - 47 ? width - half - CHIP_AIR : chip.x <= 47 ? half + CHIP_AIR : chip.x;
  const left = half > 0 && width > half * 2 + CHIP_AIR * 2 ? Math.min(width - half - CHIP_AIR, Math.max(half + CHIP_AIR, edgeX)) : chip.x;
  return <button ref={button} type="button" className={styles.edgeChip} style={{ left: `${left}px`, top: `${chip.y}px` }} data-edge-chip
    aria-label={`${names}번 일정이 화면 밖에 있어요 · ${far} · 누르면 그곳으로 가요`} onClick={() => onGo(chip.ids)}>
    <ArrowRight size={13} strokeWidth={2.4} style={{ transform: `rotate(${Math.round(chip.angle)}deg)` }} aria-hidden="true" />
    <span className={styles.edgeNumbers} aria-hidden="true">{visibleNames}</span>{!moving && <small aria-hidden="true">{far}</small>}
  </button>;
}


function MapTool({ label, hint, children, className, onClick, expanded, disabled }: {
  label: string; hint?: string; children: ReactNode; className: string; onClick: () => void; expanded?: boolean; disabled?: boolean;
}) {
  const id = useId();
  return <button type="button" className={className} aria-label={label} aria-describedby={id} aria-expanded={expanded} aria-disabled={disabled || undefined} onClick={onClick}>
    {children}<span id={id} role="tooltip" className={styles.toolTip}>{hint ?? label}</span>
  </button>;
}
