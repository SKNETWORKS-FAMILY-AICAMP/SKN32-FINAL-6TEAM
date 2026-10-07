"use client";

import { Suspense, useEffect, useEffectEvent, useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bell, ChevronsRight, OctagonAlert } from "lucide-react";
import { DeviceFrame } from "@/components/layout/device-frame";
import { JourneyShell } from "@/components/layout/journey-shell";
import { ToastView, useToastState } from "@/components/toast-view";
import { QueryState } from "@/components/ui";
import { TripMap } from "@/features/map";
import type { PinLook } from "@/features/map/model";
import { rideLines, routeNotes, visibleShapes } from "@/features/map/route-lines";
import { hasValidCoordinates } from "@/features/map/map-points";
import { useRouteDetail } from "@/features/map/use-route-detail";
import { useDayGestures } from "@/features/plan-check/use-day-gestures";
import { useTripGuardian } from "@/features/guardian/trip-guardian";
import pc from "@/features/plan-check/plan-check.module.css";
import { LiveError } from "@/lib/live/client";
import { getRouteShapes } from "@/lib/live/route-shapes";
import type { Language, Translate } from "@/lib/i18n";
import { useSettings, useT } from "@/lib/settings";
import { onToast, type BusToast } from "@/lib/toast-bus";
import type { Notice, Proposal } from "@/lib/live/extras";
import { useDocumentTitle } from "@/lib/use-document-title";
import { ChatBar, ChatPane, useTripChat } from "./trip-chat";
import { LegRow, legSummary, StopRow } from "./trip-rows";
import { dayTimeline, tripDays, type TripLeg } from "./trip-timeline";
import { NOTICE_LABEL, noticeWhen, TripAttention, type CenterTab } from "./trip-attention";
import { useSeenNotices } from "./notice-reads";
import { DetailHeader, TripDetail } from "./trip-detail";
import { TitleMenu, TripShare, TripTitle } from "./trip-title";
import { SafetyPanel, shelterMeta } from "./trip-safety";
import { tripKey, useTrip } from "./use-trip";
import { useRouteShapes } from "./use-route-shapes";
import { useTripEvents } from "./use-trip-events";
import { noticesKey, proposalsKey, recoveryKey, useNotices, useProposals } from "./use-trip-extras";
import type { Recovery } from "@/lib/live/recovery";
import type { Trip } from "./model";
import styles from "./trip-screen.module.css";

/** 한국관광공사 이용조건 — 관광정보를 화면에 올리면 출처와 저작권 정책 링크를 같이 준다. */
const TOUR_API_POLICY_URL = "https://api.visitkorea.or.kr/#/useServiceGuide/2";
/** A description has more to read than a one-line notice: it stays this long (the pointer on its button keeps it). */
const READ_MS = 7_000;
/** `[2026-10-07 목업 C안]` A safety alert stays longer (the same 9 s as the recovery's failed-record notice). */
const URGENT_MS = 9_000;
/** How high the sheet stands over the map: half the screen, (nearly) all of it, or a strip — the handle cycles them (the plan check's sheet). */
const SHEETS = ["half", "full", "peek"] as const;
type Sheet = (typeof SHEETS)[number];
const COMPACT_BELOW = 190;
const SHEET_MIN = 104;

/**
 * `[2026-10-07 사용자 결정 — 목업 C안(mockups/tripilot-registered-c-attention.html)]` The registered trip: it stays on the plan check's screen — the map, and the sheet over it with the day chips,
 * the timeline of the registered stops and the ways between them, and the trip's chat beside it (「일정 | 채팅」, swiped to from the last day). The bell opens the trip's notices.
 * Always the phone frame (user decision 2026-10-07, like the plan check).
 */
export function TripScreen({ tripId }: { tripId: string }) {
  const query = useTrip(tripId);
  // ★A failed re-read keeps the plan already on screen (react-query keeps the last data). Only a trip that never loaded shows the error page — the change bell re-reads often.
  // ★`[2026-10-05]` But a trip that is gone (`not_found`) or a session that ended (`session_expired`) is not drawn from the cache: another account's plan must not stay on the screen.
  const gone = query.error instanceof LiveError && ["not_found", "session_expired"].includes(query.error.code);
  if (query.isPending || !query.data || gone) {
    return <JourneyShell view="other" title={["나의 여행", "Your trip"]}><QueryState loading={query.isPending} error={query.error} retry={() => void query.refetch()} /></JourneyShell>;
  }
  // `useTripGuardian` reads the address (`?guardian=on`): wait for it outside the server render.
  return <Suspense fallback={null}><TripView key={query.data.id} trip={query.data} stale={query.isError ? { reload: () => void query.refetch(), fetching: query.isFetching } : null} /></Suspense>;
}

const monthDay = (date: string) => `${date.slice(5, 7)}.${date.slice(8, 10)}`;
const weekday = (date: string, language: Language) =>
  new Intl.DateTimeFormat(language === "ko" ? "ko-KR" : "en-US", { weekday: "short", timeZone: "Asia/Seoul" }).format(new Date(`${date}T12:00:00+09:00`));
const dayLabel = (date: string, language: Language) => `${monthDay(date)} ${weekday(date, language)}`;
const dayName = (index: number, t: Translate) => t(`${index + 1}일차`, `Day ${index + 1}`);

