import type { TripStop } from "./model";

/**
 * 선택한 장소의 이름(없으면 일정 제목) — 장소를 가리키는 문구(「…에서 출발」 · 사진)에 쓴다. 원문 제목과 수정 입력은 바꾸지 않는다.
 * `[2026-10-21 사용자 결정 C — ST4F-706]` 일정의 이름(카드 · 상세 · 지도 · 알림 줄)은 고객이 쓴 제목이고, 장소 이름은 `stopPlaceNote` 로 그 아래에 함께 보인다.
 */
export function stopDisplayName(stop: Pick<TripStop, "title" | "place">): string {
  return stop.place?.trim() || stop.title;
}

/**
 * `[2026-10-21 사용자 결정 C — ST4F-706]` 제목 아래에 함께 보일 선택 장소 이름 — 제목과 같거나 장소가 없으면 `null`.
 * 공유 계획서와 같은 규칙이다(`wiki/external/public-plan-place-display.md`).
 */
export function stopPlaceNote(stop: Pick<TripStop, "title" | "place">): string | null {
  const place = stop.place?.trim();
  return place && place !== stop.title.trim() ? place : null;
}
