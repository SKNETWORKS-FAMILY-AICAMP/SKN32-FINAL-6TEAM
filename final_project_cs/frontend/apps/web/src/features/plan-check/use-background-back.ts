"use client";

import { useRef, type PointerEvent } from "react";
import { COMMIT_FRACTION } from "./use-day-gestures";

/** 좌측의 빈 배경에서 시작한 가로 스와이프만 취소한다. 입력·버튼·지도 조작은 보존한다. */
export function useBackgroundBack(enabled: boolean, onBack: () => void) {
  const start = useRef<{ id: number; x: number; y: number; locked: boolean } | null>(null);
  return {
    onPointerDown(event: PointerEvent<HTMLDivElement>) {
      start.current = null;
      if (!enabled || !event.isPrimary || event.button !== 0) return;
      const box = event.currentTarget.getBoundingClientRect();
      if (event.clientX - box.left > Math.min(112, box.width * .35)) return;
      if ((event.target as Element).closest('button,a,input,textarea,select,label,summary,[role="button"],[aria-label="여행 지도"]')) return;
      start.current = { id: event.pointerId, x: event.clientX, y: event.clientY, locked: false };
    },
    onPointerMove(event: PointerEvent<HTMLDivElement>) {
      const origin = start.current;
      if (!origin || origin.id !== event.pointerId || !enabled) return;
      const dx = event.clientX - origin.x, dy = event.clientY - origin.y;
      if (!origin.locked && Math.abs(dy) > 8 && Math.abs(dy) >= Math.abs(dx)) { start.current = null; return; }
      if (dx < -8) { start.current = null; return; }
      if (dx > 8 && dx > Math.abs(dy) * 1.4) {
        origin.locked = true;
        event.currentTarget.setPointerCapture(event.pointerId);
        event.preventDefault();
      }
    },
    onPointerUp(event: PointerEvent<HTMLDivElement>) {
      const origin = start.current; start.current = null;
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      if (!enabled || !origin?.locked || origin.id !== event.pointerId) return;
      if (event.clientX - origin.x >= event.currentTarget.clientWidth * COMMIT_FRACTION && Math.abs(event.clientY - origin.y) < (event.clientX - origin.x) / 2) onBack();
    },
    onPointerCancel() { start.current = null; },
  };
}