function TripView({ trip, stale }: { trip: Trip; stale: { reload: () => void; fetching: boolean } | null }) {
  const t = useT();
  const { language, skipAnimation } = useSettings();
  const queryClient = useQueryClient();
  useDocumentTitle(`${t("나의 여행", "Your trip")} · triPilot`);
  // The server's "this trip changed" bell keeps the plan, notices and choices current while the trip is open.
  useTripEvents(trip.id);
  const guardian = useTripGuardian(trip.id);
  const notices = useNotices(trip.id);
  const proposals = useProposals(trip.id);
  // `[2026-10-07 목업 C안]` The bell counts the notices this browser has not seen yet (the server keeps no read state — `notice-reads.ts`).
  const seen = useSeenNotices(trip.id);
  const unread = (notices.data ?? []).filter((notice) => !seen.includes(notice.key)).length;
  // `[2026-10-04]` The lines between the stops (never holding the page up); zoomed in, the detailed lines replace them.
  const routeShapes = useRouteShapes(trip.id, trip.version);
  const routeDetail = useRouteDetail(routeShapes.data, ["trip", trip.id, trip.version ?? 0, language], () => getRouteShapes(trip.id, language, { detail: true }));
  const shapes = routeDetail.routes?.shapes ?? [];

  const days = tripDays(trip);
  const [day, setDay] = useState(days[0] ?? "");
  const [all, setAll] = useState(false);
  const mapDay = days.includes(day) ? day : days[0] ?? "";
  const dayAt = days.indexOf(mapDay);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedLine, setSelectedLine] = useState<string | null>(null);
  // One thing open in the list at a time: a stop's card or a leg.
  const [openId, setOpenId] = useState<string | null>(null);
  const [pane, setPane] = useState<"plan" | "chat">("plan");
  const [instant, setInstant] = useState(false);
  const [barOpen, setBarOpen] = useState(false);
  const [centerOpen, setCenterOpen] = useState(false);
  const [centerTab, setCenterTab] = useState<CenterTab>("warnings");
  // `[2026-10-07 목업 C안 3단계]` The title row (opened · being renamed), the share sheet, and the stop whose detail is open.
  const [titleOpen, setTitleOpen] = useState(false);
  const [titleEditing, setTitleEditing] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [slide, setSlide] = useState<"next" | "prev" | null>(null);
  const [peek, setPeek] = useState<{ side: -1 | 0 | 1; top: number; edge: boolean }>({ side: 0, top: 0, edge: false });
  const { shown: shownToast, show: showToast, hide: hideToast } = useToastState();
  // `[2026-10-06]` What happens elsewhere on this screen (the Course Keeper, …) is told in THIS bar, like every other notice here.
  useEffect(() => onToast(showToast), [showToast]);

  const selected = trip.stops.find((stop) => stop.id === selectedId) ?? null;
  const chat = useTripChat(trip, selectedId, () => goPane("chat"));
  const explain = (why: string) => showToast({ text: why });

  // ── The sheet: three heights (the handle cycles them) or a height it was dragged to — the plan check's sheet. ──
  const [sheet, setSheet] = useState<Sheet>("half");
  const [custom, setCustom] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);
  const [compact, setCompact] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const sheetBox = useRef<HTMLElement>(null);
  const bodyBox = useRef<HTMLDivElement>(null);
  const chatBox = useRef<HTMLDivElement>(null);
  const chatLog = useRef<HTMLDivElement>(null);
  const pagerTrack = useRef<HTMLDivElement>(null);
  const dayTrack = useRef<HTMLDivElement>(null);
  const stripBox = useRef<HTMLDivElement>(null);
  const markerBox = useRef<HTMLSpanElement>(null);
  const grab = useRef<{ y: number; height: number; moved: boolean } | null>(null);
  const justDragged = useRef(false);
  const lastSheetHeight = useRef(0);
  const dragHeight = useRef<number | null>(null);
  const dragFrame = useRef<number | null>(null);
  useEffect(() => {
    const element = sheetBox.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const watcher = new ResizeObserver(() => { lastSheetHeight.current = element.offsetHeight; const next = element.getBoundingClientRect().height < COMPACT_BELOW; setCompact((current) => current === next ? current : next); });
    watcher.observe(element);
    return () => watcher.disconnect();
  }, []);
  // The sheet takes its new height at once and SLIDES there (as the plan check's does).
  useLayoutEffect(() => {
    const element = sheetBox.current;
    if (!element || typeof element.animate !== "function") return;
    const height = element.offsetHeight;
    const before = lastSheetHeight.current;
    lastSheetHeight.current = height;
    if (!before || Math.abs(height - before) < 2 || skipAnimation || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const slideIn = element.animate([{ transform: `translateY(${height - before}px)` }, { transform: "translateY(0)" }], { duration: 380, easing: "cubic-bezier(.22, .8, .3, 1)" });
    return () => slideIn.cancel();
  }, [sheet, custom, skipAnimation]);
  const sheetLimits = () => ({ min: SHEET_MIN, max: Math.max(180, (box.current?.clientHeight ?? 600) - 64) });
  const sheetHeight = () => sheetBox.current?.getBoundingClientRect().height ?? 0;
  function grabSheet(event: PointerEvent<HTMLElement>) {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    const control = (event.target as HTMLElement).closest("button, a, input, select, textarea");
    if (control && control !== event.currentTarget) return;
    justDragged.current = false;
    grab.current = { y: event.clientY, height: sheetHeight(), moved: false };
    event.currentTarget.setPointerCapture(event.pointerId);
  }
  function dragSheet(event: PointerEvent<HTMLElement>) {
    const held = grab.current;
    if (!held) return;
    const up = held.y - event.clientY;
    if (!held.moved && Math.abs(up) < 6) return;
    held.moved = true;
    if (!dragging) setDragging(true);
    const { min, max } = sheetLimits();
    const height = Math.round(Math.min(max, Math.max(min, held.height + up)));
    dragHeight.current = height;
    lastSheetHeight.current = height;
    if (dragFrame.current === null) dragFrame.current = requestAnimationFrame(() => {
      dragFrame.current = null;
      if (dragHeight.current !== null) box.current?.style.setProperty("--sheet-h", `${dragHeight.current}px`);
    });
  }
  function dropSheet() {
    if (grab.current?.moved) {
      justDragged.current = true;
      if (dragFrame.current !== null) { cancelAnimationFrame(dragFrame.current); dragFrame.current = null; }
      if (dragHeight.current !== null) setCustom(dragHeight.current);
    }
    grab.current = null;
    dragHeight.current = null;
    setDragging(false);
  }
  function cycleSheet() {
    if (justDragged.current) { justDragged.current = false; return; }
    if (custom !== null) { setCustom(null); setSheet("half"); return; }
    setSheet((current) => SHEETS[(SHEETS.indexOf(current) + 1) % SHEETS.length]);
  }
  function nudgeSheet(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return;
    event.preventDefault();
    const { min, max } = sheetLimits();
    setCustom(Math.round(Math.min(max, Math.max(min, (custom ?? sheetHeight()) + (event.key === "ArrowUp" ? 40 : -40)))));
  }
  /** The map is shown again (the sheet was nearly at the top). */
  const lowerSheet = () => { if (sheet === "full" || (custom !== null && custom > (box.current?.clientHeight ?? 800) * 0.7)) { setCustom(null); setSheet("half"); } };

  // ── Days ──
  function goDay(date: string, animate = true) {
    const to = days.indexOf(date);
    setSlide(animate && !all && dayAt >= 0 && to >= 0 && to !== dayAt ? (to > dayAt ? "next" : "prev") : null);
    setAll(false);
    showDay(date);
    bodyBox.current?.scrollTo({ top: 0 });
  }
  function showDay(date: string) {
    setDay(date);
    if (selected && selected.date !== date) setSelectedId(null);
    setSelectedLine(null);
  }
  function chooseAll() { setSlide(null); setAll(true); bodyBox.current?.scrollTo({ top: 0 }); }
  const listDays = all ? days : [mapDay];
  const nextDay = !all && dayAt >= 0 && dayAt < days.length - 1 ? days[dayAt + 1] : null;
  /** Where the marker under the day chips stands: on the chip shown, or part way to its neighbour while the list is dragged. */
  function placeMarker(shift = 0, width = 1) {
    const strip = stripBox.current, marker = markerBox.current;
    if (!strip || !marker) return;
    const tabs = Array.from(strip.querySelectorAll<HTMLElement>('[role="tab"]'));
    const at = all ? 0 : dayAt + 1;
    const here = tabs[at];
    if (!here) return;
    const toward = shift < 0 ? tabs[at + 1] : shift > 0 ? tabs[at - 1] : undefined;
    const part = toward ? Math.min(1, Math.abs(shift) / (width * 0.4)) : 0;
    marker.style.transform = `translateX(${here.offsetLeft + (toward ? (toward.offsetLeft - here.offsetLeft) * part : 0)}px)`;
    marker.style.width = `${here.offsetWidth + (toward ? (toward.offsetWidth - here.offsetWidth) * part : 0)}px`;
    strip.toggleAttribute("data-dragging", shift !== 0);
    tabs.forEach((tab, index) => tab.toggleAttribute("data-lit", index === (toward && part > 0.5 ? at + (shift < 0 ? 1 : -1) : at)));
  }
  useLayoutEffect(() => {
    placeMarker();
    const tab = stripBox.current?.querySelectorAll<HTMLElement>('[role="tab"]')[all ? 0 : dayAt + 1];
    tab?.scrollIntoView?.({ inline: "nearest", block: "nearest" });
  // eslint-disable-next-line react-hooks/exhaustive-deps -- `placeMarker` reads the day shown itself
  }, [all, dayAt, days.length, language]);

  // ── The two panes: the plan, and the chat beside it. A turn made by a swipe lands where the finger left it (no second slide). ──
  function goPane(next: "plan" | "chat", bySwipe = false) {
    if (bySwipe) setInstant(true);
    setPane(next);
    if (next === "chat") setBarOpen(true);
    else if (!chat.draft.trim()) setBarOpen(false);
  }
  useEffect(() => {
    if (!instant) return;
    const frame = requestAnimationFrame(() => setInstant(false));
    return () => cancelAnimationFrame(frame);
  }, [instant]);
  // Swiping the plan: the next or previous day; past the last day (or the overview of every day), the chat.
  const toChat = useRef(false);
  useDayGestures(bodyBox, {
    swipe: pane === "plan" && !centerOpen,
    hasPrev: !all && dayAt > 0,
    hasNext: true,
    track: () => (toChat.current ? pagerTrack.current : dayTrack.current),
    onPeek: (side, top, edge) => {
      toChat.current = side === 1 && (all || dayAt === days.length - 1);
      setPeek(toChat.current ? { side: 0, top: 0, edge: false } : { side, top, edge });
    },
    onProgress: (shift, width) => { if (!toChat.current) placeMarker(shift, width); },
    onTurn: (delta) => {
      if (toChat.current && delta === 1) { goPane("chat", true); return; }
      const next = days[dayAt + delta];
      if (next) goDay(next, false);
    },
    pinch: false, zoom: 1, onPinch: () => undefined, onPinchEnd: () => undefined,
  });
  // Swiping the chat to the right: back to the plan.
  useDayGestures(chatBox, {
    swipe: pane === "chat" && !centerOpen,
    hasPrev: true,
    hasNext: false,
    track: () => pagerTrack.current,
    onPeek: () => undefined,
    onProgress: () => undefined,
    onTurn: (delta) => { if (delta === -1) goPane("plan", true); },
    pinch: false, zoom: 1, onPinch: () => undefined, onPinchEnd: () => undefined,
  });

  // ── Picks on the map and in the list ──
  const mapStops = trip.stops.filter((stop) => stop.date === mapDay);
  const legsOf = (date: string) => dayTimeline(trip, date, shapes).flatMap((entry) => entry.type === "leg" ? [entry.leg] : []);
  const bringUp = (id: string) => requestAnimationFrame(() => bodyBox.current?.querySelector<HTMLElement>(`[data-entry-id="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "nearest", behavior: "smooth" }));
  /** A stop picked on the map or with 「지도에서 보기」: marked, opened in the list and described in the notice bar. Pressed again on the map it is let go. */
  function pick(id: string, from: "map" | "list") {
    const stop = trip.stops.find((entry) => entry.id === id);
    if (!stop) return;
    if (from === "map" && selectedId === id) { setSelectedId(null); setOpenId((current) => current === id ? null : current); hideToast(); return; }
    setSelectedLine(null);
    setSelectedId(id);
    if (stop.date !== mapDay) showDay(stop.date);
    setOpenId(id);
    if (from === "list") lowerSheet();
    else if (sheet === "peek") setSheet("half");
    goPane("plan");
    bringUp(id);
    const order = trip.stops.filter((entry) => entry.date === stop.date).indexOf(stop) + 1;
    showToast({ badge: String(order), text: stop.title, sub: [`${stop.time}${stop.endTime ? `–${stop.endTime}` : ""}`, stop.placeInfo?.address].filter(Boolean).join("\n"),
      action: { label: t("목록에서 보기", "Show in list"), run: () => bringUp(id) }, ms: READ_MS });
  }
  /** A route line pressed on the map: drawn picked, its leg opened in the list, described in the notice bar. Pressed again it is let go. */
  function pickLine(lineId: string) {
    const leg = legsOf(mapDay).find((entry) => entry.shape?.itemId === lineId);
    if (!leg) return;
    if (selectedLine === lineId) { setSelectedLine(null); setOpenId((current) => current === leg.id ? null : current); hideToast(); return; }
    setSelectedLine(lineId);
    setSelectedId(null);
    setOpenId(leg.id);
    if (sheet === "peek") setSheet("half");
    goPane("plan");
    bringUp(leg.id);
    showToast(legToast(leg, t, () => bringUp(leg.id)));
  }

  // ── Safety: the pause stands at the top of the list (the notice center has it too). ──
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: tripKey(trip.id, language) });
    void queryClient.invalidateQueries({ queryKey: proposalsKey(trip.id, language) });
    void queryClient.invalidateQueries({ queryKey: noticesKey(trip.id, language) });
  };
  const resumed = (brief: Recovery | null) => {
    queryClient.setQueryData(recoveryKey(trip.id, language), brief);
    showToast({ text: t("일정을 다시 시작했어요", "The itinerary is running again"), sub: brief ? t("재난 뒤 이어가기에서 어떻게 이어갈지 골라 주세요.", "Choose how to go on under 「Going on after the disaster」.") : undefined });
  };

  // ── The notice center: opened by the bell (unread notices first), by a notice's 「알림 보기」, by 「일정 정지 중」. ──
  function openCenter(tab?: CenterTab) {
    setCenterTab(tab ?? (unread > 0 ? "notices" : centerTab));
    setTitleOpen(false);
    setCenterOpen(true);
  }
  function closeCenter() {
    setCenterOpen(false);
    requestAnimationFrame(() => document.getElementById("trip-bell")?.focus());
  }
  // ── The title: opened, it shows 「여행계획서 열기 · 공유하기」 under it; a press outside folds it. ──
  const tripTitle = trip.title ?? t("나의 여행", "Your trip");
  function closeTitle() { setTitleOpen(false); setTitleEditing(false); }
  /** `finished`: the plan was sent or saved — the title row folds too and the focus goes back to the name. */
  function closeShare(finished?: boolean) {
    setShareOpen(false);
    if (finished) setTitleOpen(false);
    requestAnimationFrame(() => document.getElementById(finished ? "trip-title-button" : "trip-title-share")?.focus({ preventScroll: true }));
  }
  useEffect(() => {
    if (!titleOpen || shareOpen) return;
    const away = (event: Event) => { if (!(event.target instanceof Element && event.target.closest("[data-trip-title]"))) setTitleOpen(false); };
    document.addEventListener("pointerdown", away);
    return () => document.removeEventListener("pointerdown", away);
  }, [titleOpen, shareOpen]);

  // ── 「상세 보기」: the stop's day on the map (the others greyed), its cards in the sheet; ← or Esc goes back to the list with that stop open. ──
  const detailStop = detailId ? trip.stops.find((stop) => stop.id === detailId) ?? null : null;
  function openDetail(id: string) {
    const stop = trip.stops.find((entry) => entry.id === id);
    if (!stop) return;
    hideToast();
    closeTitle();
    setBarOpen(false);
    goPane("plan");
    if (stop.date !== mapDay) showDay(stop.date);
    setSelectedLine(null);
    setSelectedId(id);
    setDetailId(id);
    if (sheet === "peek") setSheet("half");
  }
  function detailTo(id: string) { setDetailId(id); setSelectedId(id); }
  function closeDetail() {
    const id = detailId;
    setDetailId(null);
    if (!id) return;
    setSelectedId(id);
    setOpenId(id);
    bringUp(id);
    requestAnimationFrame(() => document.getElementById(`stop-button-${id}`)?.focus({ preventScroll: true }));
  }

  /** A notice the server sent while the trip is open: one bar, the newest (a new bar replaces the one shown). */
  const announce = useEffectEvent((notice: Notice) => showToast(noticeToast(notice, trip, proposals.data ?? [], t, () => openCenter("notices"))));
  const known = useRef<Set<string> | null>(null);
  useEffect(() => {
    if (!notices.data) return;
    const before = known.current;
    known.current = new Set(notices.data.map((notice) => notice.key));
    if (!before) return;                                                       // what was there when the screen opened is not news
    const fresh = notices.data.filter((notice) => !before.has(notice.key)).sort((a, b) => Date.parse(b.at) - Date.parse(a.at))[0];
    if (fresh) announce(fresh);
  }, [notices.data]);

  // ── Keys: Esc closes what is on top. ──
  function onKey(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    if (centerOpen) { event.preventDefault(); closeCenter(); return; }
    if (detailId) { event.preventDefault(); closeDetail(); return; }
    if (titleOpen) { event.preventDefault(); closeTitle(); requestAnimationFrame(() => document.getElementById("trip-title-button")?.focus()); return; }
    if (pane === "chat") { event.preventDefault(); goPane("plan"); return; }
    if (barOpen) { event.preventDefault(); setBarOpen(false); }
  }

  const drawn = visibleShapes(shapes, mapStops);
  const unlocated = mapStops.filter((stop) => !hasValidCoordinates(stop.coordinates));
  const dayList = (date: string) => {
    const index = days.indexOf(date);
    const stops = trip.stops.filter((stop) => stop.date === date);
    return <section key={date} aria-labelledby={`trip-day-${date}`}>
      <h3 id={`trip-day-${date}`} className={pc.day}><button type="button" className={pc.dayButton} aria-pressed={mapDay === date} onClick={() => showDay(date)}>{dayName(index, t)}<small>{dayLabel(date, language)}</small></button></h3>
      <ol className={pc.timeline}>{dayTimeline(trip, date, shapes).map((entry) => entry.type === "stop"
        ? <StopRow key={entry.stop.id} stop={entry.stop} next={stops[stops.indexOf(entry.stop) + 1]} open={openId === entry.stop.id} selected={selectedId === entry.stop.id}
            onToggle={() => { setSelectedId(entry.stop.id); setSelectedLine(null); setOpenId((current) => current === entry.stop.id ? null : entry.stop.id); }}
            onDetail={() => openDetail(entry.stop.id)} detailWhy={null} explain={explain}
            onShowOnMap={() => pick(entry.stop.id, "list")} onAsk={() => { setSelectedId(entry.stop.id); chat.askAbout(entry.stop); }} askBusy={chat.message.isPending} />
        : <LegRow key={entry.leg.id} leg={entry.leg} open={openId === entry.leg.id}
            onToggle={() => { setOpenId((current) => current === entry.leg.id ? null : entry.leg.id); setSelectedLine((current) => entry.leg.shape && current !== entry.leg.shape.itemId ? entry.leg.shape.itemId : null); setSelectedId(null); }} />)}</ol>
    </section>;
  };
  const near = peek.side === 0 ? undefined : days[dayAt + peek.side];
  const detailLooks: Record<string, PinLook> | undefined = detailStop
    ? Object.fromEntries(mapStops.map((stop, at) => [stop.id, { label: String(at + 1), tone: stop.id === detailStop.id ? "current" : "muted" }]))
    : undefined;
  const plan = pane === "plan";

  return <DeviceFrame floating menuTools={guardian.tool}
    headerExtra={<button type="button" id="trip-bell" className={styles.bell} onClick={() => openCenter()} aria-haspopup="dialog" aria-expanded={centerOpen}
      aria-label={unread > 0 ? t(`알림 센터 열기 · 읽지 않은 알림 ${unread}개`, `Open notices · ${unread} unread`) : t("알림 센터 열기", "Open notices")}>
      <Bell size={20} strokeWidth={2} aria-hidden="true" />{unread > 0 && <span className={styles.badge} aria-hidden="true">{unread > 99 ? "99+" : unread}</span>}</button>}>
    <main id="main-content" tabIndex={-1} className={`${pc.screen} ${styles.screen}`} data-floating onKeyDown={onKey}>
      {detailStop ? <DetailHeader title={detailStop.title} onBack={closeDetail} />
        : <TripTitle title={tripTitle} open={titleOpen} editing={titleEditing} onOpen={() => setTitleOpen(true)} onClose={closeTitle}
          onEdit={() => setTitleEditing(true)} onEditEnd={closeTitle}
          // ★The server cannot rename a registered trip yet: said, and the name stays.
          onSave={() => showToast({ text: t("이름 바꾸기는 준비 중이에요", "Renaming is coming"), sub: t("서버에 아직 등록한 여행의 이름을 바꾸는 기능이 없어 저장하지 않았어요.", "The server cannot rename a registered trip yet, so the name was not saved.") })} />}
      <div ref={box} className={pc.checking} data-sheet={custom !== null ? "custom" : sheet} data-dragging={dragging || undefined} data-compact={compact || undefined}
        style={custom !== null ? { "--sheet-h": `${custom}px` } as CSSProperties : undefined}>
        <div className={pc.map}>
          <TripMap stops={mapStops} dayNumber={dayAt + 1} selectedId={detailId ?? selectedId ?? undefined} variant="fill" topInset={64} bottomInset={24} looks={detailLooks}
            routes={detailStop ? undefined : routeDetail.routes} onZoom={routeDetail.onZoom}
            onSelect={(id) => detailStop ? detailTo(id) : pick(id, "map")} onSelectLine={pickLine} selectedLineId={selectedLine ?? undefined} tripId={trip.id} date={mapDay}
            routesError={routeShapes.isError ? t("경로선을 불러오지 못했어요. 장소 핀은 그대로 보여 드려요.", "Could not load the route lines. The pins are still shown.") : undefined} />
        </div>
        {/* 지도 아래 안내 줄(계획 확인 화면과 같다): 핀이 없는 일정 · 경로선을 읽지 못함. 수단 태그(지하철 · 버스 · 도보)는 띄우지 않는다(2026-10-07 사용자 결정). */}
        {(unlocated.length > 0 || routeShapes.isError) && <div className={pc.mapChips}>
          {unlocated.length > 0 && <p className={pc.unlocated}>{t("위치 미정", "No location")} · {unlocated.map((stop) => stop.title).join(", ")}</p>}
          {routeShapes.isError && <p className={pc.unlocated} role="status">{t("경로선을 불러오지 못했어요. 장소 핀은 그대로 보여 드려요.", "Could not load the route lines. The pins are still shown.")}</p>}
        </div>}
        <section ref={sheetBox} className={pc.sheet} aria-label={t("일정 목록", "Itinerary")}>
          <button type="button" className={pc.handle} aria-label={t("목록 높이 바꾸기", "Change the list height")} title={t("눌러서 높이를 바꾸고, 잡고 끌어 원하는 높이로 맞춰요", "Press to change the height, or drag it to any height")}
            onClick={cycleSheet} onPointerDown={grabSheet} onPointerMove={dragSheet} onPointerUp={dropSheet} onPointerCancel={dropSheet} onKeyDown={nudgeSheet}><span aria-hidden="true" /></button>
          {/* `[2026-10-07 사용자 결정]` 머리는 날짜 칩 줄 하나: 칩은 옆으로 스크롤되고 오른쪽 「일정 | 채팅」은 고정(자리는 정하는 중이라 임시). 「등록 완료」 표시는 두지 않는다. */}
          {detailStop && <TripDetail trip={trip} stopId={detailStop.id} dayNumber={days.indexOf(detailStop.date) + 1} onStop={detailTo}
            onAsk={(stop) => { setDetailId(null); setSelectedId(stop.id); chat.askAbout(stop); }} askBusy={chat.message.isPending} onSheetFull={() => { setCustom(null); setSheet("full"); }} />}
          {/* The list and the chat stay mounted under the detail (their gestures and scroll are kept), only hidden. */}
          <header className={`${pc.sheetHead} ${detailStop ? styles.away : ""}`} onPointerDown={grabSheet} onPointerMove={dragSheet} onPointerUp={dropSheet} onPointerCancel={dropSheet}>
            {days.length > 1 && <div ref={stripBox} className={pc.dayStrip} role="tablist" aria-label={t("일차 고르기", "Choose a day")}
              onKeyDown={(event) => {
                if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
                const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role="tab"]'));
                const target = tabs[tabs.indexOf(document.activeElement as HTMLElement) + (event.key === "ArrowRight" ? 1 : -1)];
                if (target) { event.preventDefault(); target.focus(); target.click(); }
              }}>
              <span ref={markerBox} className={pc.dayMarker} aria-hidden="true" />
              <button type="button" role="tab" className={pc.dayChip} aria-selected={all} tabIndex={all ? 0 : -1} onClick={() => { chooseAll(); goPane("plan"); }}>{t("전체", "All")}</button>
              {days.map((date, index) => <button key={date} type="button" role="tab" className={pc.dayChip} aria-selected={!all && date === mapDay} tabIndex={!all && date === mapDay ? 0 : -1}
                onClick={() => { goDay(date); goPane("plan"); }}>{dayName(index, t)}<small>{dayLabel(date, language)}</small></button>)}
            </div>}
            <div className={styles.headTools}>
              {/* `[2026-10-07 목업 C안]` 재난으로 정지된 동안만 「일정 | 채팅」 앞에 — 누르면 알림 센터(할 일 맨 위가 정지 패널). */}
              {trip.safety?.paused && <button type="button" className={styles.pausedChip} onClick={() => openCenter()} aria-label={t("일정 정지 중 · 알림 센터 열기", "Itinerary paused · open notices")}>
                <OctagonAlert size={16} strokeWidth={2} aria-hidden="true" />{t("일정 정지 중", "Paused")}</button>}
              <div className={styles.paneSwitch} role="tablist" aria-label={t("일정과 채팅 바꾸기", "Itinerary or chat")}>
                <button type="button" role="tab" id="trip-pane-button-schedule" aria-selected={plan} aria-controls="trip-pane-schedule" onClick={() => goPane("plan")}>{t("일정", "Schedule")}</button>
                <button type="button" role="tab" id="trip-pane-button-chat" aria-selected={!plan} aria-controls="trip-pane-chat" onClick={() => goPane("chat")}>{t("채팅", "Chat")}</button>
              </div>
            </div>
          </header>
          <div className={`${styles.pager} ${detailStop ? styles.away : ""}`}>
            <div ref={pagerTrack} className={styles.pagerTrack} data-pane={pane} data-instant={instant || undefined}>
              <div className={styles.pane} id="trip-pane-schedule" role="tabpanel" aria-labelledby="trip-pane-button-schedule" inert={!plan}>
                <div ref={bodyBox} className={`${pc.sheetBody} ${styles.planBody}`}>
                  {stale && <div className={styles.stale} role="alert"><p>{t("최신 여행 정보를 불러오지 못했어요. 마지막으로 확인한 내용을 보여 드리고 있어요.", "The latest trip could not be loaded. This is what we last saw.")}</p>
                    <button type="button" className={styles.action} onClick={stale.reload} disabled={stale.fetching}>{t("다시 불러오기", "Reload")}</button></div>}
                  {trip.safety?.paused && <div className={styles.safetyTop}><SafetyPanel trip={trip} notices={notices.data ?? []} onChanged={refresh} onResumed={resumed} /></div>}
                  <div ref={dayTrack} className={pc.dayTrack}>
                    {near && <div className={pc.peek} data-side={peek.side} style={{ top: peek.top }} aria-hidden="true" inert>{dayList(near)}</div>}
                    {peek.side !== 0 && peek.edge && <p className={pc.edgeNote} data-side={peek.side} style={{ top: peek.top + 28 }} aria-hidden="true">{peek.side === 1 ? t("마지막 날이에요", "Last day") : t("첫날이에요", "First day")}</p>}
                    <div key={all ? "all" : mapDay} className={pc.page} data-slide={slide ?? undefined}>{listDays.map(dayList)}</div>
                  </div>
                  {trip.stops.length === 0 && <p className={pc.empty}>{t("등록한 일정이 없어요.", "There are no stops.")}</p>}
                  {trip.stops.length > 0 && <p className={pc.credit}>{t("예약 표시는 입력한 정보 기준입니다. · 장소 정보 출처 : ⓒ한국관광공사 · ", "Booking notes reflect the information you entered. · Place data: ⓒKorea Tourism Organization · ")}<a href={TOUR_API_POLICY_URL} target="_blank" rel="noreferrer">{t("저작권 정책", "Copyright policy")}</a>
                    {drawn.length > 0 && <><br />{routeDetail.routes?.attribution}{routeNotes(drawn).map((note) => <span key={note} data-route-note><br />{note}</span>)}</>}</p>}
                  <p className={pc.dayHint}>{nextDay ? t(`옆으로 밀면 ${dayName(dayAt + 1, t)} ${dayLabel(nextDay, language)} 일정이 나와요`, `Swipe sideways for day ${dayAt + 2}`) : t("옆으로 밀면 채팅이 나와요", "Swipe sideways for the chat")}<ChevronsRight size={15} strokeWidth={1.8} aria-hidden="true" /></p>
                </div>
              </div>
              <div ref={chatBox} className={`${styles.pane} ${styles.chatPane}`} id="trip-pane-chat" role="tabpanel" aria-labelledby="trip-pane-button-chat" inert={plan}>
                <ChatPane trip={trip} chat={chat} day={mapDay} dayText={dayName(dayAt, t)} selected={selected} logRef={chatLog} />
              </div>
            </div>
          </div>
        </section>
      </div>
      {titleOpen && !titleEditing && !detailStop && <TitleMenu planUrl={trip.planUrl ?? null} onShare={() => setShareOpen(true)} onDone={closeTitle} explain={explain} />}
      {shareOpen && trip.planUrl && <TripShare trip={trip} title={tripTitle} planUrl={trip.planUrl} onClose={closeShare} notify={showToast} />}
      {!detailStop && <ChatBar chat={chat} open={barOpen} inChat={!plan} onOpen={() => setBarOpen(true)} onClose={() => setBarOpen(false)} onEnterChat={() => goPane("chat")} />}
      {/* `[2026-10-07 목업 C안 ① 알림 센터]` 할 일(재난 정지 → 재난 뒤 이어가기 → 선택 요청 → 자동 변경) 아래 탭 셋(살펴볼 점 · 받은 알림 · 변경 이력). 여행계획서 링크는 제목을 펼친 줄에 있다. */}
      {centerOpen && <section className={styles.center} role="dialog" aria-modal="false" aria-labelledby="trip-center-title">
        <header className={styles.centerHead}>
          <button type="button" className={styles.centerBack} onClick={closeCenter} aria-label={t("알림 센터 닫기", "Close notices")}><ArrowLeft size={20} strokeWidth={1.6} aria-hidden="true" /></button>
          <h2 id="trip-center-title" tabIndex={-1} ref={(element) => element?.focus({ preventScroll: true })}>{t("알림", "Notices")}</h2>
        </header>
        <div className={styles.centerBody}><TripAttention trip={trip} tab={centerTab} onTab={setCenterTab} onResumed={resumed}
          onGoto={(stopId) => { setCenterOpen(false); pick(stopId, "list"); }} /></div>
      </section>}
    </main>
    {guardian.overlay}
    {shownToast && <ToastView key={shownToast.stamp} toast={shownToast.toast} onDone={hideToast} />}
  </DeviceFrame>;
}

/** The trip's name in the header's slot (inside the frame, where the slot is provided) — the plan check's title chip. */
/** What a pressed route line says, in the one notice bar: from where to where, how, when, what it rides — only what the server gave. */
/**
 * `[2026-10-07 목업 C안]` A notice the server just sent, in the notice bar: the stop's number and name when the notice is about one (a choice), the kind as a chip, the server's sentence
 * under it, 「알림 보기」 to the center. A safety alert says the pause and the nearest shelter and stays 9 s. ★Nothing is written for the server — no sentence, no stop it did not name.
 */
function noticeToast(notice: Notice, trip: Trip, proposals: readonly Proposal[], t: Translate, view: () => void): BusToast {
  const action = { label: t("알림 보기", "View notices"), run: view };
  const label = NOTICE_LABEL[notice.type];
  const kind = label ? t(label[0], label[1]) : notice.type;
  const sub = notice.text ?? undefined;
  if (notice.type === "safety_alert") {
    const shelter = notice.safety?.shelters[0];
    const meta = shelter ? shelterMeta(shelter, t) : "";
    // A pause alert (`safety_pause_<level>` — the server pauses with it) says so even before the trip is read again.
    const pausing = trip.safety?.paused || /^safety_pause_/.test(notice.kind ?? "");
    return { text: pausing ? t("일정 정지 중", "Itinerary paused") : kind, chip: { text: kind, tone: "warn" }, sub,
      note: shelter ? [t("가까운 대피 장소", "Nearest shelter"), shelter.name, meta].filter(Boolean).join(" · ") : undefined, action, ms: URGENT_MS };
  }
  if (notice.type === "proposal_request") {
    const proposal = proposals.find((entry) => entry.id === notice.proposalId);
    const stop = trip.stops.find((entry) => entry.id === proposal?.itemId);
    const order = stop ? trip.stops.filter((entry) => entry.date === stop.date).indexOf(stop) + 1 : 0;
    return { badge: stop ? String(order) : undefined, text: stop?.title ?? kind, chip: { text: kind, tone: "warn" }, sub,
      note: proposal?.expiresAt ? t(`${noticeWhen(proposal.expiresAt)} 까지`, `Until ${noticeWhen(proposal.expiresAt)}`) : undefined, action };
  }
  if (notice.type === "change_notice") return { text: kind, chip: { text: t("바뀜", "Changed"), tone: "changed" }, sub, action };
  return { text: kind, sub, action };
}

function legToast(leg: TripLeg, t: Translate, onList: () => void) {
  const times = leg.move ? [t(`${leg.move.departAt} 출발`, `Leave ${leg.move.departAt}`), leg.move.arriveAt && t(`${leg.move.arriveAt} 도착`, `arrive ${leg.move.arriveAt}`)].filter(Boolean).join(" → ") : null;
  return {
    badge: "→", text: `${leg.from.title} → ${leg.to.title}`,
    sub: [legSummary(leg, t), times, ...(leg.shape ? rideLines(leg.shape, t) : [])].filter(Boolean).join("\n"),
    note: leg.slack !== null && leg.slack < 0 ? t(`다음 일정보다 ${Math.abs(leg.slack)}분 늦어요`, `${Math.abs(leg.slack)} min late for the next stop`) : undefined,
    action: { label: t("목록에서 보기", "Show in list"), run: onList }, ms: READ_MS,
  };
}
