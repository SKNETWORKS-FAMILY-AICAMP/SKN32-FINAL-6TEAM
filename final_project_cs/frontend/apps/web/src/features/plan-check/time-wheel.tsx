"use client";

import { Fragment, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type MouseEvent, type PointerEvent } from "react";
import { useSettings, useT } from "@/lib/settings";
import { SNAP } from "./time-plan";
import styles from "./plan-check.module.css";

/** One row of the wheel (px). Five rows show; the middle one is the value. */
const ROW = 34;
/** The hour and the minute go round: each is drawn this many times over so a flick never reaches an end, and is put back in the middle copy when it stops. */
const COPIES = 9;
const MIDDLE = 4;
/** No scrolling for this long (ms) and a column has stopped. */
const SETTLE_MS = 120;

type Part = "half" | "hour" | "minute";
/** Where the wheel stands: morning (0) or afternoon (1), the hour on the clock face (0 = 12), the 5 minutes (0 = :00, 11 = :55). */
export type WheelAt = Record<Part, number>;

const SIZE: Record<Part, number> = { half: 2, hour: 12, minute: 12 };
const LOOPS: Record<Part, boolean> = { half: false, hour: true, minute: true };
const rowsOf = (part: Part) => LOOPS[part] ? SIZE[part] * COPIES : SIZE[part];
const indexOf = (part: Part, row: number) => ((row % SIZE[part]) + SIZE[part]) % SIZE[part];
const homeRow = (part: Part, index: number) => (LOOPS[part] ? MIDDLE * SIZE[part] : 0) + index;
const clampRow = (part: Part, row: number) => Math.max(0, Math.min(rowsOf(part) - 1, row));

/** The wheel for a time of day (minutes after midnight). A time between two steps (09:07 typed) shows the step before it. */
export function wheelAt(minutes: number): WheelAt {
  const hour = Math.floor(minutes / 60) % 24;
  return { half: hour >= 12 ? 1 : 0, hour: hour % 12, minute: Math.floor((minutes % 60) / SNAP) };
}
export const wheelMinutes = (at: WheelAt) => (at.half * 12 + at.hour) * 60 + at.minute * SNAP;
/** Turning the hour across 11 ↔ 12 turns the morning into the afternoon and back, as a phone's clock does. `from` and `to` are rows of the looping hour column. */
export const crossesNoon = (from: number, to: number) => Math.abs(Math.floor(to / 12) - Math.floor(from / 12)) % 2 === 1;
/** The nearest step of the wheel inside `min`..`max` for a time outside it (a range that holds no step at all gives its own end). */
export function backInside(minutes: number, min: number, max: number): number {
  if (minutes < min) { const up = Math.ceil(min / SNAP) * SNAP; return up <= max ? up : min; }
  if (minutes > max) { const down = Math.floor(max / SNAP) * SNAP; return down >= min ? down : max; }
  return minutes;
}
/** 「오전 9:05」 · 「9:05 AM」 — what the wheel says, in the words of a phone's clock. */
export function clockText(minutes: number, english: boolean): string {
  const hour = Math.floor(minutes / 60) % 24;
  const face = hour % 12 || 12;
  const mm = String(minutes % 60).padStart(2, "0");
  return english ? `${face}:${mm} ${hour < 12 ? "AM" : "PM"}` : `${hour < 12 ? "오전" : "오후"} ${face}:${mm}`;
}
/** 「1시간 30분」 · 「1 h 30 min」. */
export function stayText(minutes: number, english: boolean): string {
  const hours = Math.floor(minutes / 60), rest = minutes % 60;
  const parts = [hours ? (english ? `${hours} h` : `${hours}시간`) : "", rest || !hours ? (english ? `${rest} min` : `${rest}분`) : ""];
  return parts.filter(Boolean).join(" ");
}

/**
 * ★`[2026-10-21 사용자 결정 — ST4F-702 A 휠]` The time picked on three wheels — 오전/오후 · 시 · 분 (5 minutes), as on a phone's alarm and calendar. The hour goes round and across 11 ↔ 12 it turns the
 * half of the day. Rows the time cannot take (outside `range`) are faint; a wheel that stops on one goes back to the nearest one it can take (`bounced` — the editor says why).
 * A finger turns it by the browser's own scrolling (snapped to the rows); a mouse drags or presses a row; the keyboard steps with the arrows.
 */
