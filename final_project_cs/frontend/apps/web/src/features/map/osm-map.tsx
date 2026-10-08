"use client";

import "leaflet/dist/leaflet.css";
import { useMemo } from "react";
import { LiveMap } from "./live-map";
import type { MapViewProps } from "./model";
import { createOsmAdapter } from "./providers/osm";

export function OsmMap({ tileUrl, ...props }: MapViewProps & { tileUrl: string }) {
  const adapter = useMemo(() => createOsmAdapter(tileUrl), [tileUrl]);
  return <LiveMap {...props} adapter={adapter} name="OpenStreetMap" />;
}
