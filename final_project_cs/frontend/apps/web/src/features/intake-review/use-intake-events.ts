"use client";

import { useEffect, useState } from "react";
import { reconnectDelay } from "@/features/trip/use-trip-events";
import { watchIntake, type IntakeContentHandler } from "@/lib/live/stream";
import type { Language } from "@/lib/i18n";
import { followAfter, rereadGate } from "./follow";

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
 * every 1.5 s. The stage events make `onChange` re-read the intake (its lines and items); the content events (`onContent`,
 * the checks of each place and leg) are not in that GET until the check is done. Runs only while `reading` is true.
 * `[2026-10-27]` A beat that only says the server is alive (same stage) does not re-read (`rereadGate`), and the state is set only when it changes
 * (a beat every 3 s re-rendered the whole plan check).
 */
export function useIntakeEvents(intakeId: string, reading: boolean, language: Language, onChange: () => void, onContent?: IntakeContentHandler): IntakeProgress {
  const [progress, setProgress] = useState<IntakeProgress>({ follow: "live", slow: false });

  useEffect(() => {
    if (!reading) return;
    const stop = new AbortController();
    void (async () => {
      let failures = 0;
      while (!stop.signal.aborted) {
        const reread = rereadGate();
        const end = await watchIntake(intakeId, language, (event) => {
          failures = 0;
          setProgress((current) => followAfter(current, event));   // a hello after `lost` keeps polling until the line carries news (`followAfter`)
          if (reread(event)) onChange();
        }, stop.signal, undefined, onContent);
        if (stop.signal.aborted || end === "closed") return;
        // [2026-10-27] "done" already passed through rereadGate and called onChange via the result event.
        if (end === "done") return;
        if (end === "gone") { onChange(); return; }
        if (end === "stalled") { setProgress({ follow: "stalled", slow: false }); onChange(); return; }
        if (end === "unsupported") { setProgress({ follow: "polling", slow: false }); return; }
        failures += 1;
        setProgress({ follow: "lost", slow: false });
        await new Promise((resolve) => setTimeout(resolve, reconnectDelay(failures)));
      }
    })();
    return () => stop.abort();
  }, [intakeId, reading, language, onChange, onContent]);

  return progress;
}
