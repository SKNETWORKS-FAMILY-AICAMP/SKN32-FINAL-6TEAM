"use client";

import { useEffect, useRef, type RefObject } from "react";

/** A press that moves this far (px) sideways (more than up and down) is a swipe; one that moves up and down first is the list's own scrolling. */
const LOCK_PX = 8;
/** Letting go past this part of the list's width turns the day. */
export const COMMIT_FRACTION = 0.28;
/** Or a flick this fast (px per ms) in the direction of the turn. */
const COMMIT_SPEED = 0.45;
/** At the first or the last day the list gives way only this part of what the finger moved, and no further than `RUBBER_MAX`: a rubber band. */
const RUBBER = 0.3;
const RUBBER_MAX = 88;
const SETTLE_MS = 240;
/** Not moving for this long (ms) before the finger is lifted: it was not a flick. */
const STOP_MS = 90;
/** What a pinch may show while the fingers are down (the zoom of the list), and where it counts as 「as far out as it goes」 / 「as far in as it goes」. */
export const PINCH_RANGE = { min: 0.55, max: 1.6 } as const;

/** The pure rule of a sideways drag: how far the list moves for a finger that has moved `dx` px, and whether letting go there turns the day. Tested without a browser. */
export function swipeStep(dx: number, width: number, neighbour: boolean): { shift: number; armed: boolean } {
  if (!neighbour) return { shift: Math.sign(dx) * Math.min(Math.abs(dx) * RUBBER, RUBBER_MAX), armed: false };
  const shift = Math.max(-width, Math.min(width, dx));
  return { shift, armed: Math.abs(shift) >= width * COMMIT_FRACTION };
}

export function turnsDay(shift: number, width: number, speed: number, neighbour: boolean): boolean {
  if (!neighbour || !width) return false;
  return Math.abs(shift) >= width * COMMIT_FRACTION || (Math.abs(speed) >= COMMIT_SPEED && Math.sign(speed) === Math.sign(shift) && Math.abs(shift) > 12);
}

export interface DayGestures {
  /** Sideways swipes are listened to (a day is shown, nothing else is being dragged). */
  swipe: boolean;
  hasPrev: boolean;
  hasNext: boolean;
  /** The element that follows the finger, and the one whose pointer events are listened to. */
  track: () => HTMLElement | null;
  /** Which neighbour is being drawn (-1 the previous day, 1 the next, 0 none), with where the list is scrolled to (the neighbour starts there). `edge`: no day on that side. */
  onPeek: (side: -1 | 0 | 1, top: number, edge: boolean) => void;
  /** How far the list is dragged (-1..1 of its width; positive = toward the next day) and whether letting go would turn the day - said on every move, for the chips. */
  onProgress: (shift: number, width: number, armed: boolean) => void;
  /** The day turns (after the list has slid out). */
  onTurn: (delta: 1 | -1) => void;
  /** Two fingers are pinching the list: the zoom they ask for now, while they are down; and once they are let go. */
  pinch: boolean;
  zoom: number;
  onPinch: (zoom: number) => void;
  onPinchEnd: (zoom: number) => void;
}

/**
 * `[2026-10-05 사용자 요청 — 날짜 전환 애니메이션 · 두 손가락 확대]` The gestures of the day list. ★The list FOLLOWS the finger sideways, with the neighbouring day moving along beside it
 * (`onPeek`); letting go past a line (`COMMIT_FRACTION`) or with a flick turns the day, otherwise the list springs back; at the first and last day it gives way like a rubber band. Two fingers
 * pinching the list ask for a zoom (`onPinch`, and `onPinchEnd` when let go). Pointer events, so a mouse drag does the same; presses that start on an input or on what drags a time are not swipes.
 */
