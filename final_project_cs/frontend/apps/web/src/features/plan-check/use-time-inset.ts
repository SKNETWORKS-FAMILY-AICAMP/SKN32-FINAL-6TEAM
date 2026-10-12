"use client";

import { useLayoutEffect, type RefObject } from "react";

/** 펼친 일정의 시각이 날짜 선택 영역 아래에서 따라오도록 두 화면이 같은 여백을 잰다. */
export function useTimeInset(boxRef: RefObject<HTMLElement | null>, sheetRef: RefObject<HTMLElement | null>, enabled: boolean, layoutKey: string) {
  useLayoutEffect(() => {
    const box = boxRef.current;
    if (!enabled || !box) return;
    const header = sheetRef.current?.querySelector<HTMLElement>("header[data-float]");
    const measure = () => {
      const css = getComputedStyle(box);
      const overlayBottom = header ? header.getBoundingClientRect().bottom - parseFloat(getComputedStyle(header).paddingBottom) : box.getBoundingClientRect().top;
      const hiddenAbove = Math.max(0, overlayBottom - box.getBoundingClientRect().top);
      const inset = hiddenAbove - parseFloat(css.paddingTop) - parseFloat(css.getPropertyValue("--stop-time-lead"));
      box.style.setProperty("--time-stick-inset", `${inset}px`);
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(box);
    if (header) observer.observe(header);
    return () => observer.disconnect();
  }, [boxRef, enabled, layoutKey, sheetRef]);
}
