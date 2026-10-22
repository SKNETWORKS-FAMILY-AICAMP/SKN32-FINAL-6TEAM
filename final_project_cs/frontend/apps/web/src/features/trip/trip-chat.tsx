"use client";

import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode, type RefObject } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, CalendarDays, Check, ChevronDown, ChevronRight, CircleAlert, Clock, CloudRain, LoaderCircle, LocateFixed, MapPin, MapPinned, MessageCircle, Navigation, Pencil, Search, Send, Sparkles, Ticket, Undo2, X } from "lucide-react";
import { tripGateway } from "@/lib/gateway";
import { undoChange, warmup } from "@/lib/live/extras";
import { LiveError } from "@/lib/live/client";
import { progressText, stageText, type OpProgress } from "@/lib/live/stream";
import { readConsents, useConsent } from "@/features/consent/consent-store";
import { OptionalConsentPrompt } from "@/features/consent/optional-consent-prompt";
import { kindLook } from "@/features/plan-check/stop-kind";
import { BrandIcon } from "@/components/ui/brand";
import { currentLocation, locationFailureText, type LocationFix } from "@/lib/location";
import { useSettings, useT } from "@/lib/settings";
import type { Translate } from "@/lib/i18n";
import { LinkedText } from "./linked-text";
import { useChatFollow } from "./use-chat-follow";
import { useSlide } from "./use-slide";
import { tripKey } from "./use-trip";
import { noticesKey, proposalsKey, useNotices, useProposals } from "./use-trip-extras";
import { chatRecords, proposalAvailable } from "./trip-chat-records";
import { ChatNotice, ChatProposalChoices } from "./trip-chat-notices";
import { openChoices } from "./attention";
import { ownChange } from "./own-changes";
import { answerCard, answerLook, coveredLines, shownText, type AnswerCard, type AnswerLook } from "./chat-cards";
import { diffStops, keepDiff, readDiffs, type ChatDiff } from "./chat-diff";
import { placeLinks, placeTarget, type MapTarget } from "./map-apps";
import { visitHours } from "./trip-rows";
import type { SeoulNow } from "./trip-timeline";
import type { Trip, TripMessage, TripPick, TripStop } from "./model";
import styles from "./trip-screen.module.css";
import c from "./trip-chat.module.css";

