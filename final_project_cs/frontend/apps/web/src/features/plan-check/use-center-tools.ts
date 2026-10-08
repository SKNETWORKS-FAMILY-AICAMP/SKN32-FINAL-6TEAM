"use client";

import { useEffect, type RefObject } from "react";

/**
 * `[2026-10-07 사용자 지시 — 손가락 기기에서 수정 · 삭제는 스크롤로 초점이 간 일정 하나에만, 잠깐]` While the list is scrolled, the stop nearest the middle of the list shows its edit and delete
 * buttons (the attribute `data-tools` on its row; the CSS shows them only where there is no mouse - `hover: none`), and they go this long after the scrolling stops.
 *
 * ★Why 4 seconds (documented in DEVELOPMENT.md): the buttons must stay long enough to be seen and pressed on purpose, and short enough that a hand holding the phone while walking does not hit them
 *   by accident later. Practice: Android's long snackbar shows for 2.75 s and Material asks 4-10 s for messages with an action; reading a short label and moving a thumb to it takes about 1-2 s
 *   (an estimate). 4 s is the shortest of the action range: long enough to decide, and gone before the next unrelated touch. A press on the card itself opens it and shows them anyway.
 */
export const TOOLS_SHOW_MS = 4_000;

export function useCenterTools(box: RefObject<HTMLElement | null>, enabled: boolean) {
  useEffect(() => {
    const element = box.current;
    if (!element || !enabled) return;
    let frame = 0;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let shown: HTMLElement | null = null;
    const show = (row: HTMLElement | null) => {
      if (shown === row) return;
      shown?.removeAttribute("data-tools");
      shown = row;
      shown?.setAttribute("data-tools", "");
    };
    const pick = () => {
      frame = 0;
      const area = element.getBoundingClientRect();
      const middle = area.top + area.height / 2;
      let best: HTMLElement | null = null, bestGap = Infinity;
      for (const row of element.querySelectorAll<HTMLElement>('li[data-type="item"]')) {
        const box = row.getBoundingClientRect();
        if (box.bottom < area.top || box.top > area.bottom) continue;
        const gap = Math.abs(box.top + box.height / 2 - middle);
        if (gap < bestGap) { best = row; bestGap = gap; }
      }
      show(best);
      clearTimeout(timer);
      timer = setTimeout(() => show(null), TOOLS_SHOW_MS);
    };
    const onScroll = () => { if (!frame) frame = requestAnimationFrame(pick); };
    element.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      element.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(frame);
      clearTimeout(timer);
      show(null);
    };
  }, [box, enabled]);
}
