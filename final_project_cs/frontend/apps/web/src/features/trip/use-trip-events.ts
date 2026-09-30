"use client";

import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { watchTrip, type ChangeKind } from "@/lib/live/events";
import { useSettings } from "@/lib/settings";
import { tripKey } from "../../lib/gateway";
import { noticesKey, proposalsKey } from "./use-trip-extras";
import { setWatchMode } from "./watch-mode";

/**
 * Keep an open trip screen current: listen for the server's "this trip changed" bell and re-read what changed.
 *
 * - A bell → re-read the parts it names (the trip itself, its notices, its proposals).
 * - Reconnected, or the tab came back to the front → re-read everything once. A bell missed while away is
 *   covered by that: the bell carries no content, the server's database is the record.
 * - The server has no bell (older server: 404/405) → the notices and proposals go back to being re-read every 30 s.
 *
 * ★Nothing is sent back to the server to "stay alive" — the server's own `: ping` lines keep the line open.
 */

/** Wait before reconnecting: 1 s, 2 s, 4 s … up to 30 s. Reset once a connection says it is ready. */
export function reconnectDelay(failures: number): number {
  return Math.min(30_000, 1_000 * 2 ** Math.max(0, failures - 1));
}

export function useTripEvents(tripId: string) {
  const queryClient = useQueryClient();
  const { language } = useSettings();

  useEffect(() => {
    if (!tripId) return;
    const stop = new AbortController();
    let current: AbortController | null = null;
    let failures = 0;
    let everReady = false;
    let wake: (() => void) | null = null;

    const reread = (kinds: readonly ChangeKind[]) => {
      if (kinds.includes("itinerary")) void queryClient.invalidateQueries({ queryKey: tripKey(tripId, language) });
      if (kinds.includes("notice")) void queryClient.invalidateQueries({ queryKey: noticesKey(tripId, language) });
      if (kinds.includes("proposal")) void queryClient.invalidateQueries({ queryKey: proposalsKey(tripId, language) });
    };
    const rereadAll = () => reread(["itinerary", "notice", "proposal"]);

    const pause = (ms: number) => new Promise<void>((resolve) => {
      const timer = setTimeout(done, ms);
      function done() { clearTimeout(timer); stop.signal.removeEventListener("abort", done); wake = null; resolve(); }
      wake = done;
      stop.signal.addEventListener("abort", done, { once: true });
    });

    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      rereadAll();
      wake?.();
    };
    document.addEventListener("visibilitychange", onVisible);

    void (async () => {
      while (!stop.signal.aborted) {
        current = new AbortController();
        const abortCurrent = () => current?.abort();
        stop.signal.addEventListener("abort", abortCurrent, { once: true });
        const end = await watchTrip(tripId, language, (event) => {
          if (event.type === "ready") {
            setWatchMode(tripId, "bell");
            // The first connection comes right after the screen read everything; later ones follow a gap.
            if (everReady) rereadAll();
            everReady = true;
            failures = 0;
          } else {
            reread(event.kinds);
          }
        }, current.signal);
        stop.signal.removeEventListener("abort", abortCurrent);
        if (stop.signal.aborted) break;
        if (end === "unsupported") { setWatchMode(tripId, "polling"); break; }
        failures += 1;
        await pause(reconnectDelay(failures));
      }
    })();

    return () => {
      stop.abort();
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [tripId, language, queryClient]);
}
