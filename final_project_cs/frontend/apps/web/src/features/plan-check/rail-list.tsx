"use client";

import { useEffect, useLayoutEffect, useRef, type ReactNode } from "react";
import { parseHm } from "./time-plan";
import { RAIL_PX_PER_MIN, railSpans, railY, type RailPoint, type RailRow } from "./time-rail";
import styles from "./plan-check.module.css";

/**
 * `[2026-10-12 사용자 결정 — 목업 Tripilot_personal/travel-careops/mockups/2026-10-12_타임라인_지금시각_목업.html]` The line at the left of a day's timeline, drawn to scale in one layer
 * over the rows: solid = the time spent at a stop (its dot to its end, closed by ⊖), dashed = only the time travelling (leaving → arriving), thin = waiting to leave, the free time
 * after arriving and any space a card or a line of text takes beyond its time. An opened card carries its solid line and ⊖ to the card's end, an opened way its dashes to its box's end.
 *
 * The rows say what they are with data attributes (the rest of the row is the screen's own): a stop `data-rail="stay"` with `data-start`/`data-end` ("HH:MM"), a way `data-rail="move"` with
 * `data-dep`/`data-arr`; `data-rail-open` when opened (its `article`, or its `[data-rail-box]`, is measured), `data-past` for a past row drawn small (not to scale).
 */

/** The centre of a stop's dot (and of its time and name) from the top of its row; a past row's small dot. */
const DOT_Y = 27.5, PAST_DOT_Y = 13;
/** The way's line of text is centred on when it leaves; it needs this much room above (half its 45 px box). */
const DEP_ROOM = 23;
/** The bottom of a stop's two-line time (start, and 「~end」 under it). */
const TIME_BOTTOM = 56;
/** The last stop of a day with no end: a short line that fades out (its end is not known). */
const OPEN_END_PX = 60;

/** Where 「now」 stands on this day: today (at `minute`), a day that is over (the line filled to its end), or none. */
export type RailNow = { kind: "today"; minute: number; label: string } | { kind: "over" };

type Segment = { kind: "stay" | "travel" | "free"; y1: number; y2: number; past?: boolean; fade?: boolean };

const minuteOf = (value: string | undefined) => (value ? parseHm(value) : null);

function readRow(row: HTMLElement): RailRow {
  return row.dataset.rail === "move"
    ? { kind: "move", depart: minuteOf(row.dataset.dep), arrive: minuteOf(row.dataset.arr) }
    : { kind: "stay", start: minuteOf(row.dataset.start), end: minuteOf(row.dataset.end) };
}

/** Lowest point a stop row's own content reaches (its card, or its past line) — the time column is fixed (`TIME_BOTTOM`) and may be stuck to the top while scrolling. */
function contentBottom(row: HTMLElement): number {
  const parts = Array.from(row.children).filter((child): child is HTMLElement => child instanceof HTMLElement && (child.tagName === "ARTICLE" || child.tagName === "DIV"));
  return Math.max(TIME_BOTTOM, ...parts.map((part) => part.offsetTop + part.offsetHeight + 4));
}

/**
 * Gives each row the height its time takes and draws the line. The rows are set top to bottom (a row's top depends on the rows above), and only ever to the height they need — a row is
 * never emptied first, so the list does not shrink for a moment and the scroll position is not clamped.
 */
