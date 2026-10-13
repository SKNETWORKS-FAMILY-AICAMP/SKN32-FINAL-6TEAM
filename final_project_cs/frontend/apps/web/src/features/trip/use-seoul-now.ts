"use client";

import { useEffect, useState } from "react";
import { seoul } from "@/lib/live/gateway";
import { toMinutes, type SeoulNow } from "./trip-timeline";

const readNow = (): SeoulNow => {
  const { date, time } = seoul(new Date().toISOString());
  return { date, minute: toMinutes(time) ?? 0 };
};

/**
 * `[2026-10-12 사용자 결정]` Now in Seoul, from the device's clock — no call to the server (the trip's times are Seoul times and the server sends no clock). It moves on at each new minute and
 * when the page is shown again (a phone kept in a pocket does not run timers); it is not read while the page is hidden. A device whose clock is wrong shows a wrong 「지금」 — there is nothing
 * to correct it with yet (`wiki/external/web-screen-api.md`).
 */
export function useSeoulNow(): SeoulNow {
  // The trip screen is drawn only in the browser (it waits for the trip), so the clock can be read at once.
  const [now, setNow] = useState(readNow);
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | undefined;
    const read = () => setNow((before) => {
      const next = readNow();
      return before.date === next.date && before.minute === next.minute ? before : next;
    });
    const schedule = () => { timer = setTimeout(() => { read(); schedule(); }, 60_000 - (Date.now() % 60_000) + 50); };
    const onVisibility = () => {
      clearTimeout(timer);
      if (document.visibilityState !== "visible") return;
      read();
      schedule();
    };
    schedule();
    document.addEventListener("visibilitychange", onVisibility);
    return () => { clearTimeout(timer); document.removeEventListener("visibilitychange", onVisibility); };
  }, []);
  return now;
}
