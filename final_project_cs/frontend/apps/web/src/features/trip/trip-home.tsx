"use client";

import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowDown, ArrowRight, CalendarDays, Check, ChevronDown, MessageCircle, Minus, Plus, Send, ShieldCheck } from "lucide-react";
import { TripMap } from "@/features/map";
import { Badge, Button, ButtonLink, Panel, QueryState } from "@/components/ui";
import { tripGateway } from "@/lib/gateway";
import { routes } from "@/lib/routes";
import { tripKey, useTrip } from "./use-trip";
import type { Trip, TripMessage, TripStop } from "./model";
import styles from "./trip-home.module.css";

type WorkspacePane = "schedule" | "map" | "chat";

const paneLabels: Record<WorkspacePane, string> = {
  schedule: "일정",
  map: "지도",
  chat: "채팅",
};

const bookingLabels: Record<TripStop["booking"], string> = {
  booked: "예약 있음 · 입력한 계획 기준",
  none: "예약 없음",
  unknown: "예약 정보가 입력되지 않았어요",
};

function navigateTabs(event: KeyboardEvent<HTMLDivElement>) {
  const tabs = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
  const current = tabs.indexOf(event.target as HTMLButtonElement);
  if (current < 0) return;
  let next = current;
  if (event.key === "ArrowRight") next = (current + 1) % tabs.length;
  else if (event.key === "ArrowLeft") next = (current - 1 + tabs.length) % tabs.length;
  else if (event.key === "Home") next = 0;
  else if (event.key === "End") next = tabs.length - 1;
  else return;
  event.preventDefault();
  tabs[next]?.focus();
  tabs[next]?.click();
}

function formatDate(date: string) {
  const [, month, day] = date.split("-");
  return month && day ? `${Number(month)}월 ${Number(day)}일` : date;
}

function calendarDayNumber(date: string, startDate: string) {
  return Math.max(1, Math.round((Date.parse(`${date}T00:00:00Z`) - Date.parse(`${startDate}T00:00:00Z`)) / 86_400_000) + 1);
}

function timeRange(stop: TripStop) {
  return stop.endTime ? `${stop.time}–${stop.endTime}` : stop.time;
}

export function TripHome({ tripId }: { tripId: string }) {
  const query = useTrip(tripId);
  if (query.isPending || query.error || !query.data) {
    return <QueryState loading={query.isPending} error={query.error} retry={() => void query.refetch()} />;
  }
  const trip = query.data;
  if (trip.status !== "active") {
    const processing = trip.status === "processing";
    return (
      <div className={styles.gate}>
        <Panel>
          <ShieldCheck size={28} aria-hidden="true" />
          <h1>{processing ? "여행 계획을 검증하고 있어요" : "검증 결과를 먼저 확인해 주세요"}</h1>
          <p>{processing ? "검증이 끝나면 결과를 확인하고 여행 관리를 시작할 수 있어요." : "검증 결과 화면에서 여행 관리 시작을 누르면 일정·지도·채팅을 이용할 수 있어요."}</p>
          <ButtonLink href={processing ? routes.verification(tripId) : routes.results(tripId)}>
            {processing ? "검증 진행 보기" : "검증 결과 보기"}<ArrowRight size={16} aria-hidden="true" />
          </ButtonLink>
        </Panel>
      </div>
    );
  }
  return <TripWorkspace key={trip.id} trip={trip} />;
}

