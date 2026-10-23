"use client";

import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { RouteShapes } from "@/lib/live/route-shapes";

/** The zoom level (the same scale as Leaflet and Google) from which the detailed route lines are worth their size: streets are a few pixels wide there. */
export const DETAIL_ZOOM = 15;

/**
 * `[2026-10-05 사용자 지시]` 「확대하면 지도를 타고 상세 경로가 똑바로 나오게」: the lines the server gives by default are the short ones (fine zoomed out); once the map is zoomed in to
 * `DETAIL_ZOOM` or more, the detailed lines (`?detail=true`: error 0.5 m, up to 5,000 points a line) are asked for ONCE and drawn instead - they follow the streets.
 * ★Once zoomed in, the detailed lines are kept even if the customer zooms out again: they are right at every zoom, and switching back and forth would only make the lines jump.
 * A failure to read them leaves the short lines (nothing is made up). Returns the lines to draw and the function to give the map as `onZoom`.
 */
export function useRouteDetail(coarse: RouteShapes | null | undefined, key: readonly unknown[], load: () => Promise<RouteShapes | null>) {
  const [zoomed, setZoomed] = useState(false);
  const onZoom = useCallback((zoom: number) => { if (zoom >= DETAIL_ZOOM) setZoomed(true); }, []);
  const detail = useQuery({
    queryKey: ["route-detail", ...key],
    queryFn: load,
    enabled: zoomed && Boolean(coarse?.shapes.length),
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 10 * 60_000,
  });
  return { onZoom, routes: detail.data ?? coarse ?? null };
}