function layoutRail(list: HTMLElement): RailPoint[] {
  const rows = Array.from(list.querySelectorAll<HTMLElement>(":scope > [data-rail]"));
  const spans = railSpans(rows.map(readRow));
  const segments: Segment[] = [];
  const caps: { y: number; past: boolean }[] = [];
  const points: RailPoint[] = [];
  let cursor: number | null = null;
  const free = (y1: number, y2: number) => { if (y2 - y1 > .5) segments.push({ kind: "free", y1, y2 }); };
  const px = (minutes: number) => Math.max(0, minutes) * RAIL_PX_PER_MIN;

  rows.forEach((row, index) => {
    const { from, to } = spans[index];
    const past = row.hasAttribute("data-past");
    const top = row.offsetTop;
    if (row.dataset.rail !== "move") {
      const dotY = top + (past ? PAST_DOT_Y : DOT_Y);
      if (cursor !== null) free(cursor, dotY);
      if (from !== null) points.push({ minute: from, y: dotY });
      if (past || from === null) {
        // A past stop is a thin line, not to scale; a stop with no time has nothing to scale by.
        row.style.minHeight = "";
        const end = top + row.offsetHeight;
        segments.push(past ? { kind: "stay", y1: dotY, y2: end, past: true } : { kind: "free", y1: dotY, y2: end });
        if (past && to !== null) points.push({ minute: to, y: end });
        cursor = end;
        return;
      }
      const lastStop = !rows.slice(index + 1).some((other) => other.dataset.rail !== "move");
      let length = to === null ? (lastStop ? OPEN_END_PX : 0) : px(to - from);
      const card = row.hasAttribute("data-rail-open") ? row.querySelector<HTMLElement>("article") : null;
      if (card) length = Math.max(length, card.offsetTop + card.offsetHeight - DOT_Y);
      row.style.minHeight = `${DOT_Y + length}px`;
      const pastOpen = row.hasAttribute("data-past-open");
      segments.push({ kind: "stay", y1: dotY, y2: dotY + length, past: pastOpen, fade: to === null });
      if (to !== null) caps.push({ y: dotY + length, past: pastOpen });
      if (to !== null) points.push({ minute: to, y: dotY + length });
      cursor = dotY + length;
      return;
    }
    if (cursor !== null) free(cursor, top);
    if (past) {
      row.style.minHeight = "";
      row.style.removeProperty("--dep");
      const end = top + row.offsetHeight;
      segments.push({ kind: "free", y1: top, y2: end, past: true });
      if (from !== null) points.push({ minute: from, y: top });
      if (to !== null) points.push({ minute: to, y: end });
      cursor = end;
      return;
    }
    const { depart, arrive } = readRow(row) as Extract<RailRow, { kind: "move" }>;
    // The room the line of text may take above it, inside the stop row before (under its card and time).
    const before = rows[index - 1];
    const room = before && before.dataset.rail !== "move" && !before.hasAttribute("data-past") ? Math.max(0, before.offsetHeight - contentBottom(before)) : 0;
    if (depart === null || arrive === null || from === null || to === null || arrive < depart) {
      // Not known when it leaves and arrives: no dashes, a thin line for the time between the two stops.
      const length = from !== null && to !== null ? px(to - from) : 0;
      row.style.setProperty("--dep", `${Math.max(0, DEP_ROOM - room)}px`);
      row.style.minHeight = `${Math.max(0, length - DOT_Y)}px`;
      free(top, top + length);
      if (from !== null && to !== null) points.push({ minute: from, y: top }, { minute: to, y: top + length });
      cursor = top + length;
      return;
    }
    const wait = px(depart - from), after = px(to - arrive);
    const pad = Math.max(0, DEP_ROOM - wait - room);
    const departY = top + pad + wait;
    row.style.setProperty("--dep", `${pad + wait}px`);
    let travel = px(arrive - depart);
    const box = row.hasAttribute("data-rail-open") ? row.querySelector<HTMLElement>("[data-rail-box]") : null;
    if (box) travel = Math.max(travel, box.offsetTop + box.offsetHeight - (pad + wait));
    row.style.minHeight = `${Math.max(0, pad + wait + travel + after - DOT_Y)}px`;
    free(top, departY);
    segments.push({ kind: "travel", y1: departY, y2: departY + travel });
    free(departY + travel, departY + travel + after);
    points.push({ minute: from, y: top + pad }, { minute: depart, y: departY }, { minute: arrive, y: departY + travel }, { minute: to, y: departY + travel + after });
    cursor = departY + travel + after;
  });

  const lines = list.querySelector<HTMLElement>(":scope > [data-rail-lines]");
  lines?.replaceChildren(...segments.map((segment) => {
    const line = document.createElement("i");
    line.className = styles.railSeg;
    line.dataset.kind = segment.kind;
    if (segment.past) line.dataset.past = "";
    if (segment.fade) line.dataset.fade = "";
    line.style.top = `${segment.y1}px`;
    line.style.height = `${segment.y2 - segment.y1}px`;
    return line;
  }));
  const ends = list.querySelector<HTMLElement>(":scope > [data-rail-caps]");
  ends?.replaceChildren(...caps.map((cap) => {
    const mark = document.createElement("i");
    mark.className = styles.railCap;
    if (cap.past) mark.dataset.past = "";
    mark.style.top = `${cap.y}px`;
    return mark;
  }));
  return points;
}

