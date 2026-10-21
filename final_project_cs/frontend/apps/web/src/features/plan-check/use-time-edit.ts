"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type MouseEvent, type PointerEvent } from "react";
import { dayTimes, type DayTimes } from "./day-times";
import type { PlanCheckView, PlanItem } from "./model";
import { RAIL_PX_PER_MIN } from "./time-rail";
import { ASSUMED_MINUTES, endRanges, formatHm, holdAtLimit, moveEnd, moveStop, ownRange, parseHm, pushRange, PUSH_DAY_START, SNAP, type Held, type Retime, type TimeRange } from "./time-plan";

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

/** The handlers of something a time is dragged by (the time itself, its dot). `ref` lets a finger that has taken it stop the list from scrolling. */
export interface Grab {
  onPointerDown: (event: PointerEvent<HTMLElement>) => void; onPointerMove: (event: PointerEvent<HTMLElement>) => void; onPointerUp: (event: PointerEvent<HTMLElement>) => void; onPointerCancel: (event: PointerEvent<HTMLElement>) => void;
  onContextMenu: (event: MouseEvent<HTMLElement>) => void;
  ref: (element: HTMLElement | null) => (() => void) | undefined;
}
/** A press that moves this far (px) up or down is a drag; one that does not is a tap (it opens the form). */
const LIFT_PX = 6;
/**
 * ★`[2026-10-21 사용자 결정 — ST4F-702 꾹 눌러 잡기]` A FINGER takes the time (or its dot) only after holding it this long: a finger that passes over it while scrolling the list no longer moves
 * the time (it did at `LIFT_PX`). The mouse still takes it at once.
 */
export const HOLD_MS = 450;
/** A finger that moves this far (px) before the hold is up is scrolling (or swiping the day): the hold is let go and the browser goes on with it. */
const HOLD_SLOP = 8;
/** A held time this close (px) to the top or the bottom of the list scrolls the list along, so the drag can go on past the edge - once the finger has gone `EDGE_ARM_PX` that way since it took the time
 *  (`[2026-10-21 사용자 확인]` a dot taken near the bottom ran off from under the finger at once: the list scrolled as soon as it was taken). */
const EDGE_PX = 48;
const EDGE_ARM_PX = 16;

/** A finger on the time of a stop (or of leaving it): holding (not taken yet) or `held` (taken - it moves the time). */
export interface TimePress { id: string; list: List; kind: TimeKind; held: boolean }

export interface TimeEditHandles {
  edit: TimeEdit | null;
  preview: TimePreview | null;
  busy: boolean;
  /** The time is being dragged (the screen shows the strip of the day), and what that would do. */
  drag: TimeDrag | null;
  press: TimePress | null;
  open: (item: PlanItem, list: List, kind?: TimeKind) => void;
  close: () => void;
  setStart: (text: string) => void;
  setEnd: (text: string) => void;
  setPush: (push: boolean) => void;
  /** Send what is previewed (the screen decides how: it may have to save the proposed plan first). */
  apply: () => Promise<void>;
  /**
   * `[2026-10-05 사용자 선택 — 시간 조정 합친 안]` The time of a stop (or of leaving it) and its dot can be taken and dragged with no form open: up = earlier, down = later.
   * A press that does not move is a tap and opens the form as before (`dragEnded` says the click that ends a drag is not one of those). `[2026-10-21]` A finger holds first (`HOLD_MS`).
   */
  handle: (item: PlanItem, list: List, kind?: TimeKind) => Grab;
  dragEnded: () => boolean;
}

/** The list a held time scrolls: the nearest box around it that scrolls up and down. */
function scrollerOf(element: HTMLElement): HTMLElement | null {
  for (let box = element.parentElement; box; box = box.parentElement) {
    const { overflowY } = getComputedStyle(box);
    if ((overflowY === "auto" || overflowY === "scroll") && box.scrollHeight > box.clientHeight) return box;
  }
  return null;
}
/** A short buzz where the phone can (Android; Safari has none - the dot and the bubble are the signal there). */
function buzz(ms: number) {
  if (typeof navigator === "undefined" || !("vibrate" in navigator) || navigator.userActivation?.hasBeenActive === false) return;
  try { navigator.vibrate(ms); } catch { /* a phone that says no: the screen says it anyway */ }
}

