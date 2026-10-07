"use client";

import { Suspense, useContext, useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react";
import { createPortal } from "react-dom";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Bell, ChevronsRight } from "lucide-react";
import { DeviceFrame, HeaderSlot } from "@/components/layout/device-frame";
import { JourneyShell } from "@/components/layout/journey-shell";
import { ToastView, useToastState } from "@/components/toast-view";
import { QueryState } from "@/components/ui";
import { TripMap } from "@/features/map";
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
import { onToast } from "@/lib/toast-bus";
import { useDocumentTitle } from "@/lib/use-document-title";
import { ChatBar, ChatPane, useTripChat } from "./trip-chat";
import { LegRow, legSummary, StopRow } from "./trip-rows";
import { dayTimeline, tripDays, type TripLeg } from "./trip-timeline";
import { TripAttention } from "./trip-attention";
import { SafetyPanel } from "./trip-safety";
import { tripKey, useTrip } from "./use-trip";
import { useRouteShapes } from "./use-route-shapes";
import { useTripEvents } from "./use-trip-events";
import { noticesKey, proposalsKey, recoveryKey, useNotices } from "./use-trip-extras";
import type { Recovery } from "@/lib/live/recovery";
import type { Trip } from "./model";
import styles from "./trip-screen.module.css";

/** 한국관광공사 이용조건 — 관광정보를 화면에 올리면 출처와 저작권 정책 링크를 같이 준다. */
const TOUR_API_POLICY_URL = "https://api.visitkorea.or.kr/#/useServiceGuide/2";
/** A description has more to read than a one-line notice: it stays this long (the pointer on its button keeps it). */
const READ_MS = 7_000;
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
  const resumed = (brief: Recovery | null) => queryClient.setQueryData(recoveryKey(trip.id, language), brief);

  // ── Keys: Esc closes what is on top. ──
  function onKey(event: KeyboardEvent<HTMLElement>) {
    if (event.key !== "Escape" || event.defaultPrevented) return;
    if (centerOpen) { event.preventDefault(); setCenterOpen(false); requestAnimationFrame(() => document.getElementById("trip-bell")?.focus()); return; }
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
            onDetail={() => undefined} detailWhy={t("상세 보기는 준비 중이에요", "Details are coming")} explain={explain}
            onShowOnMap={() => pick(entry.stop.id, "list")} onAsk={() => { setSelectedId(entry.stop.id); chat.askAbout(entry.stop); }} askBusy={chat.message.isPending} />
        : <LegRow key={entry.leg.id} leg={entry.leg} open={openId === entry.leg.id}
            onToggle={() => { setOpenId((current) => current === entry.leg.id ? null : entry.leg.id); setSelectedLine((current) => entry.leg.shape && current !== entry.leg.shape.itemId ? entry.leg.shape.itemId : null); setSelectedId(null); }} />)}</ol>
    </section>;
  };
  const near = peek.side === 0 ? undefined : days[dayAt + peek.side];
  const plan = pane === "plan";

  return <DeviceFrame floating menuTools={guardian.tool}
    headerExtra={<button type="button" id="trip-bell" className={styles.bell} onClick={() => setCenterOpen(true)} aria-label={t("알림 센터 열기", "Open notices")} aria-haspopup="dialog" aria-expanded={centerOpen}><Bell size={20} strokeWidth={2} aria-hidden="true" /></button>}>
    <main id="main-content" tabIndex={-1} className={`${pc.screen} ${styles.screen}`} data-floating onKeyDown={onKey}>
      <HeaderTitle title={trip.title ?? t("나의 여행", "Your trip")} />
      <div ref={box} className={pc.checking} data-sheet={custom !== null ? "custom" : sheet} data-dragging={dragging || undefined} data-compact={compact || undefined}
        style={custom !== null ? { "--sheet-h": `${custom}px` } as CSSProperties : undefined}>
        <div className={pc.map}>
          <TripMap stops={mapStops} dayNumber={dayAt + 1} selectedId={selectedId ?? undefined} variant="fill" topInset={64} bottomInset={24} routes={routeDetail.routes} onZoom={routeDetail.onZoom}
            onSelect={(id) => pick(id, "map")} onSelectLine={pickLine} selectedLineId={selectedLine ?? undefined} tripId={trip.id} date={mapDay}
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
          <header className={pc.sheetHead} onPointerDown={grabSheet} onPointerMove={dragSheet} onPointerUp={dropSheet} onPointerCancel={dropSheet}>
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
              <div className={styles.paneSwitch} role="tablist" aria-label={t("일정과 채팅 바꾸기", "Itinerary or chat")}>
                <button type="button" role="tab" id="trip-pane-button-schedule" aria-selected={plan} aria-controls="trip-pane-schedule" onClick={() => goPane("plan")}>{t("일정", "Schedule")}</button>
                <button type="button" role="tab" id="trip-pane-button-chat" aria-selected={!plan} aria-controls="trip-pane-chat" onClick={() => goPane("chat")}>{t("채팅", "Chat")}</button>
              </div>
            </div>
          </header>
          <div className={styles.pager}>
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
      <ChatBar chat={chat} open={barOpen} inChat={!plan} onOpen={() => setBarOpen(true)} onClose={() => setBarOpen(false)} onEnterChat={() => goPane("chat")} />
      {/* 1단계: 종을 누르면 지금까지의 여행 알림 묶음(선택 요청 · 되돌리기 · 재난 · 살펴볼 점 · 받은 알림 · 변경 이력 · 여행계획서)을 한 칸에 연다. 알림 센터의 탭 · 할 일은 2단계. */}
      {centerOpen && <section className={styles.center} role="dialog" aria-modal="false" aria-labelledby="trip-center-title">
        <header className={styles.centerHead}>
          <button type="button" className={styles.centerBack} onClick={() => { setCenterOpen(false); requestAnimationFrame(() => document.getElementById("trip-bell")?.focus()); }} aria-label={t("알림 센터 닫기", "Close notices")}><ArrowLeft size={20} strokeWidth={1.6} aria-hidden="true" /></button>
          <h2 id="trip-center-title" tabIndex={-1} ref={(element) => element?.focus({ preventScroll: true })}>{t("알림", "Notices")}</h2>
        </header>
        <div className={styles.centerBody}><TripAttention trip={trip} /></div>
      </section>}
    </main>
    {guardian.overlay}
    {shownToast && <ToastView key={shownToast.stamp} toast={shownToast.toast} onDone={hideToast} />}
  </DeviceFrame>;
}