/**
 * `[2026-10-07]` The trip's conversation with the server (moved from the old trip screen, `trip-home.tsx`, unchanged in what it sends and shows): a message goes to the server's trip
 * consultation (`POST …/messages`, live progress), the plan is read again after it, a change made from chat can be undone while it is the latest, and a question that needs where
 * the customer is asks the browser only on that press (and the personal-location agreement first).
 * `[2026-10-22 ST4F-719]` It also keeps what the answer cards need: the stages passed while waiting, and what a change changed (the plan just before sending against the plan read after).
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
  const locationAgreed = useConsent("location");
  const locationGeneration = useRef(0);
  const locationAttempt = useRef(0);
  const live = useRef(true);
  useEffect(() => {
    live.current = true;
    return () => { live.current = false; locationGeneration.current += 1; };
  }, []);
  useEffect(() => {
    if (!locationAgreed) locationGeneration.current += 1;
  }, [locationAgreed]);
  const [locationError, setLocationError] = useState("");
  // A question waiting for the customer's agreement to use their location (asked in place, see `askWithLocation`).
  const [locationQuestion, setLocationQuestion] = useState<string | null>(null);
  // What the server says it is doing with the message now (live progress stream); null until it says.
  const [progress, setProgress] = useState<OpProgress | null>(null);
  // `[2026-10-22 ST4F-719]` The stages it said so far for this message, in order (the waiting card lists them).
  const [stages, setStages] = useState<string[]>([]);
  const [kept, setKept] = useState(() => ({ tripId: trip.id, diffs: readDiffs(trip.id) }));
  const diffs: Record<string, ChatDiff> = kept.tripId === trip.id ? kept.diffs : readDiffs(trip.id);
  const onProgress = (state: OpProgress) => {
    setProgress(state);
    if (state.stage) setStages((seen) => (seen.includes(state.stage!) ? seen : [...seen, state.stage!]));
  };
  const message = useMutation({
    // Keep the cache entry that belongs to the account which sent this message.
    // A logout removes it; a new entry with the same trip key belongs to a later session.
    onMutate: () => ({ query: queryClient.getQueryCache().find({ queryKey: tripKey(trip.id, language), exact: true }),
      before: (queryClient.getQueryData<Trip>(tripKey(trip.id, language)) ?? trip).stops }),
    // ★Only a stop the customer actually picked goes to the server (`item_id`).
    mutationFn: async ({ text, itemId, location, summaryDay, focusId }: { text: string; clearDraft: boolean; itemId?: string | null; location?: LocationFix | null; summaryDay?: string; focusId?: string | null }) => {
      setProgress(null);
      setStages([]);
      try { return { updated: await tripGateway.sendMessage(trip.id, text, language, itemId, location, onProgress, undefined, summaryDay, focusId), sent: null }; }
      catch (error) {
        if (!(error instanceof LiveError) || error.code !== "reply_kept") throw error;
        setRereading(true);
        return { updated: null, sent: (error.detail as { sent?: TripMessage[] } | undefined)?.sent ?? [] };
      }
    },
    onSuccess: (result, variables, context) => {
      if (!context?.query || queryClient.getQueryCache().find({ queryKey: tripKey(trip.id, language), exact: true }) !== context.query) return;
      // SSE can refresh the plan before this response reaches the mutation.
      // Keep a newer itinerary and append only replies not already in its messages.
      let updated = result.updated;
      const current = queryClient.getQueryData<Trip>(tripKey(trip.id, language)) ?? trip;
      const older = updated && typeof updated.version === "number" && typeof current.version === "number" && updated.version < current.version;
      // `[2026-10-22 ST4F-719]` A change from this message: what it changed, before → after, kept by the version it made (the card under the answer reads it).
      const changed = [...(result.updated?.messages ?? result.sent ?? [])].reverse().find((item) => item.role === "assistant")?.changedTo;
      const diff = changed !== undefined && result.updated ? diffStops(context.before, result.updated.stops) : null;
      if (changed !== undefined && diff) { keepDiff(trip.id, changed, diff); setKept((was) => ({ tripId: trip.id, diffs: { ...(was.tripId === trip.id ? was.diffs : readDiffs(trip.id)), [String(changed)]: diff } })); }
      if (!updated || older) {
        const seen = new Set(current.messages.map(item => item.id));
        const appended = (updated?.messages ?? result.sent ?? []).filter(item => { if (seen.has(item.id)) return false; seen.add(item.id); return true; });
        updated = { ...current, messages: [...current.messages, ...appended] };
      }
      queryClient.setQueryData(tripKey(trip.id, language), updated);
      if (variables.clearDraft) setDraft("");
      // ★A message can open a choice (「알아봐 줘」 → 「선택이 필요해요」) or send a notice — read both again now, not at the next poll.
      void queryClient.invalidateQueries({ queryKey: proposalsKey(trip.id, language) });
      void queryClient.invalidateQueries({ queryKey: noticesKey(trip.id, language) });
    },
  });

  // ★Undo a change made from chat (user decision 2026-09-29). Same server call as the automatic-change undo; 409 = the plan moved on, nothing changed.
  const undo = useMutation({
    mutationFn: (version: number) => ownChange(trip.id, version, () => undoChange(trip.id, { baseVersion: version, toVersion: version - 1, requestId: `chat-undo:v${version}->v${version - 1}` }, language)),
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

  function ask(text: string, clearDraft = false, itemId: string | null = pickedId, location: LocationFix | null = null, summaryDay?: string, focusId?: string | null) {
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
    message.mutate({ text: trimmed, clearDraft, itemId, location, summaryDay, focusId });
  }

  // ★The server said the answer needs where the customer is. The browser is asked only now, on this press (user decision 2026-09-30) — and only with the agreement to the location item.
  async function askWithLocation(question: string) {
    if (!live.current || message.isPending) return;
    setLocationError("");
    if (!readConsents().location) { setLocationQuestion(question); return; }
    setLocationQuestion(null);
    const attempt = ++locationGeneration.current;
    locationAttempt.current = attempt;
    setLocating(true);
    const result = await currentLocation();
    // A delayed GPS answer must not submit a question after withdrawal, a newer
    // attempt, or leaving this trip. A withdrawn then renewed consent is a new attempt too.
    if (!live.current || attempt !== locationAttempt.current) return;
    setLocating(false);
    if (attempt !== locationGeneration.current || !readConsents().location) return;
    if (!result.ok) { setLocationError(locationFailureText(result.reason, t)); return; }
    ask(question, false, undefined, result.fix);
  }

  const askAbout = (stop: TripStop) => ask(t(`${stop.date} ${stop.time} ${stop.title} 일정의 상세를 알려 주세요.`, `Tell me about the ${stop.title} stop on ${stop.date} at ${stop.time}.`), false, stop.id, null, undefined, stop.id);

  return { draft, setDraft, inputError, setInputError, rereading, locating: locating && locationAgreed, locationError, locationQuestion, setLocationQuestion, progress, stages, diffs, message, undo, ask, askWithLocation, askAbout };
}

export type TripChat = ReturnType<typeof useTripChat>;

/** The stop after `stop` in the plan (by day and time, as the server's 「다음 일정」 answer reads it). */
function nextStop(stops: readonly TripStop[], stop: TripStop): TripStop | null {
  const ordered = [...stops].sort((a, b) => `${a.date}T${a.time}`.localeCompare(`${b.date}T${b.time}`));
  return ordered[ordered.indexOf(stop) + 1] ?? null;
}

const hhmm = (minute: number) => `${String(Math.floor(minute / 60)).padStart(2, "0")}:${String(minute % 60).padStart(2, "0")}`;
const mapLabels = (t: Translate) => ({ mapLabel: t("지도 앱으로 열기", "Open in maps app"), siteLabel: (site: string) => t(`${site}에서 열기`, `Open on ${site}`) });

/**
 * The chat pane of the sheet (mockup C안 「채팅」): the conversation, the chips that follow the situation and what a message does. Typing is the chat bar's (`ChatBar`) — it stays at the
 * bottom of the frame.
 * `[2026-10-22 사용자 결정 — ST4F-719 · 목업 ② + ⓑ]` Each answer is a card: a heading badge, the server's text (without the lines its card shows), a card of what it is about (the stop · the day ·
 * what a change changed) and, under it, what can be done next (the server's choices · 직접 고르기 · 더 보기 · 진행 과정). The context box at the top went into the chips' caption.
 */
