"use client";

import { useEffect, useState } from "react";
import { reconnectDelay } from "@/features/trip/use-trip-events";
import { watchIntake } from "@/lib/live/stream";
import type { Language } from "@/lib/i18n";

/**
 * How the screen follows an intake the server is reading:
 *   - `live`: the server's progress stream is open — each event re-reads the intake;
 *   - `lost`: the stream went silent or dropped — reconnecting (1 s, 2 s, 4 s … up to 30 s);
 *   - `polling`: no stream here (an older server, or the per-user stream limit) — the intake is re-read every 1.5 s;
 *   - `stalled`: the server says the reading stopped (its worker died, e.g. a restart) — it will not finish by itself.
 */
export type IntakeFollow = "live" | "lost" | "polling" | "stalled";

export interface IntakeProgress {
  follow: IntakeFollow;
  /** The server has been in the same stage longer than usual (`beat.slow`). */
  slow: boolean;
}

/**
 * `[2026-10-02]` The server streams an intake's reading (`GET /v1/web/trip-intakes/{id}/events`) instead of being asked
 * every 1.5 s. The stream carries only the stage — `onChange` re-reads the intake (its lines and items) on every event.
 * Runs only while `reading` is true.
 */
export function useIntakeEvents(intakeId: string, reading: boolean, language: Language, onChange: () => void): IntakeProgress {
  const [progress, setProgress] = useState<IntakeProgress>({ follow: "live", slow: false });

  useEffect(() => {
    if (!reading) return;
    const stop = new AbortController();
    void (async () => {
      let failures = 0;
      while (!stop.signal.aborted) {
        const end = await watchIntake(intakeId, language, (event) => {
          failures = 0;
          setProgress({ follow: "live", slow: event.type === "progress" && event.slow });
          onChange();
        }, stop.signal);
        if (stop.signal.aborted || end === "closed") return;
        if (end === "done" || end === "gone") { onChange(); return; }
        if (end === "stalled") { setProgress({ follow: "stalled", slow: false }); onChange(); return; }
        if (end === "unsupported") { setProgress({ follow: "polling", slow: false }); return; }
        failures += 1;
        setProgress({ follow: "lost", slow: false });
        await new Promise((resolve) => setTimeout(resolve, reconnectDelay(failures)));
      }
    })();
    return () => stop.abort();
  }, [intakeId, reading, language, onChange]);

  return progress;
}
