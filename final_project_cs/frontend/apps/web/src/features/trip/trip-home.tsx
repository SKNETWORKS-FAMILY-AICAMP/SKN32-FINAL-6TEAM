"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, CalendarDays, Check, Leaf, MapPin, MessageCircle, SquarePen, Send, ShieldCheck } from "lucide-react";
import { TripMap } from "@/features/map";
import { mapConfiguration } from "@/features/map/config";
import { Badge, Button, ButtonLink, Eyebrow, Panel, QueryState } from "@/components/ui";
import { tripGateway } from "@/lib/gateway";
import type { Translate } from "@/lib/i18n";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import { tripKey, useTrip } from "./use-trip";
import type { Trip, TripStop } from "./model";
import styles from "./trip-home.module.css";

type Pane = "schedule" | "map" | "chat";
const icon = { size: 18, strokeWidth: 1.6, "aria-hidden": true } as const;

function bookingLabel(stop: TripStop, t: Translate) {
  if (stop.booking === "booked") return t("예약 있음", "Booking noted");
  if (stop.booking === "none") return t("예약 없음", "No booking noted");
  return t("예약 정보 없음", "Booking not specified");
}

export function TripHome({ tripId }: { tripId: string }) {
  const t = useT();
  const query = useTrip(tripId);
  if (query.isPending || query.error || !query.data) {
    return <QueryState loading={query.isPending} error={query.error} retry={() => void query.refetch()} />;
  }
  const trip = query.data;
  if (trip.status !== "active") {
    const processing = trip.status === "processing" || trip.status === "failed";
    return <Panel className={styles.gate}>
      <ShieldCheck size={28} strokeWidth={1.6} aria-hidden="true" />
      <h1>{processing ? t("여행 계획을 확인하고 있어요", "We’re still checking your plan") : t("검증 결과를 먼저 확인해 주세요", "Review your results first")}</h1>
      <p>{processing ? t("확인이 끝나면 결과를 보고 여행 관리를 시작할 수 있어요.", "Once the check is complete, review the results and start your trip.") : t("검증 결과 화면에서 여행 관리를 시작하면 일정·방문 순서·채팅을 이용할 수 있어요.", "Start your trip from the results to use the itinerary, visit order and chat.")}</p>
      <ButtonLink href={processing ? routes.verification(tripId) : routes.results(tripId)}>{processing ? t("확인 진행 보기", "View the check") : t("검증 결과 보기", "View results")}<ArrowRight {...icon} /></ButtonLink>
    </Panel>;
  }
  return <TripWorkspace key={trip.id} trip={trip} />;
}

