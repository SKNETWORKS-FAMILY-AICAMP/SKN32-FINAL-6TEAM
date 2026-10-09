"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent, type RefObject, type UIEvent } from "react";
import { dampedScrollTo } from "@/lib/damped-scroll";

/** How close (px) to the bottom still counts as 「at the bottom」 — the list is then followed again. */
export const NEAR_BOTTOM_PX = 48;
/** Room (px) left between the followed row and the edge of the list. */
export const FOLLOW_MARGIN_PX = 12;
/** A scroll this soon after the customer's wheel, touch, key or press is theirs (not the screen following the check). */
const USER_MS = 1200;

/**
 * How far to scroll (px, + down) so `target` is inside `box`, leaving `margin`; 0 when it already is. Pure, so the rule is tested
 * without a browser. A row taller than the box is brought to its top instead of being chased.
 */
export function scrollDelta(box: { top: number; bottom: number }, target: { top: number; bottom: number }, margin = FOLLOW_MARGIN_PX, align: "nearest" | "center" = "nearest"): number {
  if (target.bottom - target.top > box.bottom - box.top - margin * 2) return target.top - box.top - margin;
  if (align === "center") return (target.top + target.bottom - box.top - box.bottom) / 2;
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
export function useFollowScroll(box: RefObject<HTMLElement | null>, find: (box: HTMLElement) => HTMLElement | null, enabled: boolean, change: unknown, align: "nearest" | "center" = "nearest") {
  const [following, setFollowing] = useState(true);
  const touched = useRef(0);

  useEffect(() => {
    const element = box.current;
    if (!element || !enabled || align !== "center") return;
    // Reserve room below the last row, so it can reach the middle too; remove it once the result is ready.
    const resize = () => element.style.setProperty("--follow-room", `${element.clientHeight / 2}px`);
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
    const delta = scrollDelta(element.getBoundingClientRect(), target.getBoundingClientRect(), FOLLOW_MARGIN_PX, align);
    if (Math.abs(delta) < 1) return;
    // ★`[2026-10-06 사용자 지적]` A damped spring, not the browser's fixed smooth scroll that restarts at every row (it looked jerky): the list eases towards the newest row and keeps its speed as rows are added.
    dampedScrollTo(element, element.scrollTop + delta);
  }, [box, find, enabled, following, change, align]);

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
  const resume = useCallback(() => setFollowing(true), []);

  return { following, resume, handlers: { onScroll, onWheel: note, onTouchMove: note, onPointerDown, onKeyDown } };
}