export function ChatPane({ trip, chat, day, dayText, dayHeading, now, selected, logRef, active, onPick, onDetail, onMapApps }: { trip: Trip; chat: TripChat; day: string; dayText: string;
  /** 「1일차 10.01 목」 for a day's summary card. */
  dayHeading: (date: string) => string; now: SeoulNow; selected: TripStop | null; logRef: RefObject<HTMLDivElement | null>; active: boolean;
  /** `[2026-10-19 사용자 결정]` 「직접 고르기」 under an answer that could not find the place: the screen turns into the edit, as 「일정 수정」 does (`TripPick`). */
  onPick?: (pick: TripPick) => void;
  /** `[2026-10-22 사용자 결정]` A card's 「상세 보기」: that stop's detail; ← comes back to the chat where it was. */
  onDetail: (id: string) => void; onMapApps: (target: MapTarget) => void }) {
  const t = useT();
  const { message, undo } = chat;
  const notices = useNotices(trip.id);
  const proposals = useProposals(trip.id);
  const records = chatRecords(trip.messages, notices.data ?? []);
  const latest = useChatFollow(logRef, active, `${records.length}:${records.at(-1)?.id ?? ""}`, message.isPending);
  const last = trip.messages.length - 1;
  const latestAnswer = !message.isPending && trip.messages[last]?.role === "assistant" ? trip.messages[last] : null;
  const openProposal = openChoices(proposals.data ?? [], notices.data ?? [], trip.stops).find((choice) => choice.stop && proposalAvailable(choice.proposal, trip.version)) ?? null;
  return <>
    <div ref={logRef} className={styles.chatLog} tabIndex={0} onScroll={latest.onScroll} role="log" aria-label={t("여행 대화 이력", "Travel conversation")} aria-live="polite" aria-relevant="additions text" aria-busy={message.isPending}>
      {trip.messages.length === 0 && <div className={c.card}><div className={c.head}><Speaker /></div>
        <p className={c.body}>{t("등록한 일정에서 궁금한 내용을 골라 주세요. 하루 요약, 선택한 장소와 다음 일정을 함께 살펴볼 수 있어요.", "Explore your saved itinerary. Ask for a day summary, details of your selected stop, or what comes next.")}</p></div>}
      {records.map(record => {
        // `[2026-10-22 ST4F-723 c]` A proposal's notice under which its card (`ChatProposalChoices`) draws the options: their numbered list and warnings are left out of the sentence.
        if (record.kind === "notice") return <ChatNotice key={record.id} notice={record.notice}
          cover={(proposals.data ?? []).find((proposal) => proposal.status === "open" && proposal.id === record.notice.proposalId)?.options} />;
        const { message: item, index } = record;
        if (item.role === "user") return <p key={record.id} className={c.user} data-chat-user>{item.text}</p>;
        return <Answer key={record.id} trip={trip} chat={chat} item={item} latest={index === last} previous={trip.messages[index - 1]} dayHeading={dayHeading}
          onPick={onPick} onDetail={onDetail} onMapApps={onMapApps} />;
      })}
      {notices.error && <p className={`${c.status} ${c.statusError}`} role="alert">{t("여행 알림을 읽지 못했어요.", "Travel notices could not be loaded.")}
        <button type="button" className={c.chip} onClick={() => void notices.refetch()}>{t("알림 다시 읽기", "Reload notices")}</button></p>}
      <ChatProposalChoices key={trip.id} trip={trip} notices={notices.data ?? []} />
      {chat.locationQuestion !== null && <OptionalConsentPrompt code="location" why={t("내 위치로 답하려면 개인위치정보 수집·이용에 동의해야 해요.", "To answer from where you are, we need your agreement to the personal location item.")}
        onAgreed={() => void chat.askWithLocation(chat.locationQuestion!)} onCancel={() => chat.setLocationQuestion(null)} />}
      {chat.locationError && <p className={`${c.status} ${c.statusError}`} role="alert">{chat.locationError}</p>}
      {undo.error && <p className={`${c.status} ${c.statusError}`} role="alert">{undo.error instanceof LiveError && ["stale_itinerary", "stale", "invalid_version"].includes(undo.error.code)
        ? t("그 사이 일정이 다시 바뀌어 되돌리지 않았어요.", "The plan changed again meanwhile, so nothing was undone.") : undo.error.message}</p>}
      {undo.data && !undo.error && <p className={c.status} role="status">{undo.data.notice?.text ?? undo.data.answer ?? t("바꾸기 전 일정으로 되돌렸어요.", "Your plan is back to how it was.")}</p>}
      {message.isPending && <>
        <p className={c.user} data-chat-user>{message.variables.text}</p>
        <div className={c.card} data-chat-pending><div className={c.head}><Speaker /><span className={c.badge} role={chat.stages.length || chat.progress?.lost ? undefined : "status"}><LoaderCircle size={13} strokeWidth={2.2} aria-hidden="true" />{t("답변을 준비하고 있어요…", "Preparing a reply…")}</span></div>
          {/* The stages passed so far — the last one now, with its seconds (before the server names one, the badge says it is waiting). */}
          {(chat.stages.length > 0 || chat.progress?.lost) && <div className={c.pending}><ol className={c.stepList}>
            {chat.stages.slice(0, -1).map((stage) => <li key={stage}><Check size={14} strokeWidth={2.2} aria-hidden="true" />{stageText(stage, t)}</li>)}
            <li data-active role="status" data-lost={chat.progress?.lost || undefined}><LoaderCircle size={14} strokeWidth={2.2} aria-hidden="true" />{progressText(chat.progress, t, ["답변을 준비하고 있어요…", "Preparing a reply…"])}</li>
          </ol></div>}</div>
      </>}
      {chat.rereading && !message.isPending && <p className={c.status} role="status">{t("답은 받았어요. 최신 일정을 다시 불러오지 못해 잠시 뒤 다시 읽고 있어요.", "The reply arrived. The latest plan did not load, so it is being read again shortly.")}</p>}
      {message.isError && <>
        <p className={c.user} data-chat-user>{message.variables?.text}</p>
        <div className={`${c.card} ${c.error}`} role="alert"><div className={c.head}><span className={c.badge} data-tone="error"><CircleAlert size={13} strokeWidth={2.2} aria-hidden="true" />{t("메시지를 보내지 못했어요.", "The message could not be sent.")}</span></div>
          <p className={c.body}>{message.error.message}</p>
          <div className={c.foot}><button type="button" className={c.button} data-primary onClick={() => message.variables && message.mutate(message.variables)}>{t("다시 보내기", "Send again")}</button></div></div>
      </>}
    </div>
    <div className={c.dock}>
      {latest.away && <button type="button" className={`${styles.chatLatest} ${c.latest}`} onClick={() => { latest.jump(); logRef.current?.focus({ preventScroll: true }); }}>{latest.unread ? t("새 메시지 · 최신 대화로 이동", "New messages · Jump to latest") : t("최신 대화로 이동", "Jump to latest")}</button>}
      <ChatChips trip={trip} chat={chat} day={day} dayText={dayText} now={now} selected={selected} latestAnswer={latestAnswer} previous={trip.messages[last - 1]}
        proposal={openProposal ? { id: openProposal.proposal.id, title: openProposal.stop!.title, forecast: openProposal.proposal.reason === "forecast_advisory" } : null}
        onProposal={(id) => document.querySelector(`[data-chat-proposal="${CSS.escape(id)}"]`)?.scrollIntoView({ block: "center", behavior: "smooth" })} />
    </div>
  </>;
}

