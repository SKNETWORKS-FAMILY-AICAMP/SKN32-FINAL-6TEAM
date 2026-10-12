"use client";

import { useCallback, useLayoutEffect, useRef, type RefObject } from "react";

/** 검증 화면과 등록 여행이 함께 쓰는 날짜 표시. 숨김·글꼴·탭 폭 변경에도 다시 잰다. */
export function useDayMarker(stripRef: RefObject<HTMLElement | null>, markerRef: RefObject<HTMLElement | null>, active: number, layoutKey: string) {
  const progress = useRef({ shift: 0, width: 1 });
  const placeMarker = useCallback((shift = 0, width = 1) => {
    progress.current = { shift, width };
    const strip = stripRef.current, marker = markerRef.current;
    if (!strip || !marker || !strip.clientWidth) return;
    const tabs = Array.from(strip.querySelectorAll<HTMLElement>('[role="tab"]'));
    const here = tabs[active];
    if (!here) return;
    const toward = shift < 0 ? tabs[active + 1] : shift > 0 ? tabs[active - 1] : undefined;
    const part = toward ? Math.min(1, Math.abs(shift) / Math.max(1, width * 0.4)) : 0;
    marker.style.setProperty("transform", `translateX(${here.offsetLeft + (toward ? (toward.offsetLeft - here.offsetLeft) * part : 0)}px)`);
    marker.style.setProperty("width", `${here.offsetWidth + (toward ? (toward.offsetWidth - here.offsetWidth) * part : 0)}px`);
    strip.toggleAttribute("data-dragging", shift !== 0);
    tabs.forEach((tab, index) => tab.toggleAttribute("data-lit", index === (toward && part > 0.5 ? active + (shift < 0 ? 1 : -1) : active)));
  }, [active, markerRef, stripRef]);

  useLayoutEffect(() => {
    placeMarker();
    stripRef.current?.querySelectorAll<HTMLElement>('[role="tab"]')[active]?.scrollIntoView({ inline: "nearest", block: "nearest" });
  }, [active, layoutKey, placeMarker, stripRef]);

  useLayoutEffect(() => {
    const strip = stripRef.current;
    if (!strip) return;
    let live = true;
    const measure = () => { if (live) placeMarker(progress.current.shift, progress.current.width); };
    const observer = new ResizeObserver(measure);
    observer.observe(strip, { box: "border-box" });
    strip.querySelectorAll<HTMLElement>('[role="tab"]').forEach((tab) => observer.observe(tab, { box: "border-box" }));
    void document.fonts.ready.then(measure);
    return () => { live = false; observer.disconnect(); };
  }, [layoutKey, placeMarker, stripRef]);
  return placeMarker;
}
