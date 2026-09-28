"use client";

import { useMemo } from "react";
import { LiveMap, MapUnavailable } from "./live-map";
import type { MapViewProps } from "./model";
import { createGoogleAdapter } from "./providers/google";

export function GoogleMap({ apiKey, mapId, ...props }: MapViewProps & { apiKey: string; mapId: string }) {
  const adapter = useMemo(() => createGoogleAdapter(apiKey, mapId), [apiKey, mapId]);
  return apiKey.trim() && mapId.trim() ? <LiveMap {...props} adapter={adapter} name="Google" /> : <MapUnavailable message="Google Maps 연결 설정이 필요해요." />;
}
