"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type RefObject, type UIEvent } from "react";
import { dampedScrollTo } from "@/lib/damped-scroll";

/** How close (px) to the bottom still counts as 「at the bottom」 — the list is then followed again. */
export const NEAR_BOTTOM_PX = 48;
/** Room (px) left between the followed row and the edge of the list. */
export const FOLLOW_MARGIN_PX = 12;
/** `[2026-10-20 사용자 결정 — 계획 확인 C안]` Room (px) above the card being checked, pinned at the top of the list. */
export const FOLLOW_TOP_PX = 14;
/** A scroll this soon after the customer's wheel, touch, key or press is theirs (not the screen following the check). */
const USER_MS = 1200;

/** Where the followed row is brought: just into view, or to the top (`[2026-10-20]` the plan check's C안 — it was brought to the middle). */
export type FollowAlign = "nearest" | "top";

/**
 * How far to scroll (px, + down) so `target` is inside `box`, leaving `margin`; 0 when it already is. Pure, so the rule is tested
 * without a browser. A row taller than the box is brought to its top instead of being chased. `top` brings it `margin` under the top, always.
 */
export function scrollDelta(box: { top: number; bottom: number }, target: { top: number; bottom: number }, margin = FOLLOW_MARGIN_PX, align: FollowAlign = "nearest"): number {
  if (align === "top" || target.bottom - target.top > box.bottom - box.top - margin * 2) return target.top - box.top - margin;
  if (target.bottom > box.bottom - margin) return target.bottom - box.bottom + margin;
  if (target.top < box.top + margin) return target.top - box.top - margin;
  return 0;
}

export const nearBottom = (box: { scrollTop: number; clientHeight: number; scrollHeight: number }) =>
  box.scrollTop + box.clientHeight >= box.scrollHeight - NEAR_BOTTOM_PX;

/**
 * `[2026-10-03 사용자 지시]` While the server's check is drawn row by row, the list follows the newest row, so what is being
 * checked is always in view (it used to stay at the top while rows were added below). The customer's own scrolling wins: once
 * they scroll away from the bottom the list stays where they put it, and it follows again when they come back to the bottom
 * (or press 「따라가기」, `resume`).
 *
 * `find` picks the row to follow in the list; `change` is whatever changes when rows are added (the drawn view). Spread
 * `handlers` on the list element.
 */
export function useFollowScroll(box: RefObject<HTMLElement | null>, find: (box: HTMLElement) => HTMLElement | null, enabled: boolean, change: unknown, align: FollowAlign = "nearest",
  /** `[2026-10-20 C안]` For `top`: the room above the followed row (under the stop banner while the check is stopped); `FOLLOW_TOP_PX` when left out. */
  topRoom?: (box: HTMLElement) => number) {
  const [following, setFollowing] = useState(true);
  const touched = useRef(0);

  useEffect(() => {
    const element = box.current;
    if (!element || !enabled || align !== "top") return;
    // Reserve room below the last row, so it can reach the top too; remove it once the result is ready.
    const resize = () => element.style.setProperty("--follow-room", `${element.clientHeight - FOLLOW_TOP_PX}px`);
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(element);
    return () => { observer.disconnect(); element.style.removeProperty("--follow-room"); };
  }, [box, enabled, align]);

  useEffect(() => {
    if (!enabled || !following) return;
    const element = box.current;
    const target = element && find(element);
    if (!element || !target) return;
    const delta = scrollDelta(element.getBoundingClientRect(), target.getBoundingClientRect(), align === "top" ? topRoom?.(element) ?? FOLLOW_TOP_PX : FOLLOW_MARGIN_PX, align);
    if (Math.abs(delta) < 1) return;
    // `[2026-10-20 사용자 결정 — 계획 확인 C안]` Pinned at the top, the list moves once per card (its checks tick in where it stands): the browser's own smooth scroll, at once when motion is reduced.
    if (align === "top") { element.scrollTo({ top: element.scrollTop + delta, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" }); return; }
    // ★`[2026-10-06 사용자 지적]` A damped spring, not the browser's fixed smooth scroll that restarts at every row (it looked jerky): the list eases towards the newest row and keeps its speed as rows are added.
    dampedScrollTo(element, element.scrollTop + delta);
  }, [box, find, enabled, following, change, align, topRoom]);

  const note = useCallback(() => { touched.current = Date.now(); }, []);
  // ★A press on a row (a card, a button) is a click, not a scroll: counting it made the screen's own next scroll look like the customer's
  //   and stopped the following (found in review 2026-10-03). A press on the list itself — its scrollbar — is the customer scrolling.
  const onPointerDown = useCallback((event: PointerEvent<HTMLElement>) => { if (event.target === event.currentTarget) note(); }, [note]);
  const onScroll = useCallback((event: UIEvent<HTMLElement>) => {
    const element = event.currentTarget;
    if (Date.now() - touched.current > USER_MS) return;       // the screen's own scroll
    setFollowing(nearBottom(element));
  }, []);
  const onKeyDown = useCallback((event: KeyboardEvent<HTMLElement>) => {
    if (["ArrowUp", "ArrowDown", "PageUp", "PageDown", "Home", "End", " "].includes(event.key)) note();
  }, [note]);
  // `[2026-10-23]` Pressing 「따라가기」 is the customer asking the screen to scroll: forget their last wheel or touch. Otherwise the screen's own scroll that follows,
  // within `USER_MS` of a wheel just before the press, was read as theirs and turned the following off again (the pill stayed — stop-ask-flow e2e, fast runs only).
  const resume = useCallback(() => { touched.current = 0; setFollowing(true); }, []);

  return { following, resume, handlers: { onScroll, onWheel: note, onTouchMove: note, onPointerDown, onKeyDown } };
}
