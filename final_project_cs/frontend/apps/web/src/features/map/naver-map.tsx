"use client";

import { useMemo } from "react";
import { LiveMap, MapUnavailable } from "./live-map";
import type { MapViewProps } from "./model";
import { createNaverAdapter } from "./providers/naver";

export function NaverMap({ clientId, ...props }: MapViewProps & { clientId: string }) {
  const adapter = useMemo(() => createNaverAdapter(clientId), [clientId]);
  return clientId.trim() ? <LiveMap {...props} adapter={adapter} name="네이버" /> : <MapUnavailable message="네이버지도 연결 설정이 필요해요." />;
}