function TripWorkspace({ trip }: { trip: Trip }) {
  const days = Array.from(new Set(trip.stops.map((stop) => stop.date))).sort();
  if (days.length === 0) days.push(trip.startDate);
  const [date, setDate] = useState(days[0]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [pane, setPane] = useState<WorkspacePane>("schedule");
  const [draft, setDraft] = useState("");
  const [inputError, setInputError] = useState("");
  const chatInput = useRef<HTMLInputElement>(null);
  const chatLog = useRef<HTMLDivElement>(null);
  const timelineButtons = useRef(new Map<string, HTMLButtonElement>());
  const queryClient = useQueryClient();
  const activeDate = days.includes(date) ? date : days[0];
  const dayNumber = calendarDayNumber(activeDate, trip.startDate);
  const travelDays = calendarDayNumber(trip.endDate, trip.startDate);
  const stops = trip.stops.filter((stop) => stop.date === activeDate);
  const selected = stops.find((stop) => stop.id === selectedId) ?? stops[0];
  const message = useMutation({
    mutationFn: ({ text }: { text: string; clearDraft: boolean }) => tripGateway.sendMessage(trip.id, text),
    onSuccess: (updated, variables) => {
      queryClient.setQueryData(tripKey(trip.id), updated);
      if (variables.clearDraft) setDraft("");
    },
  });

  useEffect(() => {
    const log = chatLog.current;
    if (log) log.scrollTop = log.scrollHeight;
  }, [trip.messages.length, message.isPending, pane]);

  function selectDay(next: string) {
    setDate(next);
    setSelectedId(null);
    setExpandedId(null);
  }

  function selectStop(stopId: string, expand: boolean) {
    setSelectedId(stopId);
    if (expand) setExpandedId(expandedId === stopId ? null : stopId);
  }

  function ask(text: string, clearDraft = false) {
    if (message.isPending) return;
    const trimmed = text.trim();
    if (!trimmed) {
      setInputError("메시지를 입력해 주세요.");
      chatInput.current?.focus();
      return;
    }
    setInputError("");
    setPane("chat");
    message.mutate({ text: trimmed, clearDraft });
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    ask(draft, true);
  }

  function showOnTimeline(stopId: string) {
    setSelectedId(stopId);
    setExpandedId(stopId);
    setPane("schedule");
    requestAnimationFrame(() => {
      const button = timelineButtons.current.get(stopId);
      button?.closest("article")?.scrollIntoView({ block: "start", behavior: "instant" });
      button?.focus({ preventScroll: true });
    });
  }

  function askAbout(stop: TripStop) {
    ask(`${stop.date} ${stop.time} ${stop.title} 일정의 상세와 확인할 조건을 알려 주세요.`);
  }

  return (
    <div className={styles.home}>
      <section className={styles.tripbar} aria-labelledby="trip-home-title">
        <div>
          <p className={styles.eyebrow}>READY FOR YOUR TRIP</p>
          <h1 id="trip-home-title">{trip.title}</h1>
        </div>
        <p className={styles.tripmeta}><CalendarDays size={15} aria-hidden="true" />{trip.startDate} – {trip.endDate}<span>· {travelDays}일 여행 · {trip.stops.length}개 일정</span></p>
      </section>
      <div className={styles.watchbar}>
        <strong><Check size={15} aria-hidden="true" />여행을 등록했어요 · 시작 대기</strong>
        <span>{trip.startDate}부터 · 서울 시각 기준</span>
      </div>
      <div className={styles.daybar}>
        <div className={styles.daytabs} role="tablist" aria-label="여행 일차" onKeyDown={navigateTabs}>
          {days.map((day) => (
            <button type="button" role="tab" id={`trip-day-${day}`} aria-controls="trip-day-panel" aria-selected={activeDate === day} tabIndex={activeDate === day ? 0 : -1} key={day} onClick={() => selectDay(day)}>
              {calendarDayNumber(day, trip.startDate)}일차 <span>{formatDate(day)}</span>
            </button>
          ))}
        </div>
        <ButtonLink href={`${routes.newTrip}?from=${encodeURIComponent(trip.id)}`} variant="secondary" className={styles.editLink}>일정 수정</ButtonLink>
      </div>
      <div className={styles.mobileTabs} role="tablist" aria-label="여행 화면" onKeyDown={navigateTabs}>
        {(Object.keys(paneLabels) as WorkspacePane[]).map((key) => (
          <button type="button" role="tab" id={`trip-pane-tab-${key}`} key={key} aria-controls={`trip-pane-${key}`} aria-selected={pane === key} tabIndex={pane === key ? 0 : -1} onClick={() => setPane(key)}>{paneLabels[key]}</button>
        ))}
      </div>
      <div id="trip-day-panel" role="tabpanel" aria-labelledby={`trip-day-${activeDate}`} className={styles.workspace}>
        <section className={styles.pane} id="trip-pane-schedule" role="tabpanel" aria-labelledby="trip-schedule-heading" data-active={pane === "schedule"}>
          <div className={styles.panehead}>
            <h2 id="trip-schedule-heading">{dayNumber}일차 일정</h2><Badge>{stops.length}개 항목</Badge>
          </div>
          <div className={styles.timeline}>
            {stops.map((stop, index) => (
              <div key={stop.id}>
                <article className={styles.stop} data-selected={selected?.id === stop.id}>
                  <button type="button" className={styles.stophead} id={`stop-button-${stop.id}`} aria-expanded={expandedId === stop.id} aria-controls={`stop-detail-${stop.id}`} onClick={() => selectStop(stop.id, true)} ref={(node) => { if (node) timelineButtons.current.set(stop.id, node); else timelineButtons.current.delete(stop.id); }}>
                    <time>{stop.time}</time>
                    <span><strong>{stop.title}</strong><span className={styles.stopsummary}>{stop.kind} · {stop.area}</span><span className={styles.stopTags}>{stop.booking === "booked" && <Badge>예약 있음</Badge>}{stop.originalTime && stop.originalTime !== stop.time && <Badge tone="success">첫 검증에서 조정</Badge>}</span></span>
                    {expandedId === stop.id ? <Minus size={14} aria-hidden="true" /> : <Plus size={14} aria-hidden="true" />}
                  </button>
                  {expandedId === stop.id && <div className={styles.stopdetails} id={`stop-detail-${stop.id}`} aria-labelledby={`stop-button-${stop.id}`}>
                    <h3>장소 상세</h3>
                    <StopDetails stop={stop} next={stops[index + 1]} />
                    <div className={styles.detailActions}>
                      <Button variant="secondary" onClick={() => { setSelectedId(stop.id); setPane("map"); }}>지도에서 보기</Button>
                      <Button variant="secondary" disabled={message.isPending} onClick={() => askAbout(stop)}>이 일정 질문하기</Button>
                    </div>
                  </div>}
                </article>
                {index < stops.length - 1 && <p className={styles.movement}><ArrowDown size={12} aria-hidden="true" />{stop.movement || "다음 장소로 이동 · 이동 정보는 일정에 입력해 주세요"}</p>}
              </div>
            ))}
            {stops.length === 0 && <p className={styles.empty}>이 날짜에는 등록한 일정이 없어요.</p>}
          </div>
        </section>
        <section className={`${styles.pane} ${styles.mapPane}`} id="trip-pane-map" role="tabpanel" aria-labelledby="trip-map-heading" data-active={pane === "map"}>
          <div className={styles.panehead}><h2 id="trip-map-heading">지도</h2><span>{dayNumber}일차 · 방문 순서</span></div>
          <TripMap stops={stops} selectedId={selected?.id} dayNumber={dayNumber} onSelect={(stopId) => selectStop(stopId, false)} />
          <div className={styles.mapSelection}>
            {selected ? <>
              <p className={styles.eyebrow}>선택한 장소</p><h3>{selected.title}</h3>
              <p>{timeRange(selected)} · {selected.area}</p><p>{bookingLabels[selected.booking]}</p>
              <div className={styles.detailActions}><Button variant="secondary" onClick={() => showOnTimeline(selected.id)}>일정 상세 보기</Button><Button variant="secondary" disabled={message.isPending} onClick={() => askAbout(selected)}>채팅으로 질문</Button></div>
            </> : <p>일정을 등록하면 선택한 장소의 상세가 표시돼요.</p>}
          </div>
        </section>
        <section className={`${styles.pane} ${styles.chatPane}`} id="trip-pane-chat" role="tabpanel" aria-labelledby="trip-chat-heading" data-active={pane === "chat"}>
          <div className={styles.panehead}><h2 id="trip-chat-heading">여행 채팅</h2><span>이 여행의 모든 대화</span></div>
          <div ref={chatLog} className={styles.chatlog} role="log" aria-label="여행 대화 이력" aria-live="polite" aria-relevant="additions text" aria-busy={message.isPending}>
            <p className={styles.chatdate}>여행 전체 일차의 대화</p>
            <div className={styles.chatcontext}><strong>지금 보고 있는 {dayNumber}일차</strong><span>{activeDate} · {stops.length}개 일정</span>{selected && <span>선택: {selected.time} {selected.title}</span>}</div>
            {trip.messages.length === 0 && <ChatMessage message={{ id: "welcome", role: "assistant", text: `여행 계획을 등록했어요.\n\n${trip.startDate}부터 ${trip.endDate}까지 ${trip.stops.length}개의 일정이에요. 궁금한 일정이나 지켜야 할 조건을 아래 채팅창에 입력해 보세요.`, createdAt: "" }} />}
            {trip.messages.map((item) => <ChatMessage key={item.id} message={item} />)}
            {message.isPending && <><ChatMessage message={{ id: "pending", role: "user", text: message.variables.text, createdAt: "" }} /><p className={styles.pending} role="status"><span />답변을 준비하고 있어요…</p></>}
          </div>
          <div className={styles.composer}>
            <div className={styles.prompts}>
              <Button variant="quiet" disabled={message.isPending} onClick={() => ask(`${activeDate} 하루 일정 요약을 알려 주세요.`)}>하루 일정 요약</Button>
              <Button variant="quiet" disabled={!selected || message.isPending} onClick={() => selected && askAbout(selected)}>선택 일정 상세</Button>
              <Button variant="quiet" disabled={message.isPending} onClick={() => ask(`${activeDate} 예약 일정 확인을 해 주세요.`)}>예약 일정 확인</Button>
            </div>
            <form onSubmit={submit} className={styles.chatForm} noValidate>
              <label className={styles.srOnly} htmlFor="trip-chat-message">여행 메시지</label>
              <input id="trip-chat-message" ref={chatInput} value={draft} onChange={(event) => { setDraft(event.target.value); if (inputError) setInputError(""); }} maxLength={600} placeholder="궁금한 점이나 변경 요청을 입력" autoComplete="off" disabled={message.isPending} aria-invalid={Boolean(inputError)} aria-describedby={inputError ? "trip-chat-input-error" : undefined} />
              <Button type="submit" variant="primary" disabled={message.isPending} aria-label="메시지 전송"><Send size={16} aria-hidden="true" /><span className={styles.sendText}>전송</span></Button>
            </form>
            {inputError && <p id="trip-chat-input-error" className={styles.error} role="alert">{inputError}</p>}
            {message.isError && <div className={styles.error} role="alert"><p>메시지를 보내지 못했어요. {message.error.message}</p><Button variant="secondary" onClick={() => message.variables && message.mutate(message.variables)}>다시 보내기</Button></div>}
            <p className={styles.chatnote}>데모 응답 · 실제 에이전트 연결 전</p>
          </div>
        </section>
      </div>
      <footer className={styles.workspaceFooter}><span><ShieldCheck size={15} aria-hidden="true" />첫 검증 결과가 반영된 여행 계획이에요.</span><ButtonLink href={routes.results(trip.id)} variant="quiet">검증 결과 다시 보기<ChevronDown className={styles.resultArrow} size={14} aria-hidden="true" /></ButtonLink></footer>
    </div>
  );
}

function StopDetails({ stop, next }: { stop: TripStop; next?: TripStop }) {
  return <dl className={styles.details}>
    <dt>장소</dt><dd>{stop.title}</dd>
    <dt>날짜</dt><dd>{stop.date}</dd>
    <dt>예정 시간</dt><dd>{timeRange(stop)}</dd>
    <dt>위치</dt><dd>{stop.area}</dd>
    <dt>예약 상태</dt><dd>{bookingLabels[stop.booking]}</dd>
    {stop.originalTime && stop.originalTime !== stop.time && <><dt>변경 전</dt><dd>{stop.originalTime} → {stop.time}</dd></>}
    <dt>다음 일정</dt><dd>{next ? `${next.time} · ${next.title}` : "이날 마지막 일정"}</dd>
    <dt>안내</dt><dd>{stop.notes || "별도 메모가 없어요."}</dd>
  </dl>;
}

function ChatMessage({ message }: { message: TripMessage }) {
  return <article className={styles.message} data-role={message.role}>
    {message.role === "assistant" && <span className={styles.messageAvatar} aria-hidden="true"><MessageCircle size={14} /></span>}
    <div className={styles.messageBody}><p className={styles.messageMeta}>{message.role === "user" ? "나" : "triPilot"}</p><p className={styles.messageBubble}>{message.text}</p></div>
  </article>;
}
