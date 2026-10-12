"use client";

import { useEffect, useState, type RefObject } from "react";

/** Keep the final action available at the actual end, including fractional scroll positions. */
export function useListEnd(box: RefObject<HTMLElement | null>, enabled: boolean) {
  const [atEnd, setAtEnd] = useState(false);
  useEffect(() => {
    const element = box.current;
    if (!element || !enabled) return;
    let frame = 0;
    const measure = () => {
      frame = 0;
      setAtEnd(element.clientHeight > 0 && element.scrollHeight - element.clientHeight - element.scrollTop <= 2);
    };
    const schedule = () => { if (!frame) frame = requestAnimationFrame(measure); };
    const resize = new ResizeObserver(schedule);
    const observe = () => {
      resize.disconnect();
      resize.observe(element);
      for (const child of element.children) resize.observe(child);
      schedule();
    };
    const content = new MutationObserver(observe);
    content.observe(element, { childList: true, subtree: true });
    element.addEventListener("scroll", schedule, { passive: true });
    observe();
    return () => {
      element.removeEventListener("scroll", schedule);
      content.disconnect();
      resize.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [box, enabled]);
  return enabled && atEnd;
}