/** 「지금」: the dot and its label at now's height, and the line filled from the day's first dot to it (to the end on a day that is over). Only moved — nothing is laid out again. */
function placeNow(list: HTMLElement, points: readonly RailPoint[], now: RailNow | null, smooth: boolean) {
  const fill = list.querySelector<HTMLElement>(":scope > [data-now-fill]");
  const mark = list.querySelector<HTMLElement>(":scope > [data-now-mark]");
  if (!fill || !mark) return;
  list.style.paddingBottom = "";
  if (!now || points.length === 0) { fill.style.display = "none"; mark.style.display = "none"; return; }
  const start = points[0].y;
  const last = Math.max(...points.map((point) => point.y));
  let y = last;
  if (now.kind === "today") {
    const at = railY(points, now.minute);
    // Before the first stop the mark stands at the top of its row: above its time (the label would cover 「12:30」), under the day's heading.
    y = Math.round(now.minute < points[0].minute ? start - DOT_Y + 4 : at ?? last + 6);
    // Past the day's last stop the mark stands under the list: room for its label, so it does not sit on what follows.
    if (now.minute >= points[0].minute && at === null) list.style.paddingBottom = "28px";
    mark.style.display = "";
    mark.style.transition = smooth ? "" : "none";
    mark.style.transform = `translateY(${y}px)`;
    const label = mark.querySelector<HTMLElement>("[data-now-label]");
    if (label) label.textContent = now.label;
  } else {
    mark.style.display = "none";
  }
  fill.style.display = "";
  fill.style.transition = smooth ? "" : "none";
  fill.style.top = `${start}px`;
  fill.style.height = `${Math.max(0, y - start)}px`;
}

/**
 * A day's `<ol>` with its line drawn to scale. It is laid out after every render and when its size changes (a card opened, the width, a font); `now` only moves the 「지금」 mark —
 * a minute passing does not rebuild or re-measure the list, so scrolling is not interrupted (2026-10-12 사용자 지적 — the mockup rebuilt its list every minute and the scroll stuck).
 */
export function RailList({ className, now = null, children }: { className: string; now?: RailNow | null; children: ReactNode }) {
  const list = useRef<HTMLOListElement>(null);
  const points = useRef<RailPoint[]>([]);
  const nowRef = useRef(now);
  const placed = useRef(false);
  useLayoutEffect(() => {
    nowRef.current = now;
    const element = list.current;
    if (!element) return;
    points.current = layoutRail(element);
    placeNow(element, points.current, nowRef.current, placed.current);
    placed.current = true;
  });
  useEffect(() => {
    const element = list.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const watcher = new ResizeObserver(() => { points.current = layoutRail(element); placeNow(element, points.current, nowRef.current, true); });
    watcher.observe(element);
    return () => watcher.disconnect();
  }, []);
  return <ol ref={list} className={className} data-rail-list>
    {children}
    <li className={styles.railLines} aria-hidden="true" data-rail-lines />
    <li className={styles.railCaps} aria-hidden="true" data-rail-caps />
    {now && <li className={styles.nowFill} aria-hidden="true" data-now-fill />}
    {now && <li className={styles.nowMark} aria-hidden="true" data-now-mark><span className={styles.nowDot} /><span className={styles.nowLabel} data-now-label /></li>}
  </ol>;
}
