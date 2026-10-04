"use client";

import { useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { dayTimes } from "./day-times";
import type { PlanCheckView, PlanItem } from "./model";
import { formatHm, moveStop, ownRange, parseHm, pushRange, SNAP, type Retime, type TimeRange } from "./time-plan";

type List = "before" | "after";

/** What the customer has typed or dragged so far for one stop: the texts in its two fields, whether the neighbours may be pushed. */
export interface TimeEdit {
  id: string; list: List; start: string; end: string; push: boolean;
  /** The customer typed the end himself: from then on it stays as typed (until then it moves with the start, so the stop keeps its length). */
  endTouched: boolean;
  /** The stop as it was when the editor opened - what the end is carried along from. */
  first: { start: number | null; end: number | null };
}

/** What the maths says about that: the stops that would change (the stop itself first in day order), what is allowed, and why not when it is not. */
export interface TimePreview {
  changes: Retime[];
  /** The start times this stop can have with the neighbours pushed or not, as the switch stands. */
  range: TimeRange;
  /** Other stops that move along: name and minutes (negative = earlier), for the line under the fields. */
  along: { title: string; minutes: number }[];
  problem: string;
}

/** 1 px of dragging is half a minute (10 px = 5 minutes): fine enough to place a time, coarse enough to stay in step with a thumb. */
export const DRAG_MINUTES_PER_PX = 0.5;
/** A drag that comes this close to where the stop was, or to the end of its range, sticks there. */
const MAGNET = 2;

export interface TimeEditHandles {
  edit: TimeEdit | null;
  preview: TimePreview | null;
  busy: boolean;
  open: (item: PlanItem, list: List) => void;
  close: () => void;
  setStart: (text: string) => void;
  setEnd: (text: string) => void;
  setPush: (push: boolean) => void;
  /** Move the start by `minutes` (kept inside the range). */
  step: (minutes: number) => void;
  /** Send what is previewed (the screen decides how: it may have to save the proposed plan first). */
  apply: () => Promise<void>;
  /** Handlers for the grip: drag up and down, or arrow keys for 5 minutes (Shift 30). A release applies. */
  grip: { onPointerDown: (event: PointerEvent<HTMLElement>) => void; onPointerMove: (event: PointerEvent<HTMLElement>) => void; onPointerUp: (event: PointerEvent<HTMLElement>) => void; onPointerCancel: (event: PointerEvent<HTMLElement>) => void; onKeyDown: (event: KeyboardEvent<HTMLElement>) => void };
}

/**
 * `[2026-10-04 사용자 지시]` Changing the time of a stop in place: the time pressed opens an editor with the start and end fields, a grip to drag the start up and down,
 * 「−5분 / +5분」, and a switch for pushing the stops around it. Everything shown while it is open is a preview worked out from the plan as it is (`time-plan.ts`),
 * nothing is sent until `apply`. `views` are the two pictures of the plan (the plan as it is, and the proposed one under it); `commit` is how the screen sends a batch.
 */
export function useTimeEdit({ views, commit }: { views: Record<List, PlanCheckView | null>; commit: (list: List, changes: Retime[]) => Promise<void> }): TimeEditHandles {
  const [edit, setEdit] = useState<TimeEdit | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const drag = useRef<{ y: number; origin: number } | null>(null);

  const preview = useMemo<TimePreview | null>(() => {
    const view = edit ? views[edit.list] : null;
    const item = view?.items.find((entry) => entry.id === edit?.id);
    if (!edit || !view || !item) return null;
    const times = dayTimes(view, item.day);
    const index = times.indexOf.get(item.id);
    if (index === undefined) return { changes: [], range: { min: 0, max: 0 }, along: [], problem: "이 일정은 시작 시각이 없어서 시간을 고칠 수 없어요." };
    const range = edit.push ? pushRange(times.stops, times.legs, index, 1) : ownRange(times.stops, times.legs, index, 1);
    const start = parseHm(edit.start);
    const end = edit.end.trim() ? parseHm(edit.end) : null;
    const none = (problem: string): TimePreview => ({ changes: [], range, along: [], problem });
    if (start === null) return none("시작 시각을 적어 주세요.");
    if (edit.end.trim() && end === null) return none("끝 시각을 시:분으로 적어 주세요.");
    if (edit.endTouched && end !== null && end <= start) return none("끝 시각이 시작보다 빨라요.");
    if (start < range.min || start > range.max) {
      const wording = range.min === range.max ? `지금 시각(${formatHm(range.min)})에서 움직일 수 없어요` : `가능한 시각은 ${formatHm(range.min)} ~ ${formatHm(range.max)}이에요`;
      return none(`${wording}${edit.push ? "" : " · 앞뒤 일정도 함께 밀면 더 넓어져요"}.`);
    }
    const moved = moveStop(times.stops, times.legs, index, start, { push: edit.push, step: 1 });
    const stop = times.stops[index];
    // The end the customer typed wins over the shifted end; an end left alone keeps the stop's length.
    const typedEnd = edit.end.trim() ? end : null;
    const endChanged = edit.endTouched;
    const changes = moved.changes.map((change) => change.id === item.id ? { ...change, end: endChanged ? typedEnd : change.end } : change);
    if (!changes.some((change) => change.id === item.id) && endChanged) changes.push({ id: item.id, start: stop.start, end: typedEnd });
    changes.sort((a, b) => times.stops.findIndex((s) => s.id === a.id) - times.stops.findIndex((s) => s.id === b.id));
    const along = changes.filter((change) => change.id !== item.id).map((change) => ({
      title: view.items.find((entry) => entry.id === change.id)?.title ?? change.id,
      minutes: change.start - (times.stops[times.indexOf.get(change.id) ?? 0]?.start ?? change.start),
    }));
    return { changes, range, along, problem: "" };
  }, [edit, views]);

  const open = (item: PlanItem, list: List) => {
    setFailure("");
    setEdit((current) => current?.id === item.id && current.list === list ? null : { id: item.id, list, start: item.startsAt, end: item.endsAt, push: true, endTouched: false, first: { start: parseHm(item.startsAt), end: parseHm(item.endsAt) } });
  };
  const close = () => { drag.current = null; setFailure(""); setEdit(null); };
  const patch = (change: Partial<TimeEdit>) => { setFailure(""); setEdit((current) => current && { ...current, ...change }); };
  /** A new start: the end field follows it by the same distance until the customer types an end of his own. */
  const moveStart = (text: string) => {
    setFailure("");
    setEdit((current) => {
      if (!current) return current;
      const start = parseHm(text);
      const { first } = current;
      if (current.endTouched || start === null || first.start === null || first.end === null) return { ...current, start: text };
      return { ...current, start: text, end: formatHm(first.end + start - first.start) };
    });
  };

  async function apply() {
    if (!edit || !preview) return;
    if (preview.problem) return;
    if (!preview.changes.length) { close(); return; }
    setBusy(true);
    try { await commit(edit.list, preview.changes); close(); }
    catch (error) { setFailure(error instanceof Error ? error.message : String(error)); }
    finally { setBusy(false); }
  }

  const startMinutes = () => parseHm(edit?.start ?? "");
  const step = (minutes: number) => {
    const now = startMinutes();
    const range = preview?.range;
    if (now === null || !range) return;
    moveStart(formatHm(Math.min(range.max, Math.max(range.min, now + minutes))));
  };

  /** Where a drag of `dy` px leaves the start: 5-minute steps from where it began, sticking to where it began and to the ends of the range. */
  const draggedTo = (origin: number, dy: number) => {
    const range = preview?.range;
    let wanted = origin + Math.round((dy * DRAG_MINUTES_PER_PX) / SNAP) * SNAP;
    if (!range) return wanted;
    wanted = Math.min(range.max, Math.max(range.min, wanted));
    for (const stick of [origin, range.min, range.max]) if (Math.abs(wanted - stick) <= MAGNET) wanted = stick;
    return wanted;
  };
  const grip: TimeEditHandles["grip"] = {
    onPointerDown: (event) => {
      if (!edit || busy) return;
      const origin = startMinutes();
      if (origin === null) return;
      event.preventDefault();
      event.currentTarget.setPointerCapture(event.pointerId);
      drag.current = { y: event.clientY, origin };
    },
    onPointerMove: (event) => {
      const held = drag.current;
      if (!held) return;
      moveStart(formatHm(draggedTo(held.origin, event.clientY - held.y)));
    },
    onPointerUp: (event) => {
      const held = drag.current;
      drag.current = null;
      if (!held) return;
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      if (Math.abs(event.clientY - held.y) >= 3) void apply();          // a press with no move is not a drag
    },
    onPointerCancel: (event) => {
      const held = drag.current;
      drag.current = null;
      if (held) moveStart(formatHm(held.origin));                        // let go without applying: back to where it was
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    },
    onKeyDown: (event) => {
      if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
      event.preventDefault();
      step((event.key === "ArrowUp" ? -1 : 1) * (event.shiftKey ? 30 : SNAP));
    },
  };

  const shown = preview && failure ? { ...preview, problem: failure } : preview;
  return { edit, preview: shown, busy, open, close, setStart: moveStart, setEnd: (end) => patch({ end, endTouched: true }), setPush: (push) => patch({ push }), step, apply, grip };
}