function Speaker() {
  const t = useT();
  return <><span className={c.avatar}><BrandIcon size={22} /></span><b className={c.name}>{t("구구루트", "GuguRoute")}</b></>;
}

/** The answer's heading badge: what the server did with the message. */
function Badge({ look }: { look: AnswerLook }) {
  const t = useT();
  const [Icon, label] = {
    pick: [Search, t("장소를 찾지 못했어요", "Place not found")],
    location: [LocateFixed, t("위치가 필요해요", "Location needed")],
    waiting: [Clock, t("답을 기다려요", "Waiting for you")],
    undone: [Undo2, t("되돌렸어요", "Undone")],
    changed: [Check, t("일정을 바꿨어요", "Plan changed")],
    kept: [Check, t("바꾸지 않았어요", "Not changed")],
    answer: [Sparkles, t("답변", "Answer")],
  }[look.kind] as [typeof Check, string];
  return <span className={c.badge} data-tone={look.tone}><Icon size={13} strokeWidth={2.2} aria-hidden="true" />{label}</span>;
}

/** One answer of the server, as a card. Only the latest answer's choices, 직접 고르기 and waiting line are live — an older question is no longer open. */
function Answer({ trip, chat, item, latest, previous, dayHeading, onPick, onDetail, onMapApps }: { trip: Trip; chat: TripChat; item: TripMessage; latest: boolean; previous?: TripMessage;
  dayHeading: (date: string) => string; onPick?: (pick: TripPick) => void; onDetail: (id: string) => void; onMapApps: (target: MapTarget) => void }) {
  const t = useT();
  const { message, undo } = chat;
  // ★A change made from chat can be undone while it is still the plan's latest version.
  const undoable = item.changedTo !== undefined && item.changedTo === trip.version;
  const undone = item.changedTo !== undefined && undo.isSuccess && undo.variables === item.changedTo;
  const look = answerLook(item, undone);
  const card = answerCard(item, trip, chat.diffs);
  const text = shownText(item.text, coveredLines(card), undoable);
  const waiting = item.awaitingReply && latest;
  const choices = item.choices && item.choices.length > 0 && latest;
  const pick = item.pick && onPick && latest;
  return <article className={c.card} data-role="assistant" data-chat-answer data-card={card?.kind}>
    <div className={c.head}><Speaker />{look && <Badge look={look} />}</div>
    {text && <p className={c.body}><LinkedText text={text} {...mapLabels(t)} /></p>}
    {card?.kind === "place" && <PlaceCard stop={card.stop} onDetail={onDetail} onMapApps={onMapApps} />}
    {card?.kind === "day" && <DayCard card={card} heading={dayHeading(card.date)} />}
    {card?.kind === "diff" && <div className={c.diff}><h3>{t("바뀐 일정", "What changed")}</h3>
      {card.diff.rows.map((row) => <div key={row.id} className={c.row} data-diff-row={row.kind}><span><s>{row.before}</s><br /><span className={c.new}>{row.after}</span></span><span>{row.title}</span></div>)}
      {card.diff.keep.map((keep) => <div key={keep.id} className={c.row} data-keep><span>{keep.time}</span><span>{keep.title}<span className={c.keepTag}>{t("그대로", "Unchanged")}</span></span></div>)}
      {undoable && <div className={c.acts}><UndoButton chat={chat} version={item.changedTo!} />
        {trip.stops.some((stop) => stop.id === card.diff.rows[0].id) && <button type="button" className={c.button} onClick={() => onDetail(card.diff.rows[0].id)}
          aria-label={t(`${card.diff.rows[0].title} 상세 보기`, `Details of ${card.diff.rows[0].title}`)}>{t("상세 보기", "Details")}<ChevronRight size={15} strokeWidth={1.8} aria-hidden="true" /></button>}</div>}
      {undoable && <p className={c.hint}>{t("바꾼 일정이 마음에 안 드시면 되돌릴 수 있어요.", "Not what you wanted? You can undo this change.")}</p>}</div>}
    {undoable && card?.kind !== "diff" && <div className={c.foot}><UndoButton chat={chat} version={item.changedTo!} />
      <span className={c.footTitle}>{t("바꾼 일정이 마음에 안 드시면 되돌릴 수 있어요.", "Not what you wanted? You can undo this change.")}</span></div>}
    {(waiting || choices || pick) && <div className={c.foot}>
      {waiting && <span className={c.footTitle}>{t("답변을 기다리고 있어요. 아래에 답하시면 같은 요청을 이어서 처리해요.", "Waiting for your reply. Answer below to continue this request.")}</span>}
      {/* `[2026-10-22 사용자 결정]` The server's choices stay under the answer, each a whole sentence that wraps — in the chip row they were cut off. */}
      {choices && <>{item.choicesTitle && <span className={c.footTitle}>{item.choicesTitle}</span>}{item.choices!.map((choice) =>
        <button key={choice.message} type="button" className={c.chip} data-wrap disabled={message.isPending} onClick={() => chat.ask(choice.message, false, choice.itemId ?? null)}>{choice.label}</button>)}</>}
      {/* `[2026-10-19 사용자 결정 — 못 찾은 장소는 직접 고르기로]` The edit opens on that stop (or on the add form, filled in). */}
      {pick && <>
        <button type="button" className={c.button} data-primary data-pick={item.pick!.mode} disabled={message.isPending} onClick={() => onPick!(item.pick!)}><Pencil size={15} strokeWidth={1.8} aria-hidden="true" />{t("직접 고르기", "Choose myself")}</button>
        <span className={c.footTitle}>{item.pick!.mode === "add"
          ? t("수정 화면의 일정 추가 칸에서 장소를 찾아 넣어요.", "Find the place in the edit's add form.")
          : t("수정 화면에서 이 일정의 장소를 직접 골라요.", "Pick this stop's place yourself in the edit.")}</span></>}
    </div>}
    {item.more && <details className={c.more}><summary>{t("더 보기", "More")}<ChevronDown size={15} strokeWidth={1.8} aria-hidden="true" /></summary><div><LinkedText text={item.more} {...mapLabels(t)} /></div></details>}
    {item.steps && item.steps.length > 0 && <details className={c.steps}><summary><Check size={13} strokeWidth={2.2} aria-hidden="true" />{t(`진행 과정 · ${item.steps.length}단계 · ${item.secs ?? 1}초`, `Progress · ${item.steps.length} steps · ${item.secs ?? 1} s`)}<ChevronDown size={14} strokeWidth={1.8} aria-hidden="true" /></summary>
      <ol className={c.stepList}>{item.steps.map((stage) => <li key={stage}><Check size={14} strokeWidth={2.2} aria-hidden="true" />{stageText(stage, t)}</li>)}</ol></details>}
    {item.basis && item.basis.length > 0 && <p className={c.devBasis}>{t("개발 모드 · 근거 ", "Dev mode · basis ")}{item.basis.join(", ")}</p>}
    {/* A question that needs where the customer is: the button is the chips' (`ChatChips`), the browser asks only on that press. */}
    {item.needsLocation && latest && previous?.role === "user" && <div className={c.foot}><span className={c.footTitle}>{t("누르면 브라우저가 위치 권한을 물어요. 위치는 이 질문에 답하는 데 써요.", "Your browser will ask first. The location is used to answer this question.")}</span></div>}
  </article>;
}

