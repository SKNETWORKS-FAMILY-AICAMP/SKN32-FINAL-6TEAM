"use client";

import { useEffect, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import type { Language } from "@/lib/i18n";
import { emptyStream, reduceStream, watchIntake, type IntakeStreamEvent, type StreamState } from "@/lib/live/intake-events";
import { useSettings } from "@/lib/settings";
import { reconnectDelay } from "../trip/use-trip-events";
import { createPacer, type Pacer } from "./pacer";
import { connectionAfter, type StreamConnection } from "./stream-connection";

export const intakeKey = (intakeId: string, language: Language) => ["intake", intakeId, language] as const;

const prefersLessMotion = () => typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Follow the reading of one plan while it is being read, and hand the screen what it has built so far.
 *
 * - Events are copies of state, so a reconnect (which replays everything) just overwrites — nothing is lost or doubled.
 * - The server keeps the order and the screen keeps the pace: events wait in a line and are shown one after another
 *   (`pacer.ts`), or at once if the customer asked for less motion. `playing` is true while some are still waiting — the
 *   screen stays on the reading until they have been shown, even if the server is already done.
 * - On `result` the plan is read again with the GET (the truth); the stream only showed how it came to be.
 * - The connection falls back to polling when the stream cannot be opened or goes quiet (`stream-connection.ts`).
 * - `enabled` false (the plan is not being read) closes the connection — but what is still waiting to be shown is shown first.
 * - Mount it with `key={intakeId}`: the state it builds belongs to one plan.
 */
export function useIntakeStream(intakeId: string, enabled: boolean) {
  const queryClient = useQueryClient();
  const { language } = useSettings();
  const [connection, setConnection] = useState<StreamConnection>("connecting");
  const [stream, setStream] = useState<StreamState>(emptyStream);
  const [slow, setSlow] = useState(false);
  const [playing, setPlaying] = useState(false);
  const connectionRef = useRef<StreamConnection>("connecting");
  // One pace for the whole life of the screen: the connection may close (the reading ended) while events are still waiting.
  const pacerRef = useRef<Pacer | null>(null);

  useEffect(() => () => { pacerRef.current?.stop(); }, []);

  useEffect(() => {
    if (!enabled || !intakeId) return;
    const stop = new AbortController();
    let failures = 0;
    let finished = false;
    let lastHeard = Date.now();
    // A reconnect (a new language, a retry) starts again from what the server replays — events are copies of state,
    // so what was built before is overwritten, not doubled. A different plan gets a fresh hook (`key={intakeId}`).
    const move = (next: StreamConnection) => {
      if (next === connectionRef.current) return;
      connectionRef.current = next;
      setConnection(next);
    };
    pacerRef.current ??= createPacer({
      show: (event) => setStream((state) => reduceStream(state, event)),
      onBusy: setPlaying,
      instant: prefersLessMotion(),
    });
    const pacer = pacerRef.current;

    const heard = (event: IntakeStreamEvent) => {
      lastHeard = Date.now();
      failures = 0;
      if (event.type === "result" || (event.type === "error" && !event.retryable)) {
        finished = true;
        move("closed");
        void queryClient.invalidateQueries({ queryKey: intakeKey(intakeId, language) });
        return;
      }
      move(connectionAfter(connectionRef.current, { kind: "heard" }));
      if (event.type === "beat") { setSlow(event.slow); return; }
      if (event.type === "stage") {
        setSlow(false);
        // A new stage is when the original's lines first exist (a photo's text arrives after transcribing) — read the plan again.
        void queryClient.invalidateQueries({ queryKey: intakeKey(intakeId, language) });
      }
      pacer.push(event);
    };

    const watchdog = setInterval(() => {
      if (!finished) move(connectionAfter(connectionRef.current, { kind: "silent", ms: Date.now() - lastHeard }));
    }, 1_000);

    void (async () => {
      while (!stop.signal.aborted && !finished) {
        const end = await watchIntake(intakeId, language, heard, stop.signal);
        if (stop.signal.aborted || finished) break;
        failures += 1;
        move(connectionAfter(connectionRef.current, { kind: "ended", end, failures }));
        if (end === "unsupported") break;                // this server has no stream — do not keep knocking
        await new Promise<void>((resolve) => {
          const timer = setTimeout(done, reconnectDelay(failures));
          function done() { clearTimeout(timer); stop.signal.removeEventListener("abort", done); resolve(); }
          stop.signal.addEventListener("abort", done, { once: true });
        });
      }
    })();

    return () => { stop.abort(); clearInterval(watchdog); };
  }, [intakeId, language, enabled, queryClient]);

  return { connection: enabled ? connection : "closed" as const, stream, slow, playing };
}
