/** 검증 화면과 등록 여행에서 같은 목록 확대 설정을 쓴다. */
const ZOOM_KEY = "triPilot.planListZoom";
export function readListZoom(): number {
  try { const value = Number(window.localStorage.getItem(ZOOM_KEY)); return Number.isFinite(value) && value >= 0.8 && value <= 1.3 ? value : 1; } catch { return 1; }
}
export function writeListZoom(value: number) {
  try { window.localStorage.setItem(ZOOM_KEY, String(value)); } catch { /* 비공개 창에서는 현재 화면에만 적용한다. */ }
}