/** The trip's name in the header's slot (inside the frame, where the slot is provided) — the plan check's title chip. */
function HeaderTitle({ title }: { title: string }) {
  const slot = useContext(HeaderSlot);
  return slot && createPortal(<div className={pc.headInfo} data-title><h1 className={pc.headTitle}>{title}</h1></div>, slot);
}

/** What a pressed route line says, in the one notice bar: from where to where, how, when, what it rides — only what the server gave. */
function legToast(leg: TripLeg, t: Translate, onList: () => void) {
  const times = leg.move ? [t(`${leg.move.departAt} 출발`, `Leave ${leg.move.departAt}`), leg.move.arriveAt && t(`${leg.move.arriveAt} 도착`, `arrive ${leg.move.arriveAt}`)].filter(Boolean).join(" → ") : null;
  return {
    badge: "→", text: `${leg.from.title} → ${leg.to.title}`,
    sub: [legSummary(leg, t), times, ...(leg.shape ? rideLines(leg.shape, t) : [])].filter(Boolean).join("\n"),
    note: leg.slack !== null && leg.slack < 0 ? t(`다음 일정보다 ${Math.abs(leg.slack)}분 늦어요`, `${Math.abs(leg.slack)} min late for the next stop`) : undefined,
    action: { label: t("목록에서 보기", "Show in list"), run: onList }, ms: READ_MS,
  };
}

