"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { requestRiskAlternatives } from "@/lib/live/risks";
import { useSettings, useT } from "@/lib/settings";
import { noticesKey, proposalsKey, risksKey } from "./use-trip-extras";

/** This explicit customer action asks for a proposal; applying it remains the customer's separate choice. */
export function useRiskAlternatives(tripId: string, onOffered: () => void) {
  const { language } = useSettings();
  const t = useT();
  const client = useQueryClient();
  const request = useMutation({ mutationFn: (itemId: string) => requestRiskAlternatives(tripId, itemId, language),
    onSuccess: (result) => {
      void client.invalidateQueries({ queryKey: risksKey(tripId, language) });
      if (result.status === "offered" || result.status === "already") {
        void client.invalidateQueries({ queryKey: proposalsKey(tripId, language) });
        void client.invalidateQueries({ queryKey: noticesKey(tripId, language) });
        onOffered();
      }
    } });
  const status = request.data?.status;
  const categories: Record<string, [string, string]> = {
    forecast: ["날씨 예보", "Weather forecast"], weather_warning: ["기상 특보", "Weather warnings"],
    traffic_control: ["도로 통제", "Road restrictions"], disaster_msg: ["재난 안내", "Disaster guidance"],
    air_quality: ["대기질", "Air quality"], earthquake: ["지진 정보", "Earthquake information"],
  };
  const missed = (request.data?.failedCategories ?? []).flatMap(code => categories[code] ? [t(...categories[code])] : []);
  const message = request.isError ? t("실내 대안을 확인하지 못했어요. 일정은 그대로예요. 다시 시도해 주세요.", "Indoor alternatives could not be checked. Your itinerary is kept. Try again.")
    : status === "no_alternate" ? `${request.data?.reason ?? t("이번 확인에서 안전·운영시간·이동 조건을 만족한 실내 후보를 확보하지 못했어요.", "No indoor candidate met safety, opening-hour and travel conditions in this check.")} ${t("현재 일정은 그대로예요. 다시 확인할 수 있어요.", "The current plan is kept. You can check again.")}`
    : status === "unavailable" ? `${request.data?.message ?? t("필요한 자료를 확인하지 못해 후보 검증을 끝내지 못했어요.", "Required information was unavailable, so candidate verification could not finish.")} ${missed.length ? t(`확인하지 못한 자료: ${missed.join(" · ")}. `, `Unverified sources: ${missed.join(" · ")}. `) : ""}${t("현재 일정은 그대로예요. 잠시 뒤 다시 확인해 주세요.", "The current plan is kept. Try again shortly.")}`
    : status === "no_risk" ? t("다시 확인한 결과, 현재 겹치는 위험이 없어요. 일정은 그대로예요.", "The new check found no overlapping risk. Your itinerary is kept.")
    : status === "stale" ? t("확인하는 동안 일정이 바뀌었어요. 새 일정에서 다시 확인해 주세요.", "The itinerary changed during the check. Check again on the new itinerary.")
    : status === "ended" ? t("이미 끝난 일정이라 대안을 만들지 않았어요.", "No alternative was made for a stop that has ended.") : null;
  return { ask: (itemId: string) => request.mutate(itemId), busy: request.isPending ? request.variables : null, message };
}
