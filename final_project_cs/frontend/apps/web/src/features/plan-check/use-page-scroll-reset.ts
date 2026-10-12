"use client";

import { useEffect, useLayoutEffect, useRef, type RefObject } from "react";
import { cancelDampedScroll } from "@/lib/damped-scroll";

/** 새 목록은 지정한 위치에서 시작한다. 이전 화면을 넘긴 휠·터치의 꼬리는 이어 받지 않는다. */
export function usePageScrollReset(box: RefObject<HTMLElement | null>, pageKey: string, top: () => number) {
  const gate = useRef({ locked: false, lastWheel: 0 });
  const target = useRef(top);
  useLayoutEffect(() => { target.current = top; });
  useLayoutEffect(() => {
    const element = box.current;
    if (!element) return;
    cancelDampedScroll(element);
    gate.current = { locked: true, lastWheel: performance.now() };
    const overflow = element.style.overflowY;
    element.style.setProperty("overflow-y", "hidden");
    element.scrollTo({ top: target.current(), behavior: "instant" });
    const frame = requestAnimationFrame(() => { element.style.setProperty("overflow-y", overflow); });
    return () => { cancelAnimationFrame(frame); element.style.setProperty("overflow-y", overflow); };
  }, [box, pageKey]);
  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const wheel = (event: WheelEvent) => {
      const now = performance.now();
      if (gate.current.locked && now - gate.current.lastWheel < 380) event.preventDefault();
      else gate.current.locked = false;
      gate.current.lastWheel = now;
    };
    const start = () => { gate.current.locked = false; };
    const move = (event: TouchEvent) => { if (gate.current.locked) event.preventDefault(); };
    element.addEventListener("wheel", wheel, { passive: false, capture: true });
    element.addEventListener("touchstart", start, { passive: true });
    element.addEventListener("touchmove", move, { passive: false });
    return () => {
      element.removeEventListener("wheel", wheel, true);
      element.removeEventListener("touchstart", start);
      element.removeEventListener("touchmove", move);
    };
  }, [box]);
}
