"use client";

import { useEffect, useRef, useState, type FormEvent, type RefObject } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { LocateFixed, MessageCircle, Send, X } from "lucide-react";
import { tripGateway } from "@/lib/gateway";
import { undoChange, warmup } from "@/lib/live/extras";
import { LiveError } from "@/lib/live/client";
import { progressText, type OpProgress } from "@/lib/live/stream";
import { readConsents } from "@/features/consent/consent-store";
import { OptionalConsentPrompt } from "@/features/consent/optional-consent-prompt";
import { currentLocation, locationFailureText, type LocationFix } from "@/lib/location";
import { useSettings, useT } from "@/lib/settings";
import { LinkedText } from "./linked-text";
import { tripKey } from "./use-trip";
import { noticesKey, proposalsKey } from "./use-trip-extras";
import type { Trip, TripMessage, TripStop } from "./model";
import styles from "./trip-screen.module.css";

/**
 * `[2026-10-07]` The trip's conversation with the server (moved from the old trip screen, `trip-home.tsx`, unchanged in what it sends and shows): a message goes to the server's trip
 * consultation (`POST …/messages`, live progress), the plan is read again after it, a change made from chat can be undone while it is the latest, and a question that needs where
 * the customer is asks the browser only on that press (and the personal-location agreement first).
 */
export function useTripChat(trip: Trip, selectedId: string | null, onAsked: () => void) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");
  const [inputError, setInputError] = useState("");
  // The server answered but the plan did not re-read (Q-05): the reply is shown, and the plan is read again until it loads.
  const [rereading, setRereading] = useState(false);
  const [locating, setLocating] = useState(false);
  const [locationError, setLocationError] = useState("");
  // A question waiting for the customer's agreement to use their location (asked in place, see `askWithLocation`).
  const [locationQuestion, setLocationQuestion] = useState<string | null>(null);
  // What the server says it is doing with the message now (live progress stream); null until it says.
  const [progress, setProgress] = useState<OpProgress | null>(null);
  const message = useMutation({
    // ★Only a stop the customer actually picked goes to the server (`item_id`).
    mutationFn: async ({ text, itemId, location }: { text: string; clearDraft: boolean; itemId?: string | null; location?: LocationFix | null }) => {
      setProgress(null);
      try { return await tripGateway.sendMessage(trip.id, text, language, itemId, location, setProgress); }
      catch (error) {
        if (!(error instanceof LiveError) || error.code !== "reply_kept") throw error;
        setRereading(true);
        return { ...trip, messages: [...trip.messages, ...((error.detail as { sent?: TripMessage[] } | undefined)?.sent ?? [])] };
      }
    },
    onSuccess: (updated, variables) => {
      queryClient.setQueryData(tripKey(trip.id, language), updated);
      if (variables.clearDraft) setDraft("");
      // ★A message can open a choice (「알아봐 줘」 → 「선택이 필요해요」) or send a notice — read both again now, not at the next poll.
      void queryClient.invalidateQueries({ queryKey: proposalsKey(trip.id, language) });
      void queryClient.invalidateQueries({ queryKey: noticesKey(trip.id, language) });
    },
  });

  // ★Undo a change made from chat (user decision 2026-09-29). Same server call as the automatic-change undo; 409 = the plan moved on, nothing changed.
  const undo = useMutation({
    mutationFn: (version: number) => undoChange(trip.id, { baseVersion: version, toVersion: version - 1, requestId: `chat-undo:v${version}->v${version - 1}` }, language),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: tripKey(trip.id, language) });
      void queryClient.invalidateQueries({ queryKey: noticesKey(trip.id, language) });
    },
  });

  useEffect(() => {
    if (!rereading) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const again = async () => {
      try {
        await queryClient.refetchQueries({ queryKey: tripKey(trip.id, language) }, { throwOnError: true });
        if (!stopped) setRereading(false);
      } catch {
        if (!stopped) timer = setTimeout(again, 5_000);
      }
    };
    timer = setTimeout(again, 2_000);
    return () => { stopped = true; clearTimeout(timer); };
  }, [rereading, trip.id, language, queryClient]);

  // ★Wake the chat model as the trip opens, so the first question does not wait for it to load (~35 s cold). Best effort — a failed chat reports itself.
  useEffect(() => {
    warmup(language).catch(() => { /* the chat reports its own failure */ });
  }, [trip.id, language]);

  const pickedId = trip.stops.some((stop) => stop.id === selectedId) ? selectedId : null;

  function ask(text: string, clearDraft = false, itemId: string | null = pickedId, location: LocationFix | null = null) {
    if (message.isPending) return;
    const trimmed = text.trim();
    if (!trimmed) {
      setInputError(t("메시지를 입력해 주세요.", "Enter a message."));
      document.getElementById("trip-chat-message")?.focus();
      return;
    }
    setInputError("");
    setLocationError("");
    onAsked();
    message.mutate({ text: trimmed, clearDraft, itemId, location });
  }

  // ★The server said the answer needs where the customer is. The browser is asked only now, on this press (user decision 2026-09-30) — and only with the agreement to the location item.
  async function askWithLocation(question: string) {
    setLocationError("");
    if (!readConsents().location) { setLocationQuestion(question); return; }
    setLocationQuestion(null);
    setLocating(true);
    const result = await currentLocation();
    setLocating(false);
    if (!result.ok) { setLocationError(locationFailureText(result.reason, t)); return; }
    ask(question, false, undefined, result.fix);
  }

  const askAbout = (stop: TripStop) => ask(t(`${stop.date} ${stop.time} ${stop.title} 일정의 상세를 알려 주세요.`, `Tell me about the ${stop.title} stop on ${stop.date} at ${stop.time}.`), false, stop.id);

  return { draft, setDraft, inputError, setInputError, rereading, locating, locationError, locationQuestion, setLocationQuestion, progress, message, undo, ask, askWithLocation, askAbout };
}