function UndoButton({ chat, version }: { chat: TripChat; version: number }) {
  const t = useT();
  return <button type="button" className={c.button} disabled={chat.undo.isPending} onClick={() => chat.undo.mutate(version)}><Undo2 size={15} strokeWidth={1.8} aria-hidden="true" />{chat.undo.isPending ? t("되돌리는 중…", "Undoing…") : t("되돌리기", "Undo")}</button>;
}

/** The stop an answer is about, drawn from what the trip has (`placeInfo` · `mapUrl`): its kind, the hours of the visit day, the address, the map apps and its detail. */
function PlaceCard({ stop, onDetail, onMapApps }: { stop: TripStop; onDetail: (id: string) => void; onMapApps: (target: MapTarget) => void }) {
  const t = useT();
  const kind = kindLook(stop.kind);
  const KindIcon = kind.icon;
  const hours = visitHours(stop);
  const maps = placeLinks(stop);
  return <div className={c.place} data-place-card={stop.id}>
    <span className={c.placeIcon} role="img" aria-label={stop.kindLabel ?? t(kind.label[0], kind.label[1])}><KindIcon size={19} strokeWidth={1.8} aria-hidden="true" /></span>
    <b>{stop.place ?? stop.title}</b>
    <span>{stop.kindLabel ?? t(kind.label[0], kind.label[1])} · {hours ? <em>{hours}</em> : t("영업시간 정보 없음", "Hours not known")}</span>
    <span>{stop.placeInfo?.address ?? t("주소 정보 없음", "Address not known")}</span>
    <div className={c.acts}>
      {maps && <button type="button" className={c.button} aria-haspopup="dialog" onClick={() => onMapApps(placeTarget(stop, maps))}><MapPinned size={15} strokeWidth={1.8} aria-hidden="true" />{t("지도 앱으로 열기", "Open in maps app")}</button>}
      <button type="button" className={c.button} onClick={() => onDetail(stop.id)} aria-label={t(`${stop.title} 상세 보기`, `Details of ${stop.title}`)}>{t("상세 보기", "Details")}<ChevronRight size={15} strokeWidth={1.8} aria-hidden="true" /></button>
    </div>
  </div>;
}

