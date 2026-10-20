import type { Translate } from "@/lib/i18n";
import { LiveError } from "@/lib/live/client";

/** 빈 검색과 조회·분류·지역 확인 실패를 구별한다. 실제 결과가 있으면 그대로 보여 준다. */
export function assertPlaceSearchComplete(found: { results: readonly unknown[]; notes?: readonly string[] }, t: Translate): void {
  if (found.results.length) return;
  const notes = found.notes ?? [];
  if (notes.some((note) => note.startsWith("kakao:"))) {
    const limited = notes.some((note) => note === "kakao:budget_exhausted" || note === "kakao:http_429");
    throw new LiveError("place_search_unavailable", limited
      ? t("지도 검색 한도에 도달해 결과를 확인하지 못했어요. 가게가 없다는 뜻은 아니에요. 나중에 다시 시도해 주세요.", "The map search limit was reached. This does not mean the place does not exist. Try again later.")
      : t("지도 검색 결과를 확인하지 못했어요. 가게가 없다는 뜻은 아니에요. 검색을 다시 시도해 주세요.", "Map search could not be completed. This does not mean the place does not exist. Please retry."));
  }
  if (notes.includes("no_same_kind")) {
    throw new LiveError("place_search_kind_unsupported", t("검색된 장소의 종류를 이 일정에 사용할 수 없어 표시하지 않았어요. 일정 종류를 확인해 주세요.", "The places found cannot be used for this type of stop. Check the stop type."));
  }
  if (notes.includes("area_unverified") || notes.includes("area_mismatch")) {
    throw new LiveError("place_search_area_unconfirmed", t("검색된 장소가 요청한 지역에 있는지 확인하지 못했어요. 지점명이나 주소를 함께 검색해 주세요.", "The places found could not be matched to the requested area. Add a branch name or address."));
  }
}
