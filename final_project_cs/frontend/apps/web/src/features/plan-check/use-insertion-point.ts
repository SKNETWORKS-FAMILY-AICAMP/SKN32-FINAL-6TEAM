"use client";

import { useEffect, type RefObject } from "react";

/** Show one seam near the usable list centre without adding height or moving the timeline. */
export function useInsertionPoint(box: RefObject<HTMLElement | null>, enabled: boolean, change: unknown) {
  useEffect(() => {
    const element = box.current;
    if (!element || !enabled) return;
    let frame = 0;
    let shown: HTMLElement | null = null;
    const pick = () => {
      frame = 0;
      const area = element.getBoundingClientRect();
      const head = element.parentElement?.querySelector("header")?.getBoundingClientRect();
      const top = Math.max(area.top, head?.bottom ?? area.top);
      const middle = (top + area.bottom) / 2;
      let best: HTMLElement | null = null, distance = Infinity;
      for (const point of element.querySelectorAll<HTMLElement>("[data-insert-point]")) {
        if (point.closest("[inert]")) continue;
        const at = point.getBoundingClientRect().top;
        if (at < top + 22 || at > area.bottom - 22) continue;
        const gap = Math.abs(at - middle);
        if (gap < distance) { best = point; distance = gap; }
      }
      if (best === shown) return;
      shown?.removeAttribute("data-insert-near");
      shown = best;
      shown?.setAttribute("data-insert-near", "");
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(pick); };
    const resize = new ResizeObserver(schedule);
    resize.observe(element);
    for (const row of element.querySelectorAll<HTMLElement>("li[data-type]")) resize.observe(row);
    element.addEventListener("scroll", schedule, { passive: true });
    schedule();
    return () => {
      element.removeEventListener("scroll", schedule);
      resize.disconnect();
      cancelAnimationFrame(frame);
      shown?.removeAttribute("data-insert-near");
    };
  }, [box, enabled, change]);
}