/** A day's summary as a small timeline (with the moves between, as the plan has them). */
function DayCard({ card, heading }: { card: Extract<AnswerCard, { kind: "day" }>; heading: string }) {
  const t = useT();
  return <div className={c.day}><h3>{heading}</h3><ol className={c.timeline}>
    {card.stops.map((stop) => <li key={stop.id}><time>{stop.time}</time><span className={c.dot} /><span>{stop.title} <small>{stop.endTime ? `~${stop.endTime} · ` : ""}{stop.kindLabel ?? t(kindLook(stop.kind).label[0], kindLook(stop.kind).label[1])}</small></span></li>)}
  </ol></div>;
}

/**
 * `[2026-10-22 사용자 결정 — ST4F-719 · 목업 ②]` The chips above the bar follow the situation, in one row that slides sideways (`useSlide`, `data-no-swipe` — the pane's own swipe back to the plan
 * does not start on it). Its caption says what they are about. First what the latest answer waits for (quick answers the screen made for 「몇 분」 — dashed, gone once used; 「내 위치 알려 주고 다시
 * 묻기」), else the stop picked (선택 일정 · 다음 일정 · 가는 길), else now (지금 다음 일정); a choice the server waits for (예보 주의 …) leads; 하루 요약 · 예약 표시 always follow. The server's own
 * choices are not here — they stay under the answer. Hidden while a message is being written.
 */
function ChatChips({ trip, chat, day, dayText, now, selected, latestAnswer, previous, proposal, onProposal }: { trip: Trip; chat: TripChat; day: string; dayText: string; now: SeoulNow;
  selected: TripStop | null; latestAnswer: TripMessage | null; previous?: TripMessage; proposal: { id: string; title: string; forecast: boolean } | null; onProposal: (id: string) => void }) {
  const t = useT();
  const { message } = chat;
  const busy = message.isPending;
  const askDetail = () => selected && chat.askAbout(selected);
  const askNext = () => selected && chat.ask(t(`${selected.date} ${selected.time} ${selected.title} 다음 일정을 알려 주세요.`, `What comes after ${selected.title} on ${selected.date} at ${selected.time}?`),
    false, undefined, null, undefined, nextStop(trip.stops, selected)?.id ?? null);
  const chip = (key: string, Icon: typeof Check, label: string, onClick: () => void, extra: Record<string, unknown> = {}) =>
    <button key={key} type="button" className={c.chip} disabled={busy} onClick={onClick} {...extra}><Icon size={15} strokeWidth={1.8} aria-hidden="true" /><span>{label}</span></button>;
  const items: ReactNode[] = [];
  let caption: [typeof Check, string];
  let about = false;
  if (proposal) items.push(chip("proposal", CloudRain, `${proposal.title} · ${proposal.forecast ? t("예보 주의", "Forecast") : t("선택이 필요해요", "Your choice is needed")}`, () => onProposal(proposal.id), { "data-risk": "" }), <span key="sep0" className={c.sep} />);
  if (latestAnswer?.awaitingReply && latestAnswer.minutes) {
    caption = [Clock, t("답하기", "Reply")];
    for (const [ko, en] of [["15분이요", "15 minutes"], ["30분이요", "30 minutes"], ["1시간이요", "An hour"]]) items.push(<button key={ko} type="button" className={c.chip} data-made disabled={busy} onClick={() => chat.ask(t(ko, en))}>{t(ko, en)}</button>);
  } else if (latestAnswer?.needsLocation && previous?.role === "user") {
    caption = [LocateFixed, t("위치가 필요해요", "Location needed")];
    const question = previous.text;
    items.push(<button key="locate" type="button" className={c.chip} data-solid disabled={busy || chat.locating} onClick={() => void chat.askWithLocation(question)}><LocateFixed size={15} strokeWidth={1.8} aria-hidden="true" /><span>{chat.locating ? t("위치 찾는 중…", "Finding your location…") : t("내 위치 알려 주고 다시 묻기", "Share my location and ask again")}</span></button>);
  } else if (selected) {
    caption = [MapPin, t(`${selected.title}에 대해`, `About ${selected.title}`)];
    about = true;
    const place = selected.place ?? selected.title;
    items.push(chip("detail", MapPin, t("선택 일정", "Selected stop"), askDetail), chip("next", ArrowRight, t("다음 일정", "Next stop"), askNext),
      chip("route", Navigation, t("가는 길", "Directions"), () => void chat.askWithLocation(t(`여기서 ${place} 어떻게 가?`, `How do I get to ${place} from here?`))));
  } else {
    caption = [Clock, t(`${dayText} · 지금 ${hhmm(now.minute)}`, `${dayText} · now ${hhmm(now.minute)}`)];
    items.push(chip("nownext", Clock, t("지금 다음 일정", "Next from now"), () => chat.ask(t("다음 일정 알려 줘", "What is next?"), false, null)));
  }
  items.push(<span key="sep" className={c.sep} />,
    chip("summary", CalendarDays, t("하루 요약", "Day summary"), () => chat.ask(t(`${day} 하루 일정을 요약해 주세요.`, `Summarize the itinerary for ${day}.`), false, null, null, day)),
    chip("booking", Ticket, t("예약 표시", "Booking notes"), () => chat.ask(t(`${day} 예약 표시를 알려 주세요.`, `Show booking notes for ${day}.`))));
  if (selected && !about) items.push(chip("detail", MapPin, t("선택 일정", "Selected stop"), askDetail), chip("next", ArrowRight, t("다음 일정", "Next stop"), askNext));
  const [CaptionIcon, captionText] = caption;
  const row = useSlide<HTMLDivElement>(`${captionText}|${latestAnswer?.id ?? ""}|${proposal?.id ?? ""}`);
  return <div className={c.chips} data-hidden={chat.draft ? "" : undefined} data-chat-chips>
    <p className={c.caption}><CaptionIcon size={13} strokeWidth={2} aria-hidden="true" />{captionText}</p>
    <div ref={row} className={`${c.row2} ${c.slide}`} data-slide data-no-swipe role="group" aria-label={t("빠른 질문", "Quick questions")}>{items}</div>
  </div>;
}

