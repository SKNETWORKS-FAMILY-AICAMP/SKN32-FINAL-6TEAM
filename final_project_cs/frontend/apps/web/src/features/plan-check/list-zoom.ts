"use client";

import { useSyncExternalStore } from "react";

/** 메뉴에서 바꾼 목록 크기를 검증 화면과 등록 여행에 즉시 함께 적용한다. */
const ZOOM_KEY = "triPilot.planListZoom";
const ZOOM_CHANGED = "triPilot.planListZoomChanged";
let current: number | null = null;
export function readListZoom(): number {
  if (current !== null) return current;
  try { const value = Number(window.localStorage.getItem(ZOOM_KEY)); return Number.isFinite(value) && value >= 0.8 && value <= 1.3 ? value : 1; } catch { return 1; }
}
export function writeListZoom(value: number) {
  const next = Math.round(Math.min(1.3, Math.max(0.8, Number.isFinite(value) ? value : 1)) * 100) / 100;
  current = next;
  try { window.localStorage.setItem(ZOOM_KEY, String(next)); } catch { /* 저장이 막혀도 현재 화면에는 적용한다. */ }
  window.dispatchEvent(new Event(ZOOM_CHANGED));
}
function subscribe(onChange: () => void) {
  const onStorage = (event: StorageEvent) => { if (event.key === ZOOM_KEY || event.key === null) { current = null; onChange(); } };
  window.addEventListener(ZOOM_CHANGED, onChange);
  window.addEventListener("storage", onStorage);
  return () => { window.removeEventListener(ZOOM_CHANGED, onChange); window.removeEventListener("storage", onStorage); };
}
export function useListZoom(): number {
  return useSyncExternalStore(subscribe, readListZoom, () => 1);
}