export function useDayGestures(box: RefObject<HTMLElement | null>, options: DayGestures) {
  const latest = useRef(options);
  useEffect(() => { latest.current = options; });
  const enabled = options.swipe || options.pinch;

  useEffect(() => {
    const element = box.current;
    if (!element || !enabled) return;
    const pointers = new Map<number, { x: number; y: number }>();
    let swipe: { id: number; x0: number; y0: number; lock: "none" | "h" | "v"; shift: number; speed: number; lastX: number; lastT: number; neighbour: boolean; armed: boolean; side: -1 | 1; peeked: boolean } | null = null;
    let pinch: { d0: number; zoom0: number; zoom: number } | null = null;
    let settling: ReturnType<typeof setTimeout> | undefined;

    const track = () => latest.current.track();
    const place = (value: number, animate: boolean) => {
      const target = track();
      if (!target) return;
      target.style.transition = animate ? `transform ${SETTLE_MS}ms cubic-bezier(.2, .8, .2, 1)` : "none";
      target.style.transform = value ? `translateX(${value}px)` : "";
    };
    const finish = () => {
      place(0, false);
      latest.current.onPeek(0, 0, false);
      latest.current.onProgress(0, 1, false);
      const target = track();
      if (target) target.removeAttribute("data-armed");
      swipe = null;
    };
    const distance = () => {
      const [a, b] = [...pointers.values()];
      return a && b ? Math.hypot(a.x - b.x, a.y - b.y) : 0;
    };

    const onDown = (event: PointerEvent) => {
      if (event.pointerType === "mouse" && event.button !== 0) return;
      const target = event.target as Element | null;
      // ★The time and its dot (`[data-grab]`) are taken by a vertical drag (the time changes), but a SIDEWAYS move that starts there is still a swipe of the day: the lock below tells them apart
      //   (up and down first = not ours). Without this the left 44 px of the list - where a swipe back to the previous day often starts - could not be swiped from.
      if (target?.closest("input, textarea, select, [data-no-swipe]")) return;
      pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (pointers.size === 2 && latest.current.pinch) {
        if (swipe?.lock === "h") { clearTimeout(settling); place(0, true); settling = setTimeout(finish, SETTLE_MS); }
        swipe = null;
        const d0 = distance();
        pinch = d0 > 0 ? { d0, zoom0: latest.current.zoom, zoom: latest.current.zoom } : null;
        return;
      }
      if (pointers.size === 1 && latest.current.swipe && !swipe) {
        clearTimeout(settling);
        finish();
        swipe = { id: event.pointerId, x0: event.clientX, y0: event.clientY, lock: "none", shift: 0, speed: 0, lastX: event.clientX, lastT: event.timeStamp, neighbour: false, armed: false, side: 1, peeked: false };
      }
    };

    const onMove = (event: PointerEvent) => {
      if (!pointers.has(event.pointerId)) return;
      pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
      if (pinch) {
        const zoom = Math.min(PINCH_RANGE.max, Math.max(PINCH_RANGE.min, pinch.zoom0 * (distance() / pinch.d0)));
        pinch.zoom = zoom;
        latest.current.onPinch(zoom);
        return;
      }
      if (!swipe || swipe.id !== event.pointerId || swipe.lock === "v") return;
      const dx = event.clientX - swipe.x0, dy = event.clientY - swipe.y0;
      if (swipe.lock === "none") {
        if (Math.abs(dy) > LOCK_PX && Math.abs(dy) >= Math.abs(dx)) { swipe.lock = "v"; return; }       // the list's own scrolling
        if (Math.abs(dx) <= LOCK_PX || Math.abs(dx) < Math.abs(dy) * 1.2) return;
        swipe.lock = "h";
        try { element.setPointerCapture(event.pointerId); } catch { /* a pointer the browser does not know (a synthetic one): the events still arrive from the list itself */ }
      }
      const width = element.clientWidth || 1;
      const side: -1 | 1 = dx < 0 ? 1 : -1;                               // dragging left = the NEXT day comes in
      const neighbour = side === 1 ? latest.current.hasNext : latest.current.hasPrev;
      // The neighbour that is drawn follows the side the finger is on: it is asked for at the first move and again whenever the finger crosses to the other side.
      if (!swipe.peeked || side !== swipe.side || neighbour !== swipe.neighbour) {
        swipe.side = side;
        swipe.neighbour = neighbour;
        swipe.peeked = true;
        latest.current.onPeek(side, element.scrollTop, !neighbour);
      }
      const step = swipeStep(dx, width, neighbour);
      const dt = event.timeStamp - swipe.lastT;
      if (dt > 0) swipe.speed = 0.7 * swipe.speed + 0.3 * ((event.clientX - swipe.lastX) / dt);
      swipe.lastX = event.clientX;
      swipe.lastT = event.timeStamp;
      if (step.armed !== swipe.armed) {
        swipe.armed = step.armed;
        const target = track();
        if (target) { if (step.armed) target.setAttribute("data-armed", ""); else target.removeAttribute("data-armed"); }
        if (step.armed) { try { navigator.vibrate?.(8); } catch { /* no vibration here */ } }
      }
      swipe.shift = step.shift;
      place(step.shift, false);
      latest.current.onProgress(step.shift, width, step.armed);
    };

    const onUp = (event: PointerEvent) => {
      if (!pointers.has(event.pointerId)) return;
      pointers.delete(event.pointerId);
      if (pinch) {
        if (pointers.size < 2) { const done = pinch.zoom; pinch = null; latest.current.onPinchEnd(done); }
        return;
      }
      if (!swipe || swipe.id !== event.pointerId) return;
      const taken = swipe;
      if (taken.lock !== "h") { swipe = null; return; }
      try { if (element.hasPointerCapture(event.pointerId)) element.releasePointerCapture(event.pointerId); } catch { /* nothing held */ }
      const width = element.clientWidth || 1;
      const cancelled = event.type === "pointercancel";
      // A finger that stopped before it was lifted is no flick: the speed is the speed at the end, not the last one it had.
      if (event.timeStamp - taken.lastT > STOP_MS) taken.speed = 0;
      if (!cancelled && turnsDay(taken.shift, width, taken.speed, taken.neighbour)) {
        place(-taken.side * width, true);                                  // the list slides out, the neighbour in; then the day itself turns
        settling = setTimeout(() => { latest.current.onTurn(taken.side); finish(); }, SETTLE_MS + 10);
      } else {
        place(0, true);                                                    // springs back (at an end: back from the rubber band)
        settling = setTimeout(finish, SETTLE_MS + 10);
      }
    };

    element.addEventListener("pointerdown", onDown, { passive: true });
    element.addEventListener("pointermove", onMove, { passive: true });
    element.addEventListener("pointerup", onUp, { passive: true });
    element.addEventListener("pointercancel", onUp, { passive: true });
    return () => {
      clearTimeout(settling);
      element.removeEventListener("pointerdown", onDown);
      element.removeEventListener("pointermove", onMove);
      element.removeEventListener("pointerup", onUp);
      element.removeEventListener("pointercancel", onUp);
      finish();
    };
  }, [box, enabled]);
}
