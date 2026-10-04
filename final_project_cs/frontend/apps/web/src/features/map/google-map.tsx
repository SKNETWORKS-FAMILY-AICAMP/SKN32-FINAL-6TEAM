"use client";

import { useEffect, useMemo, useState } from "react";
import { useSettings } from "@/lib/settings";
import { mapLoad } from "@/lib/live/extras";
import { LiveMap, MapUnavailable } from "./live-map";
import type { MapViewProps } from "./model";
import { OsmMap } from "./osm-map";
import { createGoogleAdapter } from "./providers/google";
import styles from "./map.module.css";

/** `free-setting`: the operator chose the free map — nothing went wrong, so the screen says nothing about it. */
export type GoogleDecision = "checking" | "google" | "free" | "free-setting";

/**
 * ★One question for one map, even when React mounts it twice in a row (development StrictMode mounts, unmounts and
 *   mounts again). Without this the dev server spent two counted loads per map (measured 2026-09-29: map-load ×2).
 *   A question asked less than 2 s ago is shared; a later mount is a new map and asks again.
 */
let recent: { at: number; answer: Promise<{ allowed: boolean; reason?: string | null }> } | null = null;
function askOnce(language: Parameters<typeof mapLoad>[0]): Promise<{ allowed: boolean; reason?: string | null }> {
  const now = Date.now();
  if (!recent || now - recent.at > 2000) recent = { at: now, answer: mapLoad(language) };
  return recent.answer;
}

/**
 * ★Google Maps only after the server allows this load (`POST /v1/web/map-load`, once per map mount).
 *   Refused, over the cap, or no answer → the free map. The Google SDK is never requested before the answer.
 */
export function GoogleMap({ apiKey, mapId, tileUrl, onDecided, ...props }: MapViewProps & {
  apiKey: string; mapId: string; tileUrl: string; onDecided?: (decision: GoogleDecision) => void;
}) {
  const { language } = useSettings();
  const [decision, setDecision] = useState<GoogleDecision>("checking");
  const adapter = useMemo(() => createGoogleAdapter(apiKey, mapId), [apiKey, mapId]);

  useEffect(() => {
    let cancelled = false;
    void askOnce(language).then((answer) => {
      if (cancelled) return;
      const next: GoogleDecision = answer.allowed ? "google" : answer.reason === "setting" ? "free-setting" : "free";
      setDecision(next);
      onDecided?.(next);
    });
    return () => { cancelled = true; };
    // ★One question per mount: re-renders (selection, language) must not spend another Google load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!apiKey.trim() || !mapId.trim()) return <MapUnavailable message="Google Maps 연결 설정이 필요해요." />;
  if (decision === "checking") return <div className={styles.live} role="status" aria-busy="true"><div className={styles.overlay}>지도를 불러오고 있어요…</div></div>;
  if (decision === "free" || decision === "free-setting") return <OsmMap {...props} tileUrl={tileUrl} />;
  return <LiveMap {...props} adapter={adapter} name="Google" fitButton />;
}
