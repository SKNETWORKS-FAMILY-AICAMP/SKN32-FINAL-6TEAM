"use client";

import { useEffect, useSyncExternalStore } from "react";
import { knownFeatures, loadFeatures, subscribeFeatures } from "@/lib/live/features";
import { useSettings } from "@/lib/settings";

/**
 * `[2026-10-22 사용자 지시]` Whether the plan check (before registering · editing a trip) shows its risk check panel — the operator's switch, read from the
 * server once per page (`lib/live/features.ts`). Not read yet: shown, as before — the panel appears only once the check is done, well after the answer.
 */
export function useRiskPanelShown(): boolean {
  const { language } = useSettings();
  const shown = useSyncExternalStore(subscribeFeatures, () => knownFeatures()?.riskPanel ?? true, () => true);
  useEffect(() => { void loadFeatures(language); }, [language]);
  return shown;
}