/**
 * `[2026-10-07 사용자 결정 — 목업 C안]` The chat bar at the bottom of the frame. Closed: a round chat button. Pressed: it grows into the bar WITHOUT focusing the field (no phone keyboard);
 * the keyboard focus goes to its close button. Pressing the field (or tabbing into it) takes the sheet to the chat pane and the message is written there. In the chat pane it stays open.
 * `[2026-10-14 사용자 결정 — ST4F-493]` In the chat pane only, a round grey ← at the bar's left (where ✕ is outside it) goes back to the schedule — the sheet head has no chat button any more.
 * `subject`: the chosen stop's place name — the field's hint asks about it (the chat answers about the chosen stop) instead of 「일정」.
 * `[2026-10-14 사용자 지시 — ST4F-493]` The field keeps the width between the buttons and grows downward line by line as the message wraps, up to three lines; past that its height stays
 * and it scrolls. Enter still sends (as the one-line field did); Shift+Enter is a new line, and the Enter the browser reports while a Korean syllable is still being composed is not a
 * send (Chrome reports that Enter once more when the syllable is done — sending on both sends the last syllable twice). On a phone (no mouse, a finger — there is no Shift+Enter)
 * Enter is always a new line and the send button sends. The hint is drawn over the empty field so a long one ends in 「…」(a textarea's own placeholder cannot).
 * `[2026-10-14 사용자 결정]` Opening, the round button becomes the send button in its place (💬 turns into ➤ — `chatSendFrom` · `chatSendTo`, CSS in trip-screen.module.css).
 * `[2026-10-22 사용자 결정 — ST4F-719]` In the chat pane, under the field: one short line on what chat does not change + 「자세히」 (the whole sentence floats above the bar, and a press anywhere
 * else, Esc or 「자세히」 again folds it — the press elsewhere still does what it does).
 */
const touchKeyboard = () => typeof matchMedia === "function" && matchMedia("(hover: none) and (pointer: coarse)").matches;