function TripWorkspace({ trip }: { trip: Trip }) {
  const t = useT();
  const { language, navigation } = useSettings();
  const queryClient = useQueryClient();
  const days = [...new Set(trip.stops.map((stop) => stop.date))].sort();
  const [day, setDay] = useState(days[0]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pane, setPane] = useState<Pane>("schedule");
  const [navOpen, setNavOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const [inputError, setInputError] = useState("");
  const chatLog = useRef<HTMLDivElement>(null);
  const nav = useRef<HTMLElement>(null);
  const activeDay = days.includes(day) ? day : days[0];
  const dayIndex = days.indexOf(activeDay);
  const dayText = t(`${dayIndex + 1}일차`, `Day ${dayIndex + 1}`);
  const stops = trip.stops.filter((stop) => stop.date === activeDay);
  const selected = stops.find((stop) => stop.id === selectedId) ?? stops[0];
  const diagram = mapConfiguration.provider === "demo";
  const message = useMutation({
    mutationFn: ({ text }: { text: string; clearDraft: boolean }) => tripGateway.sendMessage(trip.id, text, language),
    onSuccess: (updated, variables) => {
      queryClient.setQueryData(tripKey(trip.id, language), updated);
      if (variables.clearDraft) setDraft("");
    },
  });

  useEffect(() => {
    if (chatLog.current) chatLog.current.scrollTop = chatLog.current.scrollHeight;
  }, [trip.messages.length, message.isPending, pane]);

  useEffect(() => {
    if (!navOpen) return;
    const close = (event: Event) => {
      if (event instanceof KeyboardEvent ? event.key === "Escape" : !nav.current?.contains(event.target as Node)) {
        setNavOpen(false);
        if (event instanceof KeyboardEvent) document.getElementById("trip-nav-toggle")?.focus();
      }
    };
    document.addEventListener("click", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("click", close); document.removeEventListener("keydown", close); };
  }, [navOpen]);

  const focus = (id: string) => requestAnimationFrame(() => document.getElementById(id)?.focus({ preventScroll: true }));

  function choose(stop: TripStop) {
    setDay(stop.date);
    setSelectedId(stop.id);
  }

  function showPane(next: Pane) {
    setPane(next);
    setNavOpen(false);
    focus(navigation === "floating" ? "trip-nav-toggle" : `trip-pane-button-${next}`);
  }

  function ask(text: string, clearDraft = false) {
    if (message.isPending) return;
    const trimmed = text.trim();
    if (!trimmed) {
      setInputError(t("메시지를 입력해 주세요.", "Enter a message."));
      document.getElementById("trip-chat-message")?.focus();
      return;
    }
    setInputError("");
    setPane("chat");
    message.mutate({ text: trimmed, clearDraft });
  }

  const askAbout = (stop: TripStop) => { choose(stop); ask(t(`${stop.date} ${stop.time} ${stop.title} 일정의 상세를 알려 주세요.`, `Tell me about the ${stop.title} stop on ${stop.date} at ${stop.time}.`)); };

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    ask(draft, true);
  }

  const tabs: [Pane, typeof CalendarDays, string][] = [
    ["schedule", CalendarDays, t("일정", "Schedule")],
    ["map", MapPin, diagram ? t("방문 순서", "Visit order") : t("지도", "Map")],
    ["chat", MessageCircle, t("채팅", "Chat")],
  ];
  const [, CurrentIcon, currentLabel] = tabs.find(([key]) => key === pane)!;
  const tabGroup = <div className={styles.tabs} role="group" aria-label={t("여행 화면", "Travel views")} inert={navigation === "floating" && !navOpen}>
    {tabs.map(([key, Icon, label]) => <button key={key} type="button" id={`trip-pane-button-${key}`} aria-pressed={pane === key} aria-controls={`trip-pane-${key}`} onClick={() => showPane(key)}><Icon {...icon} />{label}</button>)}
  </div>;

  return <div className={styles.workspace} data-navigation={navigation}>
    <section className={styles.tripbar} aria-labelledby="trip-home-title">
      <div><Eyebrow>{t("여행을 함께 살펴볼까요", "YOUR JOURNEY, TOGETHER")}</Eyebrow><h1 id="trip-home-title">{t("나의 여행", "Your trip")}</h1></div>
      <p className={styles.tripmeta}><CalendarDays {...icon} /><span>{days.length > 1 ? `${days[0]} – ${days.at(-1)}` : days[0]}<br />{t(`${days.length}일 · ${trip.stops.length}개 일정`, `${days.length} days · ${trip.stops.length} stops`)}</span></p>
    </section>
    <div className={styles.watchbar}><strong><Check {...icon} />{t("여행 관리 화면", "Your travel workspace")}</strong><span>{t("입력한 일정으로 둘러보는 데모", "A demo using your itinerary")}</span></div>
    <div className={styles.daybar}>
      <div className={styles.dayTabs} role="group" aria-label={t("여행 일차", "Travel days")}>{days.map((date, index) => (
        <button key={date} type="button" aria-pressed={date === activeDay} onClick={() => { setDay(date); setSelectedId(null); setExpandedId(null); }}>{t(`${index + 1}일차`, `Day ${index + 1}`)}<span>{date.slice(5).replace("-", ".")}</span></button>
      ))}</div>
      <ButtonLink href={`${routes.newTrip}?from=${encodeURIComponent(trip.id)}`}><SquarePen {...icon} />{t("일정 수정", "Edit itinerary")}</ButtonLink>
    </div>
    {navigation === "floating"
      ? <nav ref={nav} className={`${styles.floating} ${navOpen ? styles.open : ""}`} aria-label={t("여행 화면", "Travel views")}>
        <button type="button" id="trip-nav-toggle" className={styles.toggle} aria-label={`${currentLabel} · ${t("메뉴 열기 또는 닫기", "Toggle navigation")}`} aria-expanded={navOpen} aria-controls="trip-floating-menu"
          onClick={() => { setNavOpen(true); focus(`trip-pane-button-${pane}`); }}><CurrentIcon size={21} strokeWidth={1.6} aria-hidden="true" /></button>
        <div id="trip-floating-menu" className={styles.menu}>{tabGroup}</div>
      </nav>
      : <nav className={styles.fixed} aria-label={t("여행 화면", "Travel views")}>{tabGroup}</nav>}
    <section className={styles.pane} id="trip-pane-schedule" hidden={pane !== "schedule"} aria-labelledby="trip-schedule-heading">
      <header className={styles.panehead}><h2 id="trip-schedule-heading">{dayText} {t("일정", "schedule")}</h2><Badge>{t(`${stops.length}개`, `${stops.length} stops`)}</Badge></header>
      <div className={styles.timeline}>{stops.map((stop, index) => {
        const expanded = expandedId === stop.id;
        const next = stops[index + 1];
        return <div key={stop.id}>
          <article className={styles.stop} data-selected={selected?.id === stop.id}>
            <button type="button" className={styles.stophead} id={`stop-button-${stop.id}`} aria-expanded={expanded} aria-controls={`stop-detail-${stop.id}`} onClick={() => { setSelectedId(stop.id); setExpandedId(expanded ? null : stop.id); }}>
              <time>{stop.time}</time>
              <span className={styles.stopCopy}><strong>{stop.title}</strong><span className={styles.stopTags}><Badge>{bookingLabel(stop, t)}</Badge>{stop.originalTime && stop.originalTime !== stop.time && <Badge>{t("시간 조정", "Time adjusted")}</Badge>}</span></span>
              <span className={styles.toggleMark} aria-hidden="true">{expanded ? "−" : "+"}</span>
            </button>
            {expanded && <div className={styles.stopDetails} id={`stop-detail-${stop.id}`}>
              <dl className={styles.details}>
                <dt>{t("날짜", "Date")}</dt><dd>{stop.date}</dd>
                <dt>{t("예정 시간", "Planned time")}</dt><dd>{stop.time}</dd>
                <dt>{t("예약 표시", "Booking note")}</dt><dd>{bookingLabel(stop, t)}</dd>
                {stop.originalTime && stop.originalTime !== stop.time && <><dt>{t("시간 조정", "Time adjustment")}</dt><dd>{stop.originalTime} → {stop.time}</dd></>}
                <dt>{t("다음 일정", "Next stop")}</dt><dd>{next ? `${next.time} · ${next.title}` : t("이날 마지막 일정", "Last stop of the day")}</dd>
                <dt>{t("입력한 메모", "Your notes")}</dt><dd>{stop.notes || t("등록된 메모가 없어요.", "No notes added.")}</dd>
              </dl>
              <div className={styles.detailActions}>
                <Button onClick={() => { choose(stop); setPane("map"); focus(`map-point-${stop.id}`); }}><MapPin {...icon} />{diagram ? t("방문 순서 보기", "Show visit order") : t("지도에서 보기", "Show on map")}</Button>
                <Button disabled={message.isPending} onClick={() => askAbout(stop)}><MessageCircle {...icon} />{t("이 일정 질문하기", "Ask about this stop")}</Button>
              </div>
            </div>}
          </article>
          {index < stops.length - 1 && <p className={styles.movement}><ArrowRight size={13} strokeWidth={1.6} aria-hidden="true" />{t("다음 일정으로", "Next stop")}</p>}
        </div>;
      })}
      {!stops.length && <p className={styles.empty}>{t("이 날짜에는 등록한 일정이 없어요.", "There are no stops for this date.")}</p>}</div>
    </section>
    <section className={`${styles.pane} ${styles.mapPane}`} id="trip-pane-map" hidden={pane !== "map"} aria-labelledby="trip-map-heading">
      <header className={styles.panehead}><h2 id="trip-map-heading">{diagram ? t("방문 순서 개념도", "Visit order diagram") : t("지도", "Map")}</h2><span className={styles.muted}>{dayText}</span></header>
      <TripMap stops={stops} selectedId={selected?.id} dayNumber={dayIndex + 1} onSelect={(stopId) => setSelectedId(stopId)} />
      {diagram && <p className={styles.chatnote}>{t("번호는 방문 순서입니다. 실제 위치·거리·이동 경로를 표시하지 않습니다.", "Numbers show visit order, not actual locations, distances, or routes.")}</p>}
      <div className={styles.mapSelection}>{selected ? <>
        <Eyebrow>{t("선택한 일정", "SELECTED STOP")}</Eyebrow>
        <h3>{selected.title}</h3>
        <p className={styles.muted}>{selected.time} · {bookingLabel(selected, t)}</p>
        <p>{selected.notes || t("등록된 메모가 없어요.", "No notes added.")}</p>
        <div className={styles.detailActions}>
          <Button onClick={() => { setExpandedId(selected.id); setPane("schedule"); requestAnimationFrame(() => { const button = document.getElementById(`stop-button-${selected.id}`); button?.scrollIntoView({ block: "nearest" }); button?.focus({ preventScroll: true }); }); }}>{t("일정 상세 보기", "View details")}<ArrowRight {...icon} /></Button>
          <Button disabled={message.isPending} onClick={() => askAbout(selected)}><MessageCircle {...icon} />{t("채팅으로 질문", "Ask in chat")}</Button>
        </div>
      </> : <p className={styles.muted}>{t("일정을 선택하면 상세가 표시돼요.", "Select a stop to see its details.")}</p>}</div>
    </section>
    <section className={`${styles.pane} ${styles.chatPane}`} id="trip-pane-chat" hidden={pane !== "chat"} aria-labelledby="trip-chat-heading">
      <header className={styles.panehead}><h2 id="trip-chat-heading">{t("여행 채팅", "Travel chat")}</h2><Badge>{t("데모", "Demo")}</Badge></header>
      <div ref={chatLog} className={styles.chatlog} role="log" aria-label={t("여행 대화 이력", "Travel conversation")} aria-live="polite" aria-relevant="additions text" aria-busy={message.isPending}>
        <div className={styles.chatcontext}><strong>{dayText} · {activeDay}</strong><span>{selected ? t(`선택: ${selected.title}`, `Selected: ${selected.title}`) : t("선택한 일정이 없어요.", "No stop selected.")}</span></div>
        {trip.messages.length === 0 && <article className={styles.message} data-role="assistant"><p className={styles.messageMeta}>triPilot</p><p className={styles.bubble}>{t("등록한 일정에서 궁금한 내용을 골라 주세요. 하루 요약, 선택한 장소와 다음 일정을 함께 살펴볼 수 있어요.", "Explore your saved itinerary. Ask for a day summary, details of your selected stop, or what comes next.")}</p></article>}
        {trip.messages.map((item) => <article key={item.id} className={styles.message} data-role={item.role}><p className={styles.messageMeta}>{item.role === "user" ? t("나", "You") : "triPilot"}</p><p className={styles.bubble}>{item.text}</p></article>)}
        {message.isPending && <>
          <article className={styles.message} data-role="user"><p className={styles.messageMeta}>{t("나", "You")}</p><p className={styles.bubble}>{message.variables.text}</p></article>
          <p className={styles.pending} role="status">{t("답변을 준비하고 있어요…", "Preparing a reply…")}</p>
        </>}
      </div>
      <div className={styles.composer}>
        <div className={styles.prompts}>
          <Button variant="quiet" disabled={message.isPending} onClick={() => ask(t(`${activeDay} 하루 일정을 요약해 주세요.`, `Summarize the itinerary for ${activeDay}.`))}>{t("하루 요약", "Day summary")}</Button>
          <Button variant="quiet" disabled={!selected || message.isPending} onClick={() => selected && askAbout(selected)}>{t("선택 일정", "Selected stop")}</Button>
          <Button variant="quiet" disabled={!selected || message.isPending} onClick={() => selected && ask(t(`${selected.date} ${selected.time} ${selected.title} 다음 일정을 알려 주세요.`, `What comes after ${selected.title} on ${selected.date} at ${selected.time}?`))}>{t("다음 일정", "Next stop")}</Button>
          <Button variant="quiet" disabled={message.isPending} onClick={() => ask(t(`${activeDay} 예약 표시를 알려 주세요.`, `Show booking notes for ${activeDay}.`))}>{t("예약 표시", "Booking notes")}</Button>
        </div>
        <form className={styles.chatForm} onSubmit={submit} noValidate>
          <label className="sr-only" htmlFor="trip-chat-message">{t("여행 메시지", "Travel message")}</label>
          <input id="trip-chat-message" className={styles.chatInput} value={draft} maxLength={600} autoComplete="off" placeholder={t("일정에 대해 궁금한 점을 입력하세요", "Ask about your itinerary")} disabled={message.isPending}
            aria-invalid={Boolean(inputError)} aria-describedby={inputError ? "trip-chat-error" : undefined} onChange={(event) => { setDraft(event.target.value); if (inputError) setInputError(""); }} />
          <Button type="submit" variant="primary" disabled={message.isPending} aria-label={t("메시지 전송", "Send message")}><Send {...icon} /><span className={styles.sendText}>{t("전송", "Send")}</span></Button>
          {inputError && <p id="trip-chat-error" className={styles.error} role="alert">{inputError}</p>}
        </form>
        {message.isError && <div className={styles.error} role="alert"><p>{t("메시지를 보내지 못했어요.", "The message could not be sent.")} {message.error.message}</p><Button onClick={() => message.variables && message.mutate(message.variables)}>{t("다시 보내기", "Send again")}</Button></div>}
        <p className={styles.chatnote}>{t("등록된 일정에 대한 시연 응답입니다. 실제 일정·예약 변경은 실행되지 않습니다.", "Demo replies use your itinerary. No actual itinerary or booking changes are performed.")}</p>
      </div>
    </section>
    <footer className={styles.footer}><span><Leaf {...icon} />{t("예약 표시는 입력한 정보 기준입니다.", "Booking notes reflect the information you entered.")}</span><ButtonLink href={routes.results(trip.id)} variant="quiet">{t("검증 결과 다시 보기", "Review verification results")}<ArrowRight {...icon} /></ButtonLink></footer>
  </div>;
}