/**
 * `[2026-10-04 사용자 지시]` Changing the time of a stop in place: the time pressed opens an editor with the start and end (`[2026-10-21 ST4F-702]` picked on a wheel, or typed),
 * and a switch for pushing the stops around it. Everything shown while it is open is a preview worked out from the plan as it is (`time-plan.ts`),
 * nothing is sent until `apply`. `views` are the two pictures of the plan (the plan as it is, and the proposed one under it); `commit` is how the screen sends a batch.
 *
 * ★`[2026-10-05 사용자 지시]` Free time first: a time moved later (or earlier) uses up the free minutes before anybody else moves. When they are gone the drag stops there for a few more
 *   minutes of dragging (`holdAtLimit`); only a drag that goes on pushes the next stops one after the other. The same for the time of LEAVING (`kind: "depart"` -
 *   the stop's end): leaving later eats the free time, then pushes the next stops. While a time is dragged `drag` carries what the strip of the day needs.
 */
export function useTimeEdit({ views, commit }: {
  views: Record<List, PlanCheckView | null>;
  commit: (list: List, changes: Retime[]) => Promise<void>;
}): TimeEditHandles {
  const [edit, setEdit] = useState<TimeEdit | null>(null);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  const [dragging, setDragging] = useState(false);
  const [held, setHeld] = useState<Held>(null);
  const [press, setPress] = useState<TimePress | null>(null);
  /** The drag going on: where it was taken, minutes per px, and - for a finger - the list it scrolls along (`along`: how far it has scrolled it) and the last time it buzzed for. */
  const grabbed = useRef<{ y: number; origin: number; perPx: number; scroller: HTMLElement | null; along: number; touch: boolean; last: number } | null>(null);
  const heldBefore = useRef<Held>(null);
  /** A finger has taken a time: its moves drag the time, not the list. */
  const holding = useRef(false);
  const edge = useRef<number | null>(null);

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
      : { own: ownRange(times.stops, times.legs, index, 1), reach: pushRange(times.stops, times.legs, index, 1, PUSH_DAY_START) };
  }, [edit?.kind, subject]); // eslint-disable-line react-hooks/exhaustive-deps

  const preview = useMemo<TimePreview | null>(() => {
    if (!edit || !subject) return null;
    const { view, item, times, index } = subject;
    if (index === undefined || !limits) return { changes: [], range: { min: 0, max: 0 }, along: [], problem: "이 일정은 시작 시각이 없어서 시간을 고칠 수 없어요.", day: null, title: item.title };
    const range = edit.push ? limits.reach : limits.own;
    const none = (problem: string): TimePreview => ({ changes: [], range, along: [], problem, day: times, title: item.title });
    if (item.locked || item.booked === true) return none("고정·예약 일정의 시간은 바꿀 수 없어요.");
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
  const close = () => { letGo(); grabbed.current = null; heldBefore.current = null; setDragging(false); setHeld(null); setFailure(""); setEdit(null); };
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

  const rangeNow = () => limits && edit ? (edit.push ? limits.reach : limits.own) : null;

  /** Where a drag of `dy` px leaves the time: 5-minute steps from where it began, held at the end of the free time, sticking to where it began and to the ends of the range. */
  const draggedTo = (origin: number, dy: number, perPx = DRAG_MINUTES_PER_PX): { value: number; held: Held } => {
    const range = rangeNow();
    let wanted = origin + Math.round((dy * perPx) / SNAP) * SNAP;
    if (!range || !limits || !edit) return { value: wanted, held: null };
    let now: Held = null;
    if (edit.push) { const result = holdAtLimit(wanted, limits.own, limits.reach); wanted = result.value; now = result.held; }
    wanted = Math.min(range.max, Math.max(range.min, wanted));
    if (!now) for (const stick of [origin, range.min, range.max]) if (Math.abs(wanted - stick) <= MAGNET) wanted = stick;
    return { value: wanted, held: now };
  };
  /** The drag goes on to `clientY` - and, for a held finger, as far again as the list scrolled under it. */
  const dragTo = (clientY: number) => {
    const taken = grabbed.current;
    if (!taken) return;
    const { value, held: now } = draggedTo(taken.origin, clientY - taken.y + taken.along, taken.perPx);
    // ★`[2026-10-07 사용자 지시]` No notice while dragging: the overlay of the day says it (and keeps saying it while the next stops are pushed) - the notice stood right over that overlay and hid it.
    heldBefore.current = now;
    setHeld(now);
    if (taken.touch && value !== taken.last) buzz(4);
    taken.last = value;
    setValue(formatHm(value));
  };
  const dragAt = useRef(dragTo);
  useLayoutEffect(() => { dragAt.current = dragTo; });
  /** The drag ends: no more holding, the list no longer scrolls along. */
  function letGo() {
    const taken = lift.current;
    if (taken?.timer) window.clearTimeout(taken.timer);
    holding.current = false;
    if (edge.current !== null) cancelAnimationFrame(edge.current);
    edge.current = null;
    setPress(null);
  }
  /** A held finger near the top or the bottom of the list: the list scrolls along, and the time with it. */
  const scrollAlong = () => {
    const taken = grabbed.current, finger = lift.current;
    if (!taken?.scroller || !finger || !holding.current) { edge.current = null; return; }
    const box = taken.scroller.getBoundingClientRect();
    const y = finger.lastY, went = y - taken.y;
    const speed = went < -EDGE_ARM_PX && y < box.top + EDGE_PX ? -Math.min(9, (box.top + EDGE_PX - y) / 6)
      : went > EDGE_ARM_PX && y > box.bottom - EDGE_PX ? Math.min(9, (y - (box.bottom - EDGE_PX)) / 6) : 0;
    if (speed) {
      const was = taken.scroller.scrollTop;
      taken.scroller.scrollTop += speed;
      // Only what this loop scrolled counts as dragging: the list may move for other reasons too (it is laid out again as the times change).
      const moved = taken.scroller.scrollTop - was;
      if (moved) { taken.along += moved; dragAt.current(y); }
    }
    edge.current = requestAnimationFrame(scrollAlong);
  };

  // ★`[2026-10-05]` Taking the time (or its dot) and dragging with no tap first. The edit opens (shut form: `direct`) when a mouse has moved `LIFT_PX`, or a finger has held it `HOLD_MS`.
  const lift = useRef<{ x: number; y: number; lastY: number; origin: number; moved: boolean; touch: boolean; timer: number | null } | null>(null);
  const swallow = useRef(false);
  /** A finger that has taken a time keeps the list still: React's own touch listeners cannot stop the scrolling, this one can (it is only listened to on the times and their dots). */
  const keepStill = useCallback((element: HTMLElement | null) => {
    if (!element) return undefined;
    const stop = (event: TouchEvent) => { if (holding.current && event.cancelable) event.preventDefault(); };
    element.addEventListener("touchmove", stop, { passive: false });
    return () => element.removeEventListener("touchmove", stop);
  }, []);
  useEffect(() => () => {
    if (lift.current?.timer) window.clearTimeout(lift.current.timer);
    if (edge.current !== null) cancelAnimationFrame(edge.current);
  }, []);
  const handle = (item: PlanItem, list: List, kind: TimeKind = "start"): Grab => {
    const already = edit?.id === item.id && edit.list === list && edit.kind === kind;
    /** The drag starts: the edit opens with its form shut, unless it is open on this time already. */
    const take = (taken: NonNullable<typeof lift.current>, scroller: HTMLElement | null, perPx = DRAG_MINUTES_PER_PX) => {
      taken.moved = true;
      swallow.current = true;                                              // the click that follows this drag is not a tap
      if (!already) { setFailure(""); setEdit(build(item, list, kind, true)); }
      grabbed.current = { y: taken.touch ? taken.lastY : taken.y, origin: taken.origin, perPx, scroller, along: 0, touch: taken.touch, last: taken.origin };
      heldBefore.current = null;
      setDragging(true);
    };
    return {
      ref: keepStill,
      onContextMenu: (event) => { if (holding.current || lift.current?.touch) event.preventDefault(); },   // a long press is the time's, not the phone's menu
      onPointerDown: (event) => {
        swallow.current = false;
        if (busy || item.locked || item.booked === true || (event.pointerType === "mouse" && event.button !== 0)) return;
        const origin = already ? valueMinutes() : parseHm(kind === "depart" ? build(item, list, kind).end : item.startsAt);
        if (origin === null) return;
        const element = event.currentTarget;
        const taken = { x: event.clientX, y: event.clientY, lastY: event.clientY, origin, moved: false, touch: event.pointerType !== "mouse", timer: null as number | null };
        lift.current = taken;
        element.setPointerCapture(event.pointerId);
        if (!taken.touch) return;
        // A finger holds first: the dot fills up while it does (`press`), and once it is full the time is taken.
        setPress({ id: item.id, list, kind, held: false });
        taken.timer = window.setTimeout(() => {
          if (lift.current !== taken) return;
          taken.timer = null;
          holding.current = true;
          // ★`[2026-10-21 사용자 확인]` The held dot stays under the finger: the list is drawn to scale (1 minute = `RAIL_PX_PER_MIN`, times the list's zoom), so a finger moves the time by
          //   that much - at 10 px = 5 minutes the dot fell behind the finger (60 px for every 100). The mouse keeps 10 px = 5 minutes.
          const zoom = (element as HTMLElement & { currentCSSZoom?: number }).currentCSSZoom || 1;
          take(taken, scrollerOf(element), 1 / (RAIL_PX_PER_MIN * zoom));
          setPress({ id: item.id, list, kind, held: true });
          buzz(12);
          edge.current = requestAnimationFrame(scrollAlong);
        }, HOLD_MS);
      },
      onPointerMove: (event) => {
        const taken = lift.current;
        if (!taken) return;
        taken.lastY = event.clientY;
        if (taken.touch && !taken.moved) {
          // Moved on before the hold was up: the finger is scrolling the list (or swiping the day) - let it.
          if (Math.hypot(event.clientX - taken.x, event.clientY - taken.y) <= HOLD_SLOP) return;
          letGo();
          lift.current = null;
          if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
          return;
        }
        if (!taken.moved) {
          if (Math.abs(event.clientY - taken.y) >= LIFT_PX) take(taken, null);
          return;
        }
        dragTo(event.clientY);
      },
      onPointerUp: (event) => {
        const taken = lift.current;
        if (taken?.touch) letGo();
        lift.current = null;
        if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
        if (!taken?.moved || !grabbed.current) return;                     // a tap: its click opens the form
        grabbed.current = null;
        heldBefore.current = null;
        setDragging(false);
        setHeld(null);
        void apply();                                                         // sent at once (a drag that ended where it began changes nothing and closes)
      },
      onPointerCancel: () => {
        const taken = lift.current;
        if (taken?.touch) letGo();
        lift.current = null;
        if (!taken?.moved) return;
        close();                                                              // let go without applying: back to where it was
      },
    };
  };
  const dragEnded = () => { const was = swallow.current; swallow.current = false; return was; };

  const shown = preview && failure ? { ...preview, problem: failure } : preview;
  const drag: TimeDrag | null = dragging && edit && shown && shown.day && !shown.problem
    ? { id: edit.id, kind: edit.kind, title: shown.title, from: edit.kind === "depart" ? edit.first.end : edit.first.start, to: valueMinutes(), held, day: shown.day, changes: shown.changes }
    : null;
  return { edit, preview: shown, busy, drag, press, open, close, setStart: moveStart, setEnd: (end) => patch({ end, endTouched: true }), setPush: (push) => patch({ push }), apply, handle, dragEnded };
}
