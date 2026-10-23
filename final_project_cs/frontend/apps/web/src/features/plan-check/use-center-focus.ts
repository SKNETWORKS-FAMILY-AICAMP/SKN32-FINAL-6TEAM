"use client";

import { useEffect, type RefObject } from "react";

/** The boxes that can take the centre focus: a stop's card and a way's box — not a past stop (its grey line or its opened grey card) and not a past way. */
const BOXES = "li[data-type=\"item\"]:not([data-past]):not([data-past-open]) article, li[data-type=\"move\"]:not([data-past]) [data-rail-box]";

/**
 * `[2026-10-15 사용자 결정 — ST4F-532 · 목업 「제안」]` One box — a stop's card or a way's box — is marked `data-focus` at the middle of the usable list, by the same measure as the ＋
 * (`useInsertionPoint`): the box the middle line runs through, else the box nearest it; the first box at the top of the list and the last at its end. It does not move the list or add height;
 * the CSS draws the mark (a grey border). `head` is what covers the list's top (the day strip), when it is not the list's own `header`.
 */
export function useCenterFocus(box: RefObject<HTMLElement | null>, enabled: boolean, change: unknown, head?: RefObject<HTMLElement | null>) {
  useEffect(() => {
    const element = box.current;
    if (!element || !enabled) return;
    let frame = 0;
    let shown: HTMLElement | null = null;
    const pick = () => {
      frame = 0;
      const area = element.getBoundingClientRect();
      const cover = (head?.current ?? element.parentElement?.querySelector("header"))?.getBoundingClientRect();
      const top = Math.max(area.top, cover?.bottom ?? area.top);
      const middle = (top + area.bottom) / 2;
      const seen = [...element.querySelectorAll<HTMLElement>(BOXES)]
        .filter((candidate) => !candidate.closest("[inert]"))
        .map((candidate) => ({ candidate, rect: candidate.getBoundingClientRect() }))
        // Only what is in sight: below the strip, above the list's bottom, and in this day's column (the next day waits beside it while the days slide).
        .filter(({ rect }) => rect.bottom > top + 4 && rect.top < area.bottom - 4 && rect.right > area.left + 4 && rect.left < area.right - 4);
      const atEnd = element.scrollHeight - element.clientHeight - element.scrollTop <= 2;
      const atStart = element.scrollTop <= 2;
      let best: HTMLElement | null = null;
      if (seen.length) {
        if (atStart) best = seen[0].candidate;
        else if (atEnd) best = seen[seen.length - 1].candidate;
        else {
          const across = seen.find(({ rect }) => rect.top <= middle && rect.bottom >= middle);
          best = (across ?? seen.reduce((near, next) => Math.abs(next.rect.top + next.rect.height / 2 - middle) < Math.abs(near.rect.top + near.rect.height / 2 - middle) ? next : near)).candidate;
        }
      }
      if (best === shown) return;
      shown?.removeAttribute("data-focus");
      shown = best;
      shown?.setAttribute("data-focus", "");
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
      shown?.removeAttribute("data-focus");
    };
  }, [box, enabled, change, head]);
}
