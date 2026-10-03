"use client";

import { useEffect, useRef, useState, type RefObject } from "react";

/** How far (px) the customer must keep pushing past the end of the list before the next page opens. */
export const PULL_TO_OPEN = 110;
/** Pushes arriving this soon after the list reached its end are the scroll still coasting, not a new push. */
const SETTLE_MS = 320;
/** The push is let go this long after the last input; a wheel that pauses this long starts a new gesture. */
const IDLE_MS = 380;

export type PullEdge = "end" | "start";

/**
 * One input of pushing past an end of the list, in px (`delta` > 0 pushes further down, < 0 further up): the push grows while
 * it keeps going the same way at the same end, and is let go when it does not. Pure, so the rule is tested without a browser.
 */
export function pullStep(pull: number, delta: number, edge: PullEdge | null): number {
  const cap = PULL_TO_OPEN * 1.5;
  if (edge === "end" && delta > 0) return Math.min(cap, pull + delta);
  if (edge === "start" && delta < 0) return Math.min(cap, pull - delta);
  return 0;
}

/**
 * Which end of the list an input at `delta` pushes against. A list with nothing to scroll is at both ends at once: the direction
 * of the push then says which (found in review 2026-10-03: it was always the end, so a short list could not be pushed back).
 */
export function edgeFor(box: { scrollTop: number; clientHeight: number; scrollHeight: number }, delta: number): PullEdge | null {
  const atEnd = box.scrollTop + box.clientHeight >= box.scrollHeight - 2;
  const atStart = box.scrollTop <= 0;
  if (atEnd && atStart) return delta < 0 ? "start" : "end";
  return atEnd ? "end" : atStart ? "start" : null;
}

/**
 * `[2026-10-03 사용자 지시]` Pushing on once the list is at its end opens the next page, the way the first screens of the app
 * turn when they are scrolled (`onEnd`); pushing the other way at the top comes back (`onStart`). Each end is only listened to
 * when its callback is given. Returns how far the push has got (0–1) and which end, for a hint that fills as it goes.
 *
 * ★A push counts only when it is a gesture of its own, started at the end (found in review 2026-10-03):
 *   - a wheel counts only after a pause since the last wheel input — a long coast of the same flick that brought the list to its
 *     end is not a push, however long it lasts;
 *   - a touch counts only if it began while the list stood at that end, and only against that end (a touch that began at the top
 *     and scrolled down to the bottom does not go on to push there).
 */
export function usePullPastEnd(box: RefObject<HTMLElement | null>, { onEnd, onStart }: { onEnd?: () => void; onStart?: () => void }): { progress: number; edge: PullEdge | null } {
  const [state, setState] = useState<{ pull: number; edge: PullEdge | null }>({ pull: 0, edge: null });
  const handlers = useRef({ onEnd, onStart });
  useEffect(() => { handlers.current = { onEnd, onStart }; });
  const enabled = Boolean(onEnd) || Boolean(onStart);

  useEffect(() => {
    const element = box.current;
    if (!element || !enabled) return;
    let pull = 0;
    // Already at an end when this starts (a short list, or the screen just opened): it has been there "for a long time", so the first push counts.
    let at: PullEdge | null = edgeFor(element, 0);
    let arrived = 0;
    let lastWheel = 0;
    let wheelAllowed = false;
    let idle: ReturnType<typeof setTimeout> | undefined;
    let touchY: number | null = null;
    let touchEdge: PullEdge | null = null;
    let cooldown = 0;
    const show = (next: number, edge: PullEdge | null) => { pull = next; setState({ pull: next, edge: next ? edge : null }); };
    const letGo = () => show(0, null);
    const push = (delta: number, edge: PullEdge | null) => {
      if (Date.now() < cooldown) return;
      const callback = edge === "end" ? handlers.current.onEnd : edge === "start" ? handlers.current.onStart : undefined;
      const next = callback ? pullStep(pull, delta, edge) : 0;
      show(next, edge);
      clearTimeout(idle);
      if (next >= PULL_TO_OPEN && callback) {
        cooldown = Date.now() + 900;
        letGo();
        callback();
      } else if (next) idle = setTimeout(letGo, IDLE_MS);
    };
    const arrive = (edge: PullEdge | null) => {
      if (edge === at) return;
      at = edge;
      arrived = Date.now();
      wheelAllowed = false;
    };
    const onScroll = () => {
      const edge = edgeFor(element, 0);
      arrive(edge);
      if (!edge) letGo();
    };
    const onWheel = (event: WheelEvent) => {
      const now = Date.now();
      arrive(edgeFor(element, 0));                       // where the list stands (not which way this input pushes)
      const edge = edgeFor(element, event.deltaY);
      if (now - lastWheel > IDLE_MS) wheelAllowed = Boolean(edge) && now - arrived >= SETTLE_MS;     // a new gesture, at rest at the end
      lastWheel = now;
      if (!edge || !wheelAllowed) return;
      push(event.deltaY, edge);
    };
    const onTouchStart = (event: TouchEvent) => {
      touchEdge = edgeFor(element, 0);
      touchY = touchEdge ? event.touches[0].clientY : null;
    };
    const onTouchMove = (event: TouchEvent) => {
      if (touchY === null) return;
      const y = event.touches[0].clientY;
      const delta = touchY - y;                 // the finger moves up = the list is pushed further down
      touchY = y;
      const edge = edgeFor(element, delta);
      if (edge !== touchEdge) { touchY = null; letGo(); return; }       // left the end it began at: not a push any more
      push(delta, edge);
    };
    const onTouchEnd = () => { touchY = null; touchEdge = null; letGo(); };
    element.addEventListener("scroll", onScroll, { passive: true });
    element.addEventListener("wheel", onWheel, { passive: true });
    element.addEventListener("touchstart", onTouchStart, { passive: true });
    element.addEventListener("touchmove", onTouchMove, { passive: true });
    element.addEventListener("touchend", onTouchEnd, { passive: true });
    element.addEventListener("touchcancel", onTouchEnd, { passive: true });
    return () => {
      clearTimeout(idle);
      element.removeEventListener("scroll", onScroll);
      element.removeEventListener("wheel", onWheel);
      element.removeEventListener("touchstart", onTouchStart);
      element.removeEventListener("touchmove", onTouchMove);
      element.removeEventListener("touchend", onTouchEnd);
      element.removeEventListener("touchcancel", onTouchEnd);
    };
  }, [box, enabled]);

  return { progress: Math.min(1, state.pull / PULL_TO_OPEN), edge: state.edge };
}