export type TripChat = ReturnType<typeof useTripChat>;

/**
 * The chat pane of the sheet (mockup C안 「채팅」): the context of the question (the day and the stop picked) at the top of the conversation, the conversation, the quick questions and
 * what a message does. Typing is the chat bar's (`ChatBar`) — it stays at the bottom of the frame.
 */
export function ChatPane({ trip, chat, day, dayText, selected, logRef }: { trip: Trip; chat: TripChat; day: string; dayText: string; selected: TripStop | null; logRef: RefObject<HTMLDivElement | null> }) {
  const t = useT();
  const { message, undo } = chat;
  useEffect(() => {
    if (logRef.current) logRef.current.scrollTop = logRef.current.scrollHeight;
  }, [trip.messages.length, message.isPending, logRef]);
  return <>
    <div ref={logRef} className={styles.chatLog} role="log" aria-label={t("여행 대화 이력", "Travel conversation")} aria-live="polite" aria-relevant="additions text" aria-busy={message.isPending}>
      <div className={styles.chatContext}><strong>{dayText} · {day}</strong>
        <span>{selected ? t(`선택: ${selected.title}`, `Selected: ${selected.title}`) : t("선택한 일정이 없어요.", "No stop selected.")}</span></div>
      {trip.messages.length === 0 && <article className={styles.message} data-role="assistant"><p className={styles.messageMeta}>triPilot</p><p className={styles.bubble}>{t("등록한 일정에서 궁금한 내용을 골라 주세요. 하루 요약, 선택한 장소와 다음 일정을 함께 살펴볼 수 있어요.", "Explore your saved itinerary. Ask for a day summary, details of your selected stop, or what comes next.")}</p></article>}
      {trip.messages.map((item, index) => <article key={item.id} className={styles.message} data-role={item.role}><p className={styles.messageMeta}>{item.role === "user" ? t("나", "You") : "triPilot"}</p><p className={styles.bubble}>{item.role === "assistant" ? <LinkedText text={item.text} mapLabel={t("지도 앱으로 열기", "Open in maps app")} /> : item.text}</p>
        {item.more && <details className={styles.more}><summary>{t("더 보기", "More")}</summary><p><LinkedText text={item.more} mapLabel={t("지도 앱으로 열기", "Open in maps app")} /></p></details>}
        {item.basis && item.basis.length > 0 && <p className={styles.devBasis}>{t("개발 모드 · 근거 ", "Dev mode · basis ")}{item.basis.join(", ")}</p>}
        {/* ★A change made from chat can be undone while it is still the plan's latest version. */}
        {item.changedTo !== undefined && item.changedTo === trip.version && <div className={styles.choices}>
          <button type="button" className={styles.choice} disabled={undo.isPending} onClick={() => undo.mutate(item.changedTo as number)}>{undo.isPending ? t("되돌리는 중…", "Undoing…") : t("되돌리기", "Undo")}</button>
          <span className={styles.undoHint}>{t("바꾼 일정이 마음에 안 드시면 되돌릴 수 있어요.", "Not what you wanted? You can undo this change.")}</span></div>}
        {/* ★Only the latest answer's choices can be picked — an older question is no longer open. */}
        {item.choices && item.choices.length > 0 && index === trip.messages.length - 1 && <div className={styles.choices}>
          {item.choicesTitle && <span className={styles.choicesTitle}>{item.choicesTitle}</span>}{item.choices.map((choice) =>
          <button key={choice.message} type="button" className={styles.choice} disabled={message.isPending} onClick={() => chat.ask(choice.message)}>{choice.label}</button>)}</div>}
        {item.needsLocation && index === trip.messages.length - 1 && trip.messages[index - 1]?.role === "user" && <div className={styles.choices}>
          <button type="button" className={styles.choice} disabled={message.isPending || chat.locating} onClick={() => void chat.askWithLocation(trip.messages[index - 1].text)}><LocateFixed size={15} strokeWidth={1.6} aria-hidden="true" />{chat.locating ? t("위치 찾는 중…", "Finding your location…") : t("내 위치 알려 주고 다시 묻기", "Share my location and ask again")}</button>
          <span className={styles.undoHint}>{t("누르면 브라우저가 위치 권한을 물어요. 위치는 이 질문에 답하는 데 써요.", "Your browser will ask first. The location is used to answer this question.")}</span></div>}</article>)}
      {chat.locationQuestion !== null && <OptionalConsentPrompt code="location" why={t("내 위치로 답하려면 개인위치정보 수집·이용에 동의해야 해요.", "To answer from where you are, we need your agreement to the personal location item.")}
        onAgreed={() => void chat.askWithLocation(chat.locationQuestion!)} onCancel={() => chat.setLocationQuestion(null)} />}
      {chat.locationError && <p className={styles.error} role="alert">{chat.locationError}</p>}
      {undo.error && <p className={styles.error} role="alert">{undo.error instanceof LiveError && ["stale_itinerary", "stale", "invalid_version"].includes(undo.error.code)
        ? t("그 사이 일정이 다시 바뀌어 되돌리지 않았어요.", "The plan changed again meanwhile, so nothing was undone.") : undo.error.message}</p>}
      {undo.data && !undo.error && <p className={styles.chatNote} role="status">{undo.data.answer ?? t("바꾸기 전 일정으로 되돌렸어요.", "Your plan is back to how it was.")}</p>}
      {message.isPending && <>
        <article className={styles.message} data-role="user"><p className={styles.messageMeta}>{t("나", "You")}</p><p className={styles.bubble}>{message.variables.text}</p></article>
        <p className={styles.pending} role="status" data-lost={chat.progress?.lost || undefined}>{progressText(chat.progress, t, ["답변을 준비하고 있어요…", "Preparing a reply…"])}</p>
      </>}
      {chat.rereading && !message.isPending && <p className={styles.chatNote} role="status">{t("답은 받았어요. 최신 일정을 다시 불러오지 못해 잠시 뒤 다시 읽고 있어요.", "The reply arrived. The latest plan did not load, so it is being read again shortly.")}</p>}
      {message.isError && <div className={styles.error} role="alert"><p>{t("메시지를 보내지 못했어요.", "The message could not be sent.")} {message.error.message}</p><button type="button" className={styles.choice} onClick={() => message.variables && message.mutate(message.variables)}>{t("다시 보내기", "Send again")}</button></div>}
    </div>
    <div className={styles.prompts}>
      <button type="button" className={styles.prompt} disabled={message.isPending} onClick={() => chat.ask(t(`${day} 하루 일정을 요약해 주세요.`, `Summarize the itinerary for ${day}.`))}>{t("하루 요약", "Day summary")}</button>
      <button type="button" className={styles.prompt} disabled={!selected || message.isPending} onClick={() => selected && chat.askAbout(selected)}>{t("선택 일정", "Selected stop")}</button>
      <button type="button" className={styles.prompt} disabled={!selected || message.isPending} onClick={() => selected && chat.ask(t(`${selected.date} ${selected.time} ${selected.title} 다음 일정을 알려 주세요.`, `What comes after ${selected.title} on ${selected.date} at ${selected.time}?`))}>{t("다음 일정", "Next stop")}</button>
      <button type="button" className={styles.prompt} disabled={message.isPending} onClick={() => chat.ask(t(`${day} 예약 표시를 알려 주세요.`, `Show booking notes for ${day}.`))}>{t("예약 표시", "Booking notes")}</button>
    </div>
    <p className={styles.chatNote}>{t("보낸 문장은 여행 상담으로 접수돼요. 일정을 바꾸면 여행계획서에 새 버전이 생기고, 예약이 걸린 일정은 바꾸기 전에 물어봐요.", "Messages are filed as trip requests. Changes create a new version of your plan, and booked stops are never changed without asking.")}</p>
  </>;
}

