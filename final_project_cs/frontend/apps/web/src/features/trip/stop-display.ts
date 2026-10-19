import type { TripStop } from "./model";

/** 선택한 장소의 표시 이름. 원문 제목과 수정 입력은 바꾸지 않는다. */
export function stopDisplayName(stop: Pick<TripStop, "title" | "place">): string {
  return stop.place?.trim() || stop.title;
}

/** 등록 여행 지도의 표시용 사본. 공용 지도와 원문의 수정 입력은 그대로 둔다. */
export function mapStopsWithPlaceNames(stops: TripStop[]): TripStop[] {
  return stops.map((stop) => ({ ...stop, title: stopDisplayName(stop) }));
}