export function ChatBar({ chat, open, inChat, subject, onOpen, onClose, onEnterChat, onLeaveChat }: { chat: TripChat; open: boolean; inChat: boolean; subject: string | null; onOpen: () => void; onClose: () => void; onEnterChat: () => void; onLeaveChat: () => void }) {
  const t = useT();
  const closeButton = useRef<HTMLButtonElement>(null);
  const fab = useRef<HTMLButtonElement>(null);
  const shown = open || inChat;
  const wasShown = useRef(shown);
  const wasInChat = useRef(inChat);
  const backToFab = useRef(false);
  const field = useRef<HTMLTextAreaElement>(null);
  const note = useRef<HTMLDivElement>(null);
  const [noteOpen, setNoteOpen] = useState(false);
  // Leaving the chat pane folds it (the note is not drawn over the plan).
  const [noteIn, setNoteIn] = useState(inChat);
  if (noteIn !== inChat) { setNoteIn(inChat); if (!inChat) setNoteOpen(false); }
  // The keyboard focus follows the bar: to its close button when it opens from the round button (which is gone), back to the round button when its close button shut it.
  useEffect(() => {
    if (shown && !wasShown.current && !inChat && document.activeElement === document.body) closeButton.current?.focus({ preventScroll: true });
    // `[2026-10-15 검토]` ← left the chat but the bar stays open (a draft is kept): ← is gone and ✕ stands in its place — the focus goes there, not to the page.
    if (shown && !inChat && wasInChat.current && backToFab.current) { backToFab.current = false; closeButton.current?.focus({ preventScroll: true }); }
    if (!shown && backToFab.current) { backToFab.current = false; fab.current?.focus({ preventScroll: true }); }
    wasShown.current = shown;
    wasInChat.current = inChat;
  }, [shown, inChat]);
  // The field's height follows its text (the CSS `max-height` stops it at three lines, then it scrolls) — and the width (a turned phone wraps the same text differently).
  useLayoutEffect(() => {
    const box = field.current;
    if (!box) return;
    const fit = () => { box.style.height = "auto"; box.style.height = `${box.scrollHeight}px`; };
    fit();
    window.addEventListener("resize", fit);
    return () => window.removeEventListener("resize", fit);
  }, [chat.draft, shown, inChat]);
  // The note's whole sentence folds on a press outside it (and its 「자세히」, which toggles it), or Esc.
  useEffect(() => {
    if (!noteOpen) return;
    const away = (event: PointerEvent) => { if (!note.current?.contains(event.target as Node)) setNoteOpen(false); };
    const escape = (event: KeyboardEvent) => { if (event.key === "Escape") { event.stopPropagation(); setNoteOpen(false); } };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", escape, true);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", escape, true); };
  }, [noteOpen]);
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    chat.ask(chat.draft, true);
  }
  const hint = subject ? t(`${subject}에 대해 궁금한 점을 입력하세요`, `Ask about ${subject}`) : t("일정에 대해 궁금한 점을 입력하세요", "Ask about your itinerary");
  if (!shown) {
    return <div className={styles.chatBar}><button ref={fab} type="button" className={styles.chatFab} onClick={onOpen} aria-label={t("채팅 입력 열기", "Open the chat")}><MessageCircle size={26} strokeWidth={1.7} aria-hidden="true" /></button></div>;
  }
  const describedBy = [chat.inputError ? "trip-chat-error" : "", inChat ? "trip-chat-note" : ""].filter(Boolean).join(" ") || undefined;
  // `[2026-10-15 사용자 결정 — ST4F-493 · 목업 A안]` In the chat pane the bar sits on the bottom edge, full width (`data-docked`); opened over the plan it floats as before.
  return <div className={styles.chatBar} data-open data-docked={inChat || undefined}>
    {!inChat && <button ref={closeButton} type="button" className={styles.chatClose} onClick={() => { backToFab.current = true; onClose(); }} aria-label={t("채팅 막대 접기", "Close the chat bar")}><X size={18} strokeWidth={1.8} aria-hidden="true" /></button>}
    {inChat && <button type="button" className={styles.chatClose} onClick={() => { backToFab.current = true; onLeaveChat(); }} aria-label={t("일정으로 돌아가기", "Back to the itinerary")} title={t("일정으로 돌아가기", "Back to the itinerary")}><ArrowLeft size={18} strokeWidth={1.8} aria-hidden="true" /></button>}
    <form className={styles.chatForm} onSubmit={submit} noValidate>
      <label className="sr-only" htmlFor="trip-chat-message">{t("여행 메시지", "Travel message")}</label>
      <span className={styles.chatField}>
      <textarea ref={field} id="trip-chat-message" className={styles.chatInput} rows={1} value={chat.draft} maxLength={600} autoComplete="off" placeholder={hint} readOnly={chat.message.isPending} aria-disabled={chat.message.isPending || undefined}
        aria-invalid={Boolean(chat.inputError)} aria-describedby={describedBy}
        onFocus={() => { if (!inChat) onEnterChat(); }}
        onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing && !touchKeyboard()) { event.preventDefault(); event.currentTarget.form?.requestSubmit(); } }}
        onChange={(event) => { chat.setDraft(event.target.value); if (chat.inputError) chat.setInputError(""); }} />
      {!chat.draft && <span className={styles.chatHint} aria-hidden="true">{hint}</span>}
      </span>
      <button type="submit" className={styles.chatSend} aria-disabled={chat.message.isPending || undefined} style={chat.message.isPending ? { opacity: .5, cursor: "not-allowed" } : undefined} aria-label={t("메시지 전송", "Send message")}><MessageCircle className={styles.chatSendFrom} size={18} strokeWidth={1.8} aria-hidden="true" /><Send className={styles.chatSendTo} size={18} strokeWidth={1.8} aria-hidden="true" /></button>
    </form>
    {chat.inputError && <p id="trip-chat-error" className={styles.chatError} role="alert">{chat.inputError}</p>}
    {inChat && <div ref={note} className={c.note}>
      <span id="trip-chat-note">{t("숙소 · 항공 · 예약한 일정은 「일정 수정」에서 바꿔요", "Change lodging, flights and bookings in “Edit itinerary”")}</span>{" "}
      <button type="button" className={c.noteMore} aria-expanded={noteOpen} aria-controls="trip-chat-note-full" onClick={() => setNoteOpen((value) => !value)}>{t("자세히", "More")}</button>
      {noteOpen && <p id="trip-chat-note-full" className={c.notePop} role="note">{t("채팅으로 일정을 바꾸면 여행계획서에 새 판이 생겨요. 숙소 · 항공 · 예약한 일정은 채팅으로 바꾸지 않아요 — 「일정 수정」에서 고쳐 주세요.", "Changes made in chat create a new version of your trip plan. Lodging, flights and booked stops are not changed from chat — use “Edit itinerary”.")}</p>}
    </div>}
  </div>;
}
