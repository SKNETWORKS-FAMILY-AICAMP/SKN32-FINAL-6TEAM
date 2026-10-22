"use client";

import { useEffect, useRef } from "react";

/**
 * `[2026-10-22 사용자 결정 — ST4F-719 · 목업 ②]` A row that slides sideways (the chat's chip row, the alternatives' cards). A finger scrolls it as the browser does (`touch-action: pan-x`
 * in the CSS, `data-slide`); a mouse drags it or turns its wheel (up and down move it sideways). A drag of more than 6 px is not a press of the chip it ended on. Only the side that has more
 * is faded (`data-more-left` · `data-more-right`). When `resetKey` changes (other chips) the row starts again at its beginning.
 * The row carries `data-no-swipe` in its markup, so the chat pane's own swipe back to the plan (`useDayGestures`) does not start on it.
 */
export function useSlide<T extends HTMLElement>(resetKey: string) {
  const ref = useRef<T>(null);
  useEffect(() => {
    const row = ref.current;
    if (!row) return;
    row.scrollLeft = 0;
    const edges = () => {
      const max = row.scrollWidth - row.clientWidth;
      row.toggleAttribute("data-more-left", row.scrollLeft > 2);
      row.toggleAttribute("data-more-right", row.scrollLeft < max - 2);
    };
    edges();
    const onWheel = (event: WheelEvent) => {
      if (row.scrollWidth <= row.clientWidth || Math.abs(event.deltaX) >= Math.abs(event.deltaY)) return;
      event.preventDefault();
      row.scrollLeft += event.deltaY;
    };
    let drag: { id: number; x: number; left: number; moved: boolean } | null = null;
    let draggedAt = 0;
    const onDown = (event: PointerEvent) => {
      if (event.pointerType !== "mouse" || event.button !== 0 || row.scrollWidth <= row.clientWidth) return;
      drag = { id: event.pointerId, x: event.clientX, left: row.scrollLeft, moved: false };
    };
    const onMove = (event: PointerEvent) => {
      if (!drag || event.pointerId !== drag.id) return;
      const dx = event.clientX - drag.x;
      if (!drag.moved && Math.abs(dx) < 6) return;
      if (!drag.moved) { drag.moved = true; row.setPointerCapture(event.pointerId); row.setAttribute("data-dragging", ""); }
      row.scrollLeft = drag.left - dx;
    };
    const onEnd = () => { if (drag?.moved) draggedAt = Date.now(); drag = null; row.removeAttribute("data-dragging"); };
    const onClick = (event: MouseEvent) => { if (Date.now() - draggedAt < 300) { event.preventDefault(); event.stopPropagation(); } };
    const resize = new ResizeObserver(edges);
    resize.observe(row);
    row.addEventListener("scroll", edges, { passive: true });
    row.addEventListener("wheel", onWheel, { passive: false });
    row.addEventListener("pointerdown", onDown);
    row.addEventListener("pointermove", onMove);
    row.addEventListener("pointerup", onEnd);
    row.addEventListener("pointercancel", onEnd);
    row.addEventListener("click", onClick, { capture: true });
    return () => {
      resize.disconnect();
      row.removeEventListener("scroll", edges);
      row.removeEventListener("wheel", onWheel);
      row.removeEventListener("pointerdown", onDown);
      row.removeEventListener("pointermove", onMove);
      row.removeEventListener("pointerup", onEnd);
      row.removeEventListener("pointercancel", onEnd);
      row.removeEventListener("click", onClick, { capture: true });
    };
  }, [resetKey]);
  return ref;
}
