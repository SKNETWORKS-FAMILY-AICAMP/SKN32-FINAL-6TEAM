"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { readConsents, useConsent } from "@/features/consent/consent-store";
import { createLocationSampler, getLocationStops, SEND_EVERY_MS, type LocationSampler, type LocationStops } from "@/lib/live/location-samples";
import { locationPermission, watchLocation, type LocationFailure, type LocationFix } from "@/lib/location";
import { useSettings } from "@/lib/settings";
import type { MyLocation, StayPoint } from "./model";
import { toStayPoints } from "./stays";

/**
 * `[2026-10-05 사용자 지시]` 「지도가 나올 때 고객의 위치를 지도에 바로 표시」. While a map is on the page and the customer has given the location
 * consent, follow their position (`watchLocation`).
 * - ★No consent: nothing is asked, read, drawn or said (it is an optional consent — My page says it can be turned on).
 * - The browser has refused (`denied`): no dot; `failure` says why, for one line under the map. Asked before (`prompt`): the browser asks now.
 * - The consent turned off: following stops and the dot goes.
 */
export function useMyLocation(active: boolean): { fix: LocationFix | null; failure: LocationFailure | null; agreed: boolean } {
  const agreed = useConsent("location");
  const [fix, setFix] = useState<LocationFix | null>(null);
  const [failure, setFailure] = useState<LocationFailure | null>(null);
  const on = active && agreed;

  useEffect(() => {
    if (!on) return;
    let stopped = false;
    let stop: (() => void) | null = null;
    let found = false;
    void locationPermission().then((permission) => {
      if (stopped) return;
      // Refused already: do not knock again (the browser would refuse at once anyway) — say so under the map.
      if (permission === "denied") { setFailure("denied"); return; }
      stop = watchLocation(
        (next) => { found = true; setFix(next); setFailure(null); },
        (reason) => {
          // A slow or missing fix after one was shown: the dot stays where it was, and nothing is said (the next fix moves it).
          if ((reason === "timeout" || reason === "unavailable") && found) return;
          found = false;
          setFix(null);
          setFailure(reason);
        },
      );
    });
    return () => {
      stopped = true;
      stop?.();
      setFix(null);
      setFailure(null);
    };
  }, [on]);

  return on ? { fix, failure, agreed } : { fix: null, failure: null, agreed };
}

/** The fix as the map draws it — the same object while the position and the circle stay the same. */
export function useMeOnMap(fix: LocationFix | null): MyLocation | null {
  const lat = fix?.lat, lng = fix?.lng, accuracyM = fix?.accuracyM ?? null;
  return useMemo(() => (lat === undefined || lng === undefined ? null : { coordinates: { lat, lng }, accuracyM }), [lat, lng, accuracyM]);
}

/**
 * `[2026-10-05 사용자 지시]` 「서버에서 고객이 정확히 어느 지점에서 멈춘 건지 체크」 — hand the server the positions the trip's map reads
 * (`location-samples.ts`): only on a trip's own screen (`tripId`) and only with the location consent. Sent every 60 s, when the page is hidden, and when
 * the screen closes; nothing is sent once the consent is withdrawn.
 */
export function useLocationSamples(tripId: string | undefined, fix: LocationFix | null, agreed: boolean) {
  const { language } = useSettings();
  const languageNow = useRef(language);
  const sampler = useRef<LocationSampler | null>(null);
  useEffect(() => { languageNow.current = language; }, [language]);

  useEffect(() => {
    if (!tripId || !agreed) return;
    const made = createLocationSampler(tripId, { language: languageNow.current });
    sampler.current = made;
    const timer = setInterval(() => { void made.flush(); }, SEND_EVERY_MS);
    // Hidden (another tab, the phone locked, the page closing): what is kept goes now — the page may not come back.
    const onVisibility = () => { if (document.visibilityState === "hidden") void made.flush(); };
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisibility);
      if (sampler.current === made) sampler.current = null;
      // Leaving the screen with the consent still given: what is kept goes now. Withdrawn: nothing more is sent.
      if (readConsents().location) void made.flush();
      made.stop();
    };
  }, [tripId, agreed]);

  useEffect(() => { if (fix) sampler.current?.add(fix); }, [fix]);
}

/**
 * `[2026-10-05]` The places the server found the customer stayed (`GET …/location/stops`), for a trip's own map and only with the location consent.
 * Only the stays of `date` (a day of the plan, Seoul time) when it is given. A server without the route, an error, or no stays: nothing.
 */
export function useLocationStays(tripId: string | undefined, agreed: boolean, date: string | undefined, titles: Record<string, string>): StayPoint[] {
  const { language } = useSettings();
  const enabled = Boolean(tripId) && agreed;
  const query = useQuery({
    queryKey: ["location-stops", tripId ?? ""],
    queryFn: () => getLocationStops(tripId ?? "", language),
    enabled,
    retry: false,
    refetchOnWindowFocus: false,
    staleTime: 60_000,
    refetchInterval: 5 * 60_000,
  });
  const data: LocationStops | null = enabled ? query.data ?? null : null;
  return useMemo(() => toStayPoints(data?.stops ?? [], date, titles), [data, date, titles]);
}