export function TimeWheel({ value, range, onPick, label, autoFocus = false }: {
  value: number;
  range: { min: number; max: number };
  /** Every new time while the wheel turns (`settled: false`), and where it stopped. */
  onPick: (minutes: number, how: { settled: boolean; bounced: boolean }) => void;
  label: string;
  autoFocus?: boolean;
}) {
  const t = useT();
  const { language } = useSettings();
  const english = language === "en";
  const nodes = useRef<Partial<Record<Part, HTMLDivElement | null>>>({});
  /** The row each column stands on, of all its copies. */
  const rows = useRef<WheelAt>((() => { const at = wheelAt(value); return { half: homeRow("half", at.half), hour: homeRow("hour", at.hour), minute: homeRow("minute", at.minute) }; })());
  const [at, setAt] = useState<WheelAt>(() => wheelAt(value));
  /** A column the code is turning (to this row): its scrolling is not the customer's, until it gets there or the customer takes it. */
  const target = useRef<Partial<Record<Part, number>>>({});
  const settling = useRef<Partial<Record<Part, number>>>({});
  const drag = useRef<{ part: Part; y: number; top: number; moved: boolean } | null>(null);
  const dragged = useRef(false);
  const said = useRef(value);
  const latest = useRef({ range, onPick });
  useLayoutEffect(() => { latest.current = { range, onPick }; });

  const now = (): WheelAt => ({ half: indexOf("half", rows.current.half), hour: indexOf("hour", rows.current.hour), minute: indexOf("minute", rows.current.minute) });
  const smooth = (): ScrollBehavior => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth";
  /** The code turns a column to a row. */
  const turn = (part: Part, row: number, how: ScrollBehavior) => {
    const node = nodes.current[part];
    rows.current[part] = clampRow(part, row);
    if (!node || Math.abs(node.scrollTop - rows.current[part] * ROW) <= 0.5) return;
    target.current[part] = rows.current[part];
    node.scrollTo({ top: rows.current[part] * ROW, behavior: how });
  };
  /** The whole wheel to a time (each looping column the short way round). What it shows follows when the columns get there (`scrolled`). */
  const show = (minutes: number, how: ScrollBehavior) => {
    const want = wheelAt(minutes);
    for (const part of ["half", "hour", "minute"] as const) {
      const row = rows.current[part];
      const base = row - indexOf(part, row) + want[part];
      const pick = LOOPS[part] ? [base - SIZE[part], base, base + SIZE[part]].reduce((a, b) => Math.abs(b - row) < Math.abs(a - row) ? b : a) : want[part];
      turn(part, pick, how);
    }
  };
  /** The customer turns a column to a row (a key, a press of a row, the end of a mouse drag): the scrolling that follows is theirs. */
  const take = (part: Part, row: number) => {
    delete target.current[part];
    nodes.current[part]?.scrollTo({ top: clampRow(part, row) * ROW, behavior: smooth() });
  };

  const stopped = (part: Part) => {
    const node = nodes.current[part];
    delete settling.current[part];
    if (!node) return;
    // A column the code is still turning (keys) stops where it is going, not where its scrolling has got to.
    let row = target.current[part] ?? clampRow(part, Math.round(node.scrollTop / ROW));
    if (LOOPS[part]) row = homeRow(part, indexOf(part, row));                    // back to the middle copy, unseen
    turn(part, row, "auto");
    if (Object.keys(settling.current).length) return;                            // another column is still turning
    const next = now();
    setAt(next);
    const minutes = wheelMinutes(next);
    const { min, max } = latest.current.range;
    const back = backInside(minutes, min, max);
    if (back !== minutes) show(back, smooth());
    said.current = back;
    latest.current.onPick(back, { settled: true, bounced: back !== minutes });
  };
  const scrolled = (part: Part) => {
    const node = nodes.current[part];
    if (!node) return;
    const going = target.current[part];
    if (going !== undefined) {
      if (Math.abs(node.scrollTop - going * ROW) < 1) { delete target.current[part]; setAt(now()); }
      return;
    }
    const row = clampRow(part, Math.round(node.scrollTop / ROW));
    if (row !== rows.current[part]) {
      if (part === "hour" && crossesNoon(rows.current.hour, row)) turn("half", 1 - rows.current.half, smooth());
      rows.current[part] = row;
      const next = now();
      setAt(next);
      const minutes = wheelMinutes(next);
      if (minutes !== said.current) { said.current = minutes; latest.current.onPick(minutes, { settled: false, bounced: false }); }
    }
    window.clearTimeout(settling.current[part]);
    settling.current[part] = window.setTimeout(() => stopped(part), SETTLE_MS);
  };

  useLayoutEffect(() => {
    for (const part of ["half", "hour", "minute"] as const) turn(part, rows.current[part], "auto");
    if (autoFocus) nodes.current[english ? "hour" : "half"]?.focus({ preventScroll: true });
    const timers = settling.current;
    return () => { for (const timer of Object.values(timers)) window.clearTimeout(timer); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- placed once; the value is followed below
  // A time set from outside (typed, the other field, the switch for pushing): the wheel goes there - unless the customer is turning it just now.
  useEffect(() => {
    if (Object.keys(settling.current).length || drag.current) return;
    const want = wheelAt(value), have = now();
    if (want.half === have.half && want.hour === have.hour && want.minute === have.minute) return;
    said.current = value;
    show(value, smooth());
  }, [value]); // eslint-disable-line react-hooks/exhaustive-deps -- only a new value moves the wheel

  const labels: Record<Part, string[]> = {
    half: english ? ["AM", "PM"] : ["오전", "오후"],
    hour: ["12", ...Array.from({ length: 11 }, (_, index) => String(index + 1))],
    minute: Array.from({ length: 12 }, (_, index) => String(index * SNAP).padStart(2, "0")),
  };
  const fits = (from: number, to: number) => to >= range.min && from <= range.max;
  const allowed = (part: Part, index: number) => part === "half" ? fits(index * 720, index * 720 + 719)
    : part === "hour" ? fits((at.half * 12 + index) * 60, (at.half * 12 + index) * 60 + 60 - SNAP)
      : fits(wheelMinutes({ ...at, minute: index }), wheelMinutes({ ...at, minute: index }));
  const names: Record<Part, string> = { half: t("오전 오후", "AM PM"), hour: t("시", "Hour"), minute: t("분", "Minute") };
  const order: Part[] = english ? ["hour", "minute", "half"] : ["half", "hour", "minute"];

  // A key moves the column at once (the value follows the key, not the scrolling - keys pressed fast each count) and the column scrolls after it.
  const onKey = (part: Part) => (event: KeyboardEvent<HTMLDivElement>) => {
    const by = ({ ArrowUp: -1, ArrowDown: 1, PageUp: -3, PageDown: 3 } as Record<string, number>)[event.key];
    if (!by) return;
    event.preventDefault();
    event.stopPropagation();
    const from = rows.current[part], to = clampRow(part, from + by);
    if (part === "hour" && crossesNoon(from, to)) turn("half", 1 - rows.current.half, smooth());
    turn(part, to, smooth());
    const next = now();
    setAt(next);
    const minutes = wheelMinutes(next);
    if (minutes !== said.current) { said.current = minutes; latest.current.onPick(minutes, { settled: false, bounced: false }); }
    window.clearTimeout(settling.current[part]);
    settling.current[part] = window.setTimeout(() => stopped(part), SETTLE_MS * 3);
  };
  const onDown = (part: Part) => (event: PointerEvent<HTMLDivElement>) => {
    delete target.current[part];
    if (event.pointerType !== "mouse" || event.button !== 0) return;
    const node = event.currentTarget;
    event.preventDefault();
    node.focus({ preventScroll: true });
    drag.current = { part, y: event.clientY, top: node.scrollTop, moved: false };
    node.dataset.dragging = "";
    node.setPointerCapture(event.pointerId);
  };
  const onMove = (event: PointerEvent<HTMLDivElement>) => {
    const held = drag.current;
    if (!held) return;
    const dy = event.clientY - held.y;
    if (Math.abs(dy) > 3) held.moved = true;
    event.currentTarget.scrollTop = held.top - dy;
  };
  const onUp = (event: PointerEvent<HTMLDivElement>) => {
    const held = drag.current;
    drag.current = null;
    if (!held) return;
    const node = event.currentTarget;
    delete node.dataset.dragging;
    if (node.hasPointerCapture(event.pointerId)) node.releasePointerCapture(event.pointerId);
    dragged.current = held.moved;
    if (held.moved) take(held.part, Math.round(node.scrollTop / ROW));
  };
  const onTap = (part: Part) => (event: MouseEvent<HTMLDivElement>) => {
    if (dragged.current) { dragged.current = false; return; }
    const row = (event.target as HTMLElement).closest<HTMLElement>("[data-row]")?.dataset.row;
    if (row !== undefined) take(part, Number(row));
  };

  return <div className={styles.wheel} role="group" aria-label={label} data-no-swipe>
    {order.map((part) => <Fragment key={part}>
      {part === "minute" && <span className={styles.wheelColon} aria-hidden="true">:</span>}
      <div ref={(node) => { nodes.current[part] = node; }} className={styles.wheelCol} data-part={part} tabIndex={0} role="spinbutton" aria-label={names[part]}
        aria-valuenow={part === "half" ? at.half : part === "hour" ? at.hour || 12 : at.minute * SNAP} aria-valuetext={labels[part][at[part]]}
        onScroll={() => scrolled(part)} onKeyDown={onKey(part)} onPointerDown={onDown(part)} onPointerMove={onMove} onPointerUp={onUp} onPointerCancel={onUp} onClick={onTap(part)}
        onTouchStart={() => { delete target.current[part]; }} onWheel={() => { delete target.current[part]; }}>
        <span className={styles.wheelPad} aria-hidden="true" />
        {Array.from({ length: rowsOf(part) }, (_, row) => {
          const index = indexOf(part, row);
          return <i key={row} data-row={row} data-on={index === at[part] || undefined} data-off={!allowed(part, index) || undefined} aria-hidden="true">{labels[part][index]}</i>;
        })}
        <span className={styles.wheelPad} aria-hidden="true" />
      </div>
    </Fragment>)}
  </div>;
}
