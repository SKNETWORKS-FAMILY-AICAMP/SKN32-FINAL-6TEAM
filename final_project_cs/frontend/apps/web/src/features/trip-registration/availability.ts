"use client";

import { useEffect, useSyncExternalStore } from "react";
import { knownFeatures, loadFeatures, subscribeFeatures } from "@/lib/live/features";
import { useSettings } from "@/lib/settings";

/**
 * `[2026-10-25 사용자 지시 — ST4F-739]` Whether the plan screen shows its extra panels — 「파일 선택」 · 「계획 짜 주기 (테스트)」 · 「읽는 기준」 · 「여행 취향」 —
 * next to 「직접 입력」: the operator's switch (off by default), read from the server once per page (`lib/live/features.ts`).
 * null until the answer: the plan screen waits with 「직접 입력」 alone instead of drawing the panels and taking them away again.
 */
export function usePlanInputExtrasShown(): boolean | null {
  const { language } = useSettings();
  const shown = useSyncExternalStore(subscribeFeatures, () => knownFeatures()?.planInputExtras ?? null, () => null);
  useEffect(() => { void loadFeatures(language); }, [language]);
  return shown;
}