/**
 * `[2026-10-07 사용자 결정 — 목업 C안]` The chat bar at the bottom of the frame. Closed: a round chat button. Pressed: it grows into the bar WITHOUT focusing the field (no phone keyboard);
 * the keyboard focus goes to its close button. Pressing the field (or tabbing into it) takes the sheet to the chat pane and the message is written there. In the chat pane it stays open.
 */
export function ChatBar({ chat, open, inChat, onOpen, onClose, onEnterChat }: { chat: TripChat; open: boolean; inChat: boolean; onOpen: () => void; onClose: () => void; onEnterChat: () => void }) {
  const t = useT();
  const closeButton = useRef<HTMLButtonElement>(null);
  const fab = useRef<HTMLButtonElement>(null);
  const shown = open || inChat;
  const wasShown = useRef(shown);
  const backToFab = useRef(false);
  // The keyboard focus follows the bar: to its close button when it opens from the round button (which is gone), back to the round button when its close button shut it.
  useEffect(() => {
    if (shown && !wasShown.current && !inChat && document.activeElement === document.body) closeButton.current?.focus({ preventScroll: true });
    if (!shown && backToFab.current) { backToFab.current = false; fab.current?.focus({ preventScroll: true }); }
    wasShown.current = shown;
  }, [shown, inChat]);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    chat.ask(chat.draft, true);
  }
  if (!shown) {
    return <div className={styles.chatBar}><button ref={fab} type="button" className={styles.chatFab} onClick={onOpen} aria-label={t("채팅 입력 열기", "Open the chat")}><MessageCircle size={26} strokeWidth={1.7} aria-hidden="true" /></button></div>;
  }
  return <div className={styles.chatBar} data-open>
    {!inChat && <button ref={closeButton} type="button" className={styles.chatClose} onClick={() => { backToFab.current = true; onClose(); }} aria-label={t("채팅 막대 접기", "Close the chat bar")}><X size={18} strokeWidth={1.8} aria-hidden="true" /></button>}
    <form className={styles.chatForm} onSubmit={submit} noValidate>
      <label className="sr-only" htmlFor="trip-chat-message">{t("여행 메시지", "Travel message")}</label>
      <input id="trip-chat-message" className={styles.chatInput} value={chat.draft} maxLength={600} autoComplete="off" placeholder={t("일정에 대해 궁금한 점을 입력하세요", "Ask about your itinerary")} disabled={chat.message.isPending}
        aria-invalid={Boolean(chat.inputError)} aria-describedby={chat.inputError ? "trip-chat-error" : undefined}
        onFocus={() => { if (!inChat) onEnterChat(); }}
        onChange={(event) => { chat.setDraft(event.target.value); if (chat.inputError) chat.setInputError(""); }} />
      <button type="submit" className={styles.chatSend} disabled={chat.message.isPending} aria-label={t("메시지 전송", "Send message")}><Send size={18} strokeWidth={1.8} aria-hidden="true" /></button>
    </form>
    {chat.inputError && <p id="trip-chat-error" className={styles.chatError} role="alert">{chat.inputError}</p>}
  </div>;
}
