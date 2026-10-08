"use client";

import { useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { dayTimes, type DayTimes } from "./day-times";
import type { PlanCheckView, PlanItem } from "./model";
import { ASSUMED_MINUTES, endRanges, formatHm, holdAtLimit, moveEnd, moveStop, ownRange, parseHm, pushRange, SNAP, type Held, type Retime, type TimeRange } from "./time-plan";

type List = "before" | "after";
/** What is being changed: the START of a stop (its time at the left of the card) or the time of LEAVING it for the next place (its end, shown at the left of the leg). */
export type TimeKind = "start" | "depart";

/** What the customer has typed or dragged so far for one stop: the texts in its two fields, whether the neighbours may be pushed. */
export interface TimeEdit {
  id: string; list: List; kind: TimeKind; start: string; end: string; push: boolean;
  /** The customer typed the end himself: from then on it stays as typed (until then it moves with the start, so the stop keeps its length). Always true when the end is what is changed. */
  endTouched: boolean;
  /** The stop as it was when the editor opened - what the end is carried along from. */
  first: { start: number | null; end: number | null };
  /** `[2026-10-05]` Dragged straight from the time (or its dot) with no form open: the form stays shut while the time is held, and opens only when what was dragged cannot be sent. */
  direct?: boolean;
}

/** What the maths says about that: the stops that would change (the stop itself first in day order), what is allowed, and why not when it is not. */
export interface TimePreview {
  changes: Retime[];
  /** The times this stop can have with the neighbours pushed or not, as the switch stands. */
  range: TimeRange;
  /** Other stops that move along: name and minutes (negative = earlier), for the line under the fields. */
  along: { title: string; minutes: number }[];
  problem: string;
  /** The stop's day as the maths sees it (for the strip shown while dragging). */
  day: DayTimes | null;
  title: string;
}

/** What the overlay shows while a time is dragged. */
export interface TimeDrag { id: string; kind: TimeKind; title: string; from: number | null; to: number | null; held: Held; day: DayTimes; changes: Retime[] }

/** 1 px of dragging is half a minute (10 px = 5 minutes): fine enough to place a time, coarse enough to stay in step with a thumb. */
export const DRAG_MINUTES_PER_PX = 0.5;
/** A drag that comes this close to where the stop was, or to the end of its range, sticks there. */
const MAGNET = 2;
/** The wording [Korean, English] when a drag (or a step) is held at the end of the free time. */
export const heldTexts = (kind: TimeKind, held: Exclude<Held, null>): readonly [string, string] => held === "max"
  ? (kind === "depart"
    ? ["여유를 다 썼어요 · 더 늦추면 다음 일정이 밀려요", "The free time is used up · going on pushes the next stops"]
    : ["여유를 다 썼어요 · 더 늦추면 뒤 일정이 밀려요", "The free time is used up · going on pushes the stops behind"])
  : ["앞 일정과 붙었어요 · 더 당기면 앞 일정이 당겨져요", "Touching the stop before · going on pulls it earlier"];

/** The wording of the overlay while the drag has gone past that end and the other stops are being pushed (`delta` > 0 later, < 0 earlier) - it stays up as long as they move. */
export const pushingTexts = (kind: TimeKind, delta: number): readonly [string, string] => delta < 0
  ? ["앞 일정과 붙었어요 · 앞 일정이 당겨지고 있어요", "Touching the stop before · it is being pulled earlier"]
  : kind === "depart"
    ? ["여유를 다 썼어요 · 다음 일정이 밀리고 있어요", "The free time is used up · the next stops are being pushed"]
    : ["여유를 다 썼어요 · 뒤 일정이 밀리고 있어요", "The free time is used up · the stops behind are being pushed"];

/** The pointer handlers of something a time is dragged by (the grip in the form, the time itself, its dot). */
export interface Grab { onPointerDown: (event: PointerEvent<HTMLElement>) => void; onPointerMove: (event: PointerEvent<HTMLElement>) => void; onPointerUp: (event: PointerEvent<HTMLElement>) => void; onPointerCancel: (event: PointerEvent<HTMLElement>) => void }
/** A press that moves this far (px) up or down is a drag; one that does not is a tap (it opens the form). */
const LIFT_PX = 6;

export interface TimeEditHandles {
  edit: TimeEdit | null;
  preview: TimePreview | null;
  busy: boolean;
  /** The grip is being dragged (the screen shows the strip of the day), and what that would do. */
  drag: TimeDrag | null;
  open: (item: PlanItem, list: List, kind?: TimeKind) => void;
  close: () => void;
  setStart: (text: string) => void;
  setEnd: (text: string) => void;
  setPush: (push: boolean) => void;
  /** Move the time being changed by `minutes` (kept inside the range; the end of the free time stops a step once and says so). */
  step: (minutes: number) => void;
  /** Send what is previewed (the screen decides how: it may have to save the proposed plan first). */
  apply: () => Promise<void>;
  /** Handlers for the grip: drag up and down, or arrow keys for 5 minutes (Shift 30). A release applies. */
  grip: Grab & { onKeyDown: (event: KeyboardEvent<HTMLElement>) => void };
  /**
   * `[2026-10-05 사용자 선택 — 시간 조정 합친 안]` The time of a stop (or of leaving it) and its dot can be taken and dragged AT ONCE, no tap first: up = earlier, down = later, the same rules as the grip.
   * A press that does not move is a tap and opens the form as before (`dragEnded` says the click that ends a drag is not one of those).
   */
  handle: (item: PlanItem, list: List, kind?: TimeKind) => Grab;
  dragEnded: () => boolean;
}

/**
 * `[2026-10-04 사용자 지시]` Changing the time of a stop in place: the time pressed opens an editor with the start and end fields, a grip to drag the start up and down,
 * 「−5분 / +5분」, and a switch for pushing the stops around it. Everything shown while it is open is a preview worked out from the plan as it is (`time-plan.ts`),
 * nothing is sent until `apply`. `views` are the two pictures of the plan (the plan as it is, and the proposed one under it); `commit` is how the screen sends a batch.
 *
 * ★`[2026-10-05 사용자 지시]` Free time first: a time moved later (or earlier) uses up the free minutes before anybody else moves. When they are gone the drag stops there for a few more
 *   minutes of dragging (`holdAtLimit`) and `onNotice` says so once; only a drag that goes on pushes the next stops one after the other. The same for the time of LEAVING (`kind: "depart"` -
 *   the stop's end): leaving later eats the free time, then pushes the next stops. While the grip is dragged `drag` carries what the strip of the day needs.
 */
export function useTimeEdit({ views, commit, onNotice }: {
  views: Record<List, PlanCheckView | null>;
  commit: (list: List, changes: Retime[]) => Promise<void>;
  onNotice?: (kind: TimeKind, held: Exclude<Held, null>) => void;
}): TimeEditHandles {
  const [edit, setEdit] = useState<TimeEdit | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [dragging, setDragging] = useState(false);
  const [held, setHeld] = useState<Held>(null);
  const grabbed = useRef<{ y: number; origin: number } | null>(null);
  const heldBefore = useRef<Held>(null);
  const saidAt = useRef(0);

  /** The stop being changed, its day and its place in it. */
  const subject = useMemo(() => {
    const view = edit ? views[edit.list] : null;
    const item = view?.items.find((entry) => entry.id === edit?.id);
    if (!edit || !view || !item) return null;
    const times = dayTimes(view, item.day);
    const index = times.indexOf.get(item.id);
    return { view, item, times, index };
  }, [edit?.id, edit?.list, views]); // eslint-disable-line react-hooks/exhaustive-deps -- the editor's texts do not change who the subject is

  /** The two ranges the time can move in: `own` moves nobody, `reach` may push (for the start of a stop, or for its end). */
  const limits = useMemo<{ own: TimeRange; reach: TimeRange } | null>(() => {
    if (!edit || !subject || subject.index === undefined) return null;
    const { times, index } = subject;
    return edit.kind === "depart"
      ? endRanges(times.stops, times.legs, index, 1)
      : { own: ownRange(times.stops, times.legs, index, 1), reach: pushRange(times.stops, times.legs, index, 1) };
  }, [edit?.kind, subject]); // eslint-disable-line react-hooks/exhaustive-deps

  const preview = useMemo<TimePreview | null>(() => {
    if (!edit || !subject) return null;
    const { view, item, times, index } = subject;
    if (index === undefined || !limits) return { changes: [], range: { min: 0, max: 0 }, along: [], problem: "이 일정은 시작 시각이 없어서 시간을 고칠 수 없어요.", day: null, title: item.title };
    const range = edit.push ? limits.reach : limits.own;
    const none = (problem: string): TimePreview => ({ changes: [], range, along: [], problem, day: times, title: item.title });
    const wording = (min: number, max: number, what: string) => `${min === max ? `지금 ${what}(${formatHm(min)})에서 움직일 수 없어요` : `가능한 시각은 ${formatHm(min)} ~ ${formatHm(max)}이에요`}${edit.push ? "" : " · 앞뒤 일정도 함께 밀면 더 넓어져요"}.`;
    const alongOf = (changes: Retime[]) => changes.filter((change) => change.id !== item.id).map((change) => ({
      title: view.items.find((entry) => entry.id === change.id)?.title ?? change.id,
      minutes: change.start - (times.stops[times.indexOf.get(change.id) ?? 0]?.start ?? change.start),
    }));
    if (edit.kind === "depart") {
      const leaving = parseHm(edit.end);
      if (leaving === null) return none("출발 시각을 시:분으로 적어 주세요.");
      if (leaving < range.min || leaving > range.max) return none(wording(range.min, range.max, "시각"));
      const moved = moveEnd(times.stops, times.legs, index, leaving, { push: edit.push, step: 1 });
      return { changes: moved.changes, range, along: alongOf(moved.changes), problem: "", day: times, title: item.title };
    }
    const start = parseHm(edit.start);
    const end = edit.end.trim() ? parseHm(edit.end) : null;
    if (start === null) return none("시작 시각을 적어 주세요.");
    if (edit.end.trim() && end === null) return none("끝 시각을 시:분으로 적어 주세요.");
    if (edit.endTouched && end !== null && end <= start) return none("끝 시각이 시작보다 빨라요.");
    if (start < range.min || start > range.max) return none(wording(range.min, range.max, "시각"));
    const moved = moveStop(times.stops, times.legs, index, start, { push: edit.push, step: 1 });
    const stop = times.stops[index];
    // The end the customer typed wins over the shifted end; an end left alone keeps the stop's length.
    const typedEnd = edit.end.trim() ? end : null;
    const endChanged = edit.endTouched;
    const changes = moved.changes.map((change) => change.id === item.id ? { ...change, end: endChanged ? typedEnd : change.end } : change);
    if (!changes.some((change) => change.id === item.id) && endChanged) changes.push({ id: item.id, start: stop.start, end: typedEnd });
    changes.sort((a, b) => times.stops.findIndex((s) => s.id === a.id) - times.stops.findIndex((s) => s.id === b.id));
    return { changes, range, along: alongOf(changes), problem: "", day: times, title: item.title };
  }, [edit, subject, limits]);

  /** What the editor starts as for a stop: its start, or - for the time of leaving - its end. A stop with no end leaves after the length the maths assumes for it. */
  const build = (item: PlanItem, list: List, kind: TimeKind, direct = false): TimeEdit => {
    const start = parseHm(item.startsAt);
    const end = parseHm(item.endsAt);
    const leaves = start === null ? null : end !== null && end > start ? end : start + ASSUMED_MINUTES;
    return kind === "depart"
      ? { id: item.id, list, kind, start: item.startsAt, end: leaves === null ? "" : formatHm(leaves), push: true, endTouched: true, first: { start, end: leaves }, direct }
      : { id: item.id, list, kind, start: item.startsAt, end: item.endsAt, push: true, endTouched: false, first: { start, end }, direct };
  };
  const open = (item: PlanItem, list: List, kind: TimeKind = "start") => {
    setFailure("");
    setEdit((current) => current?.id === item.id && current.list === list && current.kind === kind ? null : build(item, list, kind));
  };
  /** What was dragged cannot be sent as it stands: the form opens, to say why and to be fixed by hand. */
  const showForm = () => setEdit((current) => current?.direct ? { ...current, direct: false } : current);
  const close = () => { grabbed.current = null; heldBefore.current = null; setDragging(false); setHeld(null); setFailure(""); setEdit(null); };
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
  /** The time this editor changes with the grip, the arrows and the steps: the start of the stop, or - when leaving is what is changed - its end. */
  const setValue = (text: string) => { if (edit?.kind === "depart") patch({ end: text, endTouched: true }); else moveStart(text); };
  const valueMinutes = () => parseHm(edit?.kind === "depart" ? edit.end : edit?.start ?? "");

  async function apply() {
    if (!edit || !preview) return;
    if (preview.problem) { showForm(); return; }
    if (!preview.changes.length) { close(); return; }
    setBusy(true);
    try { await commit(edit.list, preview.changes); close(); }
    catch (error) { setFailure(error instanceof Error ? error.message : String(error)); showForm(); }
    finally { setBusy(false); }
  }

  /** Say that the free time is used up - once, and not again while the first notice is still on the screen. */
  const say = (kind: TimeKind, now: Exclude<Held, null>) => {
    const at = Date.now();
    if (at - saidAt.current < 3500) return;
    saidAt.current = at;
    onNotice?.(kind, now);
  };

  const rangeNow = () => limits && edit ? (edit.push ? limits.reach : limits.own) : null;
  const step = (minutes: number) => {
    const now = valueMinutes();
    const range = rangeNow();
    if (now === null || !range || !limits || !edit) return;
    let next = now + minutes;
    // Going out of the free time stops at its end once and says so; the next step goes on into the pushing.
    if (edit.push && minutes > 0 && now < limits.own.max && next > limits.own.max && limits.reach.max > limits.own.max) { next = limits.own.max; say(edit.kind, "max"); }
    else if (edit.push && minutes < 0 && now > limits.own.min && next < limits.own.min && limits.reach.min < limits.own.min) { next = limits.own.min; say(edit.kind, "min"); }
    setValue(formatHm(Math.min(range.max, Math.max(range.min, next))));
  };

  /** Where a drag of `dy` px leaves the time: 5-minute steps from where it began, held at the end of the free time, sticking to where it began and to the ends of the range. */
  const draggedTo = (origin: number, dy: number): { value: number; held: Held } => {
    const range = rangeNow();
    let wanted = origin + Math.round((dy * DRAG_MINUTES_PER_PX) / SNAP) * SNAP;
    if (!range || !limits || !edit) return { value: wanted, held: null };
    let now: Held = null;
    if (edit.push) { const result = holdAtLimit(wanted, limits.own, limits.reach); wanted = result.value; now = result.held; }
    wanted = Math.min(range.max, Math.max(range.min, wanted));
    if (!now) for (const stick of [origin, range.min, range.max]) if (Math.abs(wanted - stick) <= MAGNET) wanted = stick;
    return { value: wanted, held: now };
  };
  const grip: TimeEditHandles["grip"] = {
    onPointerDown: (event) => {
      if (!edit || busy) return;
      const origin = valueMinutes();
      if (origin === null) return;
      event.preventDefault();
      event.currentTarget.setPointerCapture(event.pointerId);
      grabbed.current = { y: event.clientY, origin };
      heldBefore.current = null;
      setDragging(true);
    },
    onPointerMove: (event) => {
      const taken = grabbed.current;
      if (!taken) return;
      const { value, held: now } = draggedTo(taken.origin, event.clientY - taken.y);
      // ★`[2026-10-07 사용자 지시]` No notice while dragging: the overlay of the day says it (and keeps saying it while the next stops are pushed) - the notice stood right over that overlay and hid it.
      heldBefore.current = now;
      setHeld(now);
      setValue(formatHm(value));
    },
    onPointerUp: (event) => {
      const taken = grabbed.current;
      grabbed.current = null;
      heldBefore.current = null;
      setDragging(false);
      setHeld(null);
      if (!taken) return;
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
      if (Math.abs(event.clientY - taken.y) >= 3) void apply();          // a press with no move is not a drag
    },
    onPointerCancel: (event) => {
      const taken = grabbed.current;
      grabbed.current = null;
      heldBefore.current = null;
      setDragging(false);
      setHeld(null);
      if (taken) setValue(formatHm(taken.origin));                        // let go without applying: back to where it was
      if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    },
    onKeyDown: (event) => {
      if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
      event.preventDefault();
      step((event.key === "ArrowUp" ? -1 : 1) * (event.shiftKey ? 30 : SNAP));
    },
  };

  // ★`[2026-10-05]` Taking the time (or its dot) and dragging with no tap first. The edit opens (shut form: `direct`) when the press has moved `LIFT_PX`; from then on it is the grip's own drag.
  const lift = useRef<{ id: string; kind: TimeKind; list: List; y: number; origin: number; moved: boolean } | null>(null);
  const swallow = useRef(false);
  const handle = (item: PlanItem, list: List, kind: TimeKind = "start"): Grab => ({
    onPointerDown: (event) => {
      swallow.current = false;
      if (busy || (event.pointerType === "mouse" && event.button !== 0)) return;
      const already = edit?.id === item.id && edit.list === list && edit.kind === kind;
      const origin = already ? valueMinutes() : parseHm(kind === "depart" ? build(item, list, kind).end : item.startsAt);
      if (origin === null) return;
      lift.current = { id: item.id, kind, list, y: event.clientY, origin, moved: false };
      event.currentTarget.setPointerCapture(event.pointerId);
    },
    onPointerMove: (event) => {
      const taken = lift.current;
      if (!taken) return;
      if (!taken.moved) {
        if (Math.abs(event.clientY - taken.y) < LIFT_PX) return;
        taken.moved = true;
        swallow.current = true;                                              // the click that follows this drag is not a tap
        if (!(edit?.id === item.id && edit.list === list && edit.kind === kind)) { setFailure(""); setEdit(build(item, list, kind, true)); }
        grabbed.current = { y: taken.y, origin: taken.origin };
        heldBefore.current = null;
        setDragging(true);
        return;
      }
      grip.onPointerMove(event);
    },
    onPointerUp: (event) => {
      const taken = lift.current;
      lift.current = null;
      if (!taken?.moved) { if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId); return; }
      grip.onPointerUp(event);
    },
    onPointerCancel: (event) => {
      const taken = lift.current;
      lift.current = null;
      if (!taken?.moved) return;
      grip.onPointerCancel(event);
      close();
    },
  });
  const dragEnded = () => { const was = swallow.current; swallow.current = false; return was; };

  const shown = preview && failure ? { ...preview, problem: failure } : preview;
  const drag: TimeDrag | null = dragging && edit && shown && shown.day && !shown.problem
    ? { id: edit.id, kind: edit.kind, title: shown.title, from: edit.kind === "depart" ? edit.first.end : edit.first.start, to: valueMinutes(), held, day: shown.day, changes: shown.changes }
    : null;
  return { edit, preview: shown, busy, drag, open, close, setStart: moveStart, setEnd: (end) => patch({ end, endTouched: true }), setPush: (push) => patch({ push }), step, apply, grip, handle, dragEnded };
}
