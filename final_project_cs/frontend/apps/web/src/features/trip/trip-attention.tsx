"use client";

import Link from "next/link";
import { useEffect, useRef, useState, useSyncExternalStore, type KeyboardEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronRight, ExternalLink, History, Undo2 } from "lucide-react";
import { Button } from "@/components/ui";
import { MaintenanceItem, NoticeItems, useServiceStatus } from "@/features/support/service-notices";
import { markServiceNoticesSeen, useSeenServiceNotices } from "@/features/support/service-notice-reads";
import { routes } from "@/lib/routes";
import { seoul } from "@/lib/live/gateway";
import { LiveError } from "@/lib/live/client";
import { undoChange, type Notice } from "@/lib/live/extras";
import { useSettings, useT } from "@/lib/settings";
import type { Translate } from "@/lib/i18n";
import { causeLines, changeOf, dayBefore, NOTICE_LIMIT, noticeFeed, openChoices, proposalText, undoableChange, withoutPlanLink, type FeedEntry, type OpenChoice } from "./attention";
import { proposalAvailable } from "./trip-chat-records";
import { chooseFailure, chooseOutcome, useChooseProposal } from "./proposal-ask";
import { NoticeCard, noticeKind, ProposalCard } from "./trip-chat-notices";
import { serverDayLabel } from "./chat-cards";
import { LinkedText } from "./linked-text";
import type { Trip, TripChange, TripStop } from "./model";
import { markNoticesSeen, useSeenNotices } from "./notice-reads";
import { ownChange } from "./own-changes";
import { tripDays } from "./trip-timeline";
import { tripKey } from "./use-trip";
import { useSeoulNow } from "./use-seoul-now";
import { noticesKey, proposalsKey, recoveryKey, useNotices, useProposals, useRecovery, useTripRisks } from "./use-trip-extras";
import { panelRisks, RiskPanel } from "@/features/risk/risk-panel";
import { useRiskAlternatives } from "./use-risk-alternatives";
import { SafetyPanel } from "./trip-safety";
import { RecoveryPanel } from "./trip-recovery";
import type { Recovery } from "@/lib/live/recovery";
import c from "./trip-chat.module.css";
import styles from "./trip-attention.module.css";
import { askBrowserNotify, browserNotifyState, type BrowserNotifyState } from "@/lib/browser-notify";

export const NOTICE_LABEL: Record<string, [string, string]> = {
  guidance: ["안내", "Guidance"], proposal_request: ["선택 요청", "Your choice"],
  safety_alert: ["안전 알림", "Safety alert"], change_notice: ["변경 알림", "Change"],
};

export const noticeWhen = (iso: string) => { const at = seoul(iso); return `${at.date} ${at.time}`; };

/**
 * `[2026-10-22 사용자 결정 — ST4F-723 구성 Ⓑ]` The notice center's three tabs: 「할 일」 (what waits for the customer's answer, then what is worth a look) · 「소식」 (what the server sent and
 * changed, by day — the old 「받은 알림」 and 「변경 이력」 in one list) · 「공지」 (the service's own notices, `[2026-10-17 ST4F-606]`).
 */
export type CenterTab = "todo" | "feed" | "service";
const TABS: readonly [CenterTab, string, string][] = [["todo", "할 일", "To do"], ["feed", "소식", "Updates"], ["service", "공지", "Announcements"]];

/**
 * `[2026-10-14 실서버 확인]` The words for the reason the server wrote a version (`append_version(reason=…)`) — 「처음 등록」 was the only one; the others showed the code itself
 * (`customer_request` …) to the customer. A reason not listed here still shows the server's code (the rule above: the screen does not write a line of its own about what it does not know).
 * `[2026-10-22 ST4F-723]` `customer_report` (「늦어요」 · 「문 닫았어요」 · 「끝났어요」 told by the customer, `journey_progress` · `itinerary_changes`) had none.
 */
const VERSION_REASON: Record<string, [string, string]> = {
  created: ["처음 등록", "Registered"],
  customer_request: ["직접 고침", "Changed by you"],
  customer_choice: ["고른 안 적용", "Your pick applied"],
  customer_report: ["알려 주신 대로 바꿈", "Changed as you told us"],
  auto_adjusted: ["자동으로 바꿈", "Changed automatically"],
  rollback: ["되돌림", "Undone"],
};
const reasonLabel = (change: TripChange, t: Translate) => VERSION_REASON[change.reason] ? t(...VERSION_REASON[change.reason]) : change.reason;

/** A proposal's state on its card in 「소식」 (`GET …/proposals` status). */
const PROPOSAL_STATE: Record<string, [string, string, boolean]> = {
  open: ["선택이 필요해요", "Needs your choice", false], chosen: ["고른 안 적용", "Your pick applied", true], kept: ["그대로 둠", "Kept", true],
  expired: ["기한 지남", "Expired", true], superseded: ["일정이 바뀌어 닫힘", "Closed — the plan changed", true],
};

/** A notice this long (a safety alert, a morning guide, a closed proposal's question) is cut to a few lines with 「더 보기」. */
const LONG_TEXT = 90;

/**
 * `[2026-10-17 사용자 결정 — ST4F-606]` 「공지」 탭 — 운영 앱의 공지(여행과 상관없는 전체 공지)를 맨 위 배너와 같은 모양으로(종류 딱지 · 장애 먼저), 점검 중이면 점검도.
 *   (옛 ST4F-604: 알림 센터 맨 위 「서비스 공지」 칸 — 할 일을 화면 아래로 밀어 탭으로 옮겼다.) 끝에 지난 공지까지 보는 공지사항 게시판으로 가는 길.
 */
function ServiceNoticeTab() {
  const t = useT();
  const status = useServiceStatus();
  const notices = status.data?.notices ?? [];
  const maintenance = status.data?.maintenance.enabled ? status.data.maintenance : null;
  return <div className={styles.service} data-service-notices>
    {status.isPending && <p className={styles.empty}>{t("공지를 불러오고 있어요.", "Loading the notices.")}</p>}
    {status.error && !status.data && <p className={styles.error} role="alert">{t("공지를 불러오지 못했어요.", "Could not load the notices.")}</p>}
    {status.data && notices.length === 0 && !maintenance && <p className={styles.empty}>{t("지금 게시 중인 공지가 없어요.", "No notices are posted now.")}</p>}
    {maintenance && <MaintenanceItem maintenance={maintenance} />}
    <NoticeItems notices={notices} />
    <Link href={routes.notices} className={styles.toBoard}>{t("지난 공지까지 보기 › 공지사항", "Past notices too › Notices")}</Link>
  </div>;
}

/**
 * Live only: what the server is waiting for, found and sent about this trip — the body of the notice center the bell opens.
 * `[2026-10-22 사용자 결정 — ST4F-723 구성 Ⓑ · 카드 ⓑ]` Three tabs at the top (the 10-17 「답이 필요해요」 above the tabs pushed the list ~540px down when there was something to answer):
 * - 「할 일」: the disaster pause → going on after it → the choices the server waits for → the automatic change that can be undone — answered, they move to 「소식」; then 「살펴볼 점」
 *   (the risk check and what the server found at registration).
 * - 「소식」: newest first under date heads; a proposal's notices (asked · options · the change it made) on one card with its state, a version on the card of the notice that made it.
 * - 「공지」: the service's notices.
 * The cards are the chat's (`trip-chat-notices.tsx` — the same parts, ST4F-719). ★Every sentence on them is the server's — its notice text, its warning reason, its history. A piece of it is left
 * out only where the card draws the same thing (`proposalText` · `withoutPlanLink`). Read state is this browser's (`notice-reads.ts`): the server keeps none yet.
 */
export function TripAttention({ trip, tab, onTab, onDetail, onResumed, focusNotice = null, focusItemId = null }: {
  trip: Trip; tab: CenterTab; onTab: (tab: CenterTab) => void;
  /** A notice to show: in 「할 일」 a safety alert or a choice (its alternatives are waited for), in 「소식」 the card that carries it (scrolled to, lit once). */
  focusNotice?: Notice | null;
  /** A stop at risk whose alternatives were asked for (「위험·대안 보기」). */
  focusItemId?: string | null;
  /** 「상세 보기」 on a stop's row: close the center and open that stop's detail (its choice is answered there too, ST4F-704). */
  onDetail: (stopId: string) => void;
  /** 「일정 다시 시작」 answered with the brief of the disaster just lifted (null when there was nothing to lift). */
  onResumed: (recovery: Recovery | null) => void;
}) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  // `[2026-10-07]` The server's "this trip changed" bell is kept by the trip screen (`trip-screen.tsx`) — it listens while the trip is open, not only while this list is shown.
  const proposals = useProposals(trip.id);
  const notices = useNotices(trip.id);
  const { refetch: refetchProposals } = proposals;
  const { refetch: refetchNotices } = notices;
  const recovery = useRecovery(trip.id);
  const risks = useTripRisks(trip.id, trip.version);
  const currentRisks = risks.data?.items ?? [];
  // `[2026-10-22 사용자 지시]` 운영자가 위험 점검 칸을 끄면(`trip.riskPanel`) 「살펴볼 점」에는 실제 위험 일정만 남는다(위험 알림 · 종 · 카드 표시가 여기로 온다).
  const riskPanelShown = trip.riskPanel !== false;
  const shownRisks = panelRisks(currentRisks, riskPanelShown);
  const riskAlternatives = useRiskAlternatives(trip.id, () => onTab("todo"));
  const all = notices.data ?? [];
  const history = trip.history ?? [];
  const choices = openChoices(proposals.data ?? [], all, trip.stops)
    .filter((choice) => Boolean(choice.stop) && proposalAvailable(choice.proposal, trip.version));
  const undoable = undoableChange(all, trip.version);
  const held = { proposals: new Set(choices.map((choice) => choice.proposal.id)), notices: new Set(undoable ? [undoable.key] : []) };
  const feed = noticeFeed(all, proposals.data ?? [], held, history);
  const shownFeed = feed.slice(0, NOTICE_LIMIT);
  const days = tripDays(trip);
  const now = useSeoulNow();

  // ── A notice to show (the notice bar's 「알림 보기」, `?notices=1`, 「위험·대안 보기」) ──
  const waitFor = tab === "todo" && (focusItemId !== null || focusNotice?.type === "safety_alert" || focusNotice?.type === "proposal_request");
  const targetChoiceId = waitFor
    ? (focusNotice?.proposalId ? choices.find((choice) => choice.proposal.id === focusNotice.proposalId)
      : focusItemId ? choices.find((choice) => choice.proposal.itemId === focusItemId) : choices[0])?.proposal.id
    : undefined;
  const focusedNoticeKey = waitFor ? focusNotice?.key ?? (focusItemId ? `risk:${focusItemId}` : undefined) : undefined;
  const [answeredNoticeKey, setAnsweredNoticeKey] = useState<string | null>(null);
  const choiceAnswered = Boolean(focusedNoticeKey && answeredNoticeKey === focusedNoticeKey);
  const choiceTarget = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!focusedNoticeKey || !targetChoiceId) return;
    const frame = requestAnimationFrame(() => {
      const target = choiceTarget.current;
      const action = target?.querySelector<HTMLButtonElement>("button:not(:disabled)") ?? target;
      action?.scrollIntoView({ block: "center", behavior: "instant" });
      action?.focus({ preventScroll: true });
    });
    return () => cancelAnimationFrame(frame);
  }, [focusedNoticeKey, targetChoiceId]);
  useEffect(() => {
    if (!focusedNoticeKey || targetChoiceId || choiceAnswered) return;
    const poll = setInterval(() => {
      void refetchProposals({ cancelRefetch: false });
      void refetchNotices({ cancelRefetch: false });
    }, 3_000);
    const bounded = setTimeout(() => clearInterval(poll), 90_000);
    return () => { clearInterval(poll); clearTimeout(bounded); };
  }, [focusedNoticeKey, targetChoiceId, choiceAnswered, refetchProposals, refetchNotices]);
  // In 「소식」: the card that carries the notice, scrolled to and lit once.
  const flashKey = tab === "feed" && focusNotice ? entryKey(feed.find((entry) => carries(entry, focusNotice.key)) ?? null) : null;
  useEffect(() => {
    if (!flashKey) return;
    const frame = requestAnimationFrame(() => document.querySelector(`[data-feed-entry="${CSS.escape(flashKey)}"]`)?.scrollIntoView({ block: "center", behavior: "instant" }));
    return () => cancelAnimationFrame(frame);
  }, [flashKey]);

  // ── Read state: a tab marks what it shows (a dot stays on what was first seen in this opening, until the center closes) ──
  const seen = useSeenNotices(trip.id);
  const [seenAtOpen] = useState(() => new Set(seen));
  const isHeld = (notice: Notice) => Boolean(notice.proposalId && held.proposals.has(notice.proposalId)) || held.notices.has(notice.key);
  const keysOf = (pick: (notice: Notice) => boolean) => all.filter(pick).map((notice) => notice.key).join("\n");
  const todoKeys = keysOf(isHeld);
  const feedKeys = keysOf((notice) => !isHeld(notice) && notice.kind !== "service_notice");
  const serviceTripKeys = keysOf((notice) => notice.kind === "service_notice");
  useEffect(() => {
    const keys = tab === "todo" ? todoKeys : tab === "feed" ? feedKeys : serviceTripKeys;
    if (keys) markNoticesSeen(trip.id, keys.split("\n"));
  }, [tab, todoKeys, feedKeys, serviceTripKeys, trip.id]);
  const feedUnread = feedKeys.split("\n").some((key) => key && !seen.includes(key));
  const fresh = (list: readonly Notice[]) => list.some((notice) => !seenAtOpen.has(notice.key)) ? t("새 알림", "New") : null;
  // `[2026-10-17 사용자 결정 — ST4F-606]` 운영 앱 공지도 같다 — 「공지」 탭이 보여 주면 읽음(종 숫자에서 빠진다). 새것이 있으면 탭에 점.
  const service = useServiceStatus();
  const seenService = useSeenServiceNotices();
  const serviceNotices = service.data?.notices ?? [];
  const serviceKeys = serviceNotices.map((notice) => notice.id).join("\n");
  const serviceUnread = serviceNotices.some((notice) => !seenService.includes(notice.id));
  useEffect(() => {
    if (tab === "service" && serviceKeys) markServiceNoticesSeen(serviceKeys.split("\n"));
  }, [tab, serviceKeys]);
  // `[2026-10-17 사용자 결정 — ST4F-606]` 재난 뒤 이어가기는 한 장짜리 카드로 — 누르면 지금의 전체 패널을 그 자리에 펼친다.
  const [recoveryOpen, setRecoveryOpen] = useState(false);
  const [opened, setOpened] = useState<ReadonlySet<string>>(new Set());
  const toggle = (key: string) => setOpened((before) => { const next = new Set(before); if (!next.delete(key)) next.add(key); return next; });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: tripKey(trip.id, language) });
    void queryClient.invalidateQueries({ queryKey: proposalsKey(trip.id, language) });
    void queryClient.invalidateQueries({ queryKey: noticesKey(trip.id, language) });
  };
  const chosen = () => { refresh(); void queryClient.invalidateQueries({ queryKey: recoveryKey(trip.id, language) }); };
  // Refused because it was already decided or the trip moved on: nothing changed, so it re-reads what is true now (`useChooseProposal`).
  const choose = useChooseProposal(trip.id, trip.version);
  const answer = (proposalId: string, key: string | null) => {
    const noticeKey = focusedNoticeKey;
    choose.mutate({ proposalId, key }, { onSuccess: (result) => { if (result.status !== "options" && noticeKey) setAnsweredNoticeKey(noticeKey); } });
  };

  // ★Undo an automatic change (only customers who chose "change it automatically" get those). 409 = the plan moved on.
  const undo = useMutation({
    mutationFn: (notice: Notice) => ownChange(trip.id, trip.version, () => undoChange(trip.id, notice.rollback!, language)),
    onSettled: refresh,
  });

  const readError = proposals.error ?? notices.error;
  const warnings = trip.warnings ?? [];
  const paused = Boolean(trip.safety?.paused);
  const goingOn = !paused && recovery.data ? recovery.data : null;
  const tasks = (paused ? 1 : 0) + (goingOn && !goingOn.chosen ? 1 : 0) + choices.length + (undoable ? 1 : 0);
  const worth = warnings.length + currentRisks.filter((item) => item.status === "problem").length;
  const serviceCount = serviceNotices.length + (service.data?.maintenance.enabled ? 1 : 0);

  function tabKeys(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const at = TABS.findIndex(([key]) => key === tab);
    const next = TABS[(at + (event.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length][0];
    event.preventDefault();
    onTab(next);
    requestAnimationFrame(() => document.getElementById(`trip-center-tab-${next}`)?.focus());
  }

  const dayOf = (stop: TripStop) => t(`${days.indexOf(stop.date) + 1}일차`, `Day ${days.indexOf(stop.date) + 1}`);
  const stopRow = (stop: TripStop) => <div className={styles.stop}>
    <span><b>{stop.title}</b><small>{dayOf(stop)} {stop.time}</small></span>
    <button type="button" className={styles.go} onClick={() => onDetail(stop.id)}>{t("상세 보기", "Details")}<ChevronRight size={14} strokeWidth={2} aria-hidden="true" /></button>
  </div>;
  /** The server's sentence; a long one (a safety alert, a guide, a closed proposal's question) is cut to a few lines until 「더 보기」. */
  const body = (key: string, text: string | null, long: boolean) => {
    if (!text) return <p className={c.body}>{t("서버가 문장을 보내지 않았어요.", "The server sent no text.")}</p>;
    const cut = long && text.length > LONG_TEXT;
    const open = opened.has(key);
    return <>
      <p className={c.body}><span className={cut && !open ? styles.clamp : undefined}><LinkedText text={text} mapLabel={t("지도 앱으로 열기", "Open in maps app")} /></span></p>
      {cut && <button type="button" className={styles.more} aria-expanded={open} onClick={() => toggle(key)}>{open ? t("접기", "Show less") : t("더 보기", "Show more")}</button>}
    </>;
  };
  /** Every notice of a proposal, oldest first, folded under its card. */
  const flow = (list: readonly Notice[]) => list.length > 1 && <details className={styles.flow}>
    <summary><ChevronDown size={14} strokeWidth={2} aria-hidden="true" />{t(`받은 알림 ${list.length}개 모두 보기`, `All ${list.length} notices`)}</summary>
    <ol>{list.map((notice) => <li key={notice.key}><b>{noticeWhen(notice.at)} · {noticeKind(notice.type, t).label}</b>
      {notice.text ? <LinkedText text={notice.text} mapLabel={t("지도 앱으로 열기", "Open in maps app")} /> : t("서버가 문장을 보내지 않았어요.", "The server sent no text.")}</li>)}</ol>
  </details>;

  const choiceTask = ({ proposal, stop, text }: OpenChoice) => {
    const list = all.filter((notice) => notice.proposalId === proposal.id).sort((a, b) => Date.parse(a.at) - Date.parse(b.at));
    const latest = list.at(-1);
    const kind = noticeKind(latest?.type ?? "proposal_request", t);
    const meta = [proposal.safety ? t("안전과 관련된 선택이에요.", "This one is about safety.") : "",
      proposal.expiresAt ? t(`${noticeWhen(proposal.expiresAt)} 까지`, `Until ${noticeWhen(proposal.expiresAt)}`) : ""].filter(Boolean).join(" ");
    return <div key={proposal.id} className={styles.pair} data-center-proposal={proposal.id} tabIndex={-1} ref={proposal.id === targetChoiceId ? choiceTarget : undefined}>
      <NoticeCard {...kind} state={{ text: t("선택이 필요해요", "Needs your choice") }} unread={fresh(list)} at={latest?.at ?? ""} when={latest ? noticeWhen(latest.at) : ""} data-task>
        {stop && stopRow(stop)}
        <p className={c.body}>{text ? <LinkedText text={proposalText(text, { stopTitle: stop?.title, options: proposal.options })} mapLabel={t("지도 앱으로 열기", "Open in maps app")} />
          : t("이 일정을 어떻게 할지 골라 주세요.", "Choose what to do with this stop.")}</p>
        {flow(list)}
      </NoticeCard>
      <ProposalCard proposal={proposal} title={null} time={null} available busy={choose.isPending} onReload={() => void proposals.refetch()}
        onChoose={(key) => answer(proposal.id, key)} meta={meta || null} />
    </div>;
  };

  const noticeEntry = (notice: Notice) => {
    const change = changeOf(notice, history);
    const kind = noticeKind(notice.type, t);
    const planText = notice.text ? withoutPlanLink(notice.text, trip.planUrl) : null;
    const causes = change?.reason === "auto_adjusted" ? causeLines(change.causes) : [];
    return <NoticeCard key={notice.key} {...kind} label={change ? reasonLabel(change, t) : kind.label} unread={fresh([notice])} at={notice.at} when={noticeWhen(notice.at)}
      data-feed-entry={notice.key} data-flash={flashKey === notice.key || undefined}>
      {body(notice.key, planText ?? notice.text, notice.type === "safety_alert" || notice.type === "guidance")}
      {(planText !== null || causes.length > 0) && <div className={c.foot}>
        {causes.length > 0 && <span className={c.footTitle}>{causes.join(" · ")}</span>}
        {planText !== null && trip.planUrl && <a className={c.button} href={trip.planUrl} target="_blank" rel="noopener noreferrer">
          <ExternalLink size={15} strokeWidth={1.8} aria-hidden="true" />{t("여행계획서 열기", "Open your trip plan")}</a>}
      </div>}
    </NoticeCard>;
  };
  const proposalEntry = (entry: Extract<FeedEntry, { kind: "proposal" }>) => {
    const { proposal } = entry;
    const latest = entry.notices.at(-1)!;
    // An open proposal here is one that can no longer be answered (the plan moved on or its stop is gone) — 「할 일」 holds the others.
    const state = proposal ? proposal.status === "open" ? [t("지난 제안", "Past proposal"), true] as const
      : PROPOSAL_STATE[proposal.status] ? [t(PROPOSAL_STATE[proposal.status][0], PROPOSAL_STATE[proposal.status][1]), PROPOSAL_STATE[proposal.status][2]] as const : [proposal.status, true] as const : null;
    const ask = [...entry.notices].reverse().find((notice) => notice.type === "proposal_request" || notice.type === "safety_alert") ?? latest;
    const kind = noticeKind(ask.type, t);
    return <NoticeCard key={entry.proposalId} {...kind} tone="muted" state={state && { text: state[0], done: state[1] }} unread={fresh(entry.notices)} at={latest.at} when={noticeWhen(latest.at)}
      data-feed-entry={entry.proposalId} data-flash={flashKey === entry.proposalId || undefined}>
      {body(entry.proposalId, latest.text, true)}
      {flow(entry.notices)}
    </NoticeCard>;
  };
  const versionEntry = (change: TripChange) => <div key={`v${change.version}`} className={styles.version} data-feed-entry={`v${change.version}`}>
    <p><History size={14} strokeWidth={1.8} aria-hidden="true" /><b>{reasonLabel(change, t)}</b><time>{change.at.slice(11)}</time></p>
    {causeLines(change.causes).map((cause) => <p key={cause} className={styles.remedy}>{cause}</p>)}
  </div>;
  const dayHead = (date: string) => {
    const label = t(serverDayLabel(date), new Intl.DateTimeFormat("en", { month: "short", day: "numeric", weekday: "short", timeZone: "Asia/Seoul" }).format(new Date(`${date}T12:00:00+09:00`)));
    return date === now.date ? t(`오늘 · ${label}`, `Today · ${label}`) : date === dayBefore(now.date) ? t(`어제 · ${label}`, `Yesterday · ${label}`) : label;
  };
  const byDay: [string, FeedEntry[]][] = [];
  for (const entry of shownFeed) {
    const date = seoul(entry.at).date;
    if (byDay.at(-1)?.[0] === date) byDay.at(-1)![1].push(entry);
    else byDay.push([date, [entry]]);
  }

  return <div className={styles.wrap}>
    {readError && <div className={styles.error} role="alert">{t("선택과 알림을 읽지 못했어요 — ", "Could not read your choices and notices — ")}{readError instanceof Error ? readError.message : String(readError)}</div>}

    <div className={styles.tabs} role="tablist" aria-label={t("알림 종류", "Kinds of notices")} onKeyDown={tabKeys}>
      {TABS.map(([key, ko, en]) => <button key={key} type="button" role="tab" id={`trip-center-tab-${key}`} aria-selected={tab === key} aria-controls="trip-center-panel" tabIndex={tab === key ? 0 : -1}
        onClick={() => onTab(key)}>{t(ko, en)}{" "}
        {/* `[2026-10-23 사용자 결정]` 「할 일」 숫자는 늘 답할 것의 수 — 없으면 0(옛: 「살펴볼 점」 수를 흐리게, 「할 일 1」인데 「지금 처리할 일은 없어요.」로 읽혔다) */}
        {key === "todo" ? <span className={styles.count} data-hot={tasks > 0 || undefined}>{tasks}</span>
          : <span className={styles.count}>{key === "feed" ? feed.length : serviceCount}</span>}
        {((key === "feed" && feedUnread) || (key === "service" && serviceUnread)) && <span className={styles.unread} role="img" aria-label={t("읽지 않은 알림", "Unread notices")} />}</button>)}
    </div>
    <div id="trip-center-panel" role="tabpanel" aria-labelledby={`trip-center-tab-${tab}`} className={styles.panel}>
      {tab === "todo" && <>
        {/* `[2026-10-06]` 재난으로 일정이 멈췄으면 맨 위에: 정지 · 안전 안내 · 다시 시작(일정 칸 맨 윗줄에도 같은 패널이 있다). 정지가 없으면 아무것도 그리지 않는다. */}
        <SafetyPanel trip={trip} notices={all} onChanged={refresh} onResumed={onResumed} where="center" />
        {focusedNoticeKey && !targetChoiceId && !choiceAnswered && <section className={styles.act} data-tone="info" data-notice-choice-state>
          <h4>{focusNotice ? t("알림과 대안 선택", "Notice and alternatives") : t("현재 위험과 대안 선택", "Current risk and alternatives")}</h4>
          {focusNotice?.text && <p><LinkedText text={focusNotice.text} mapLabel={t("지도 앱으로 열기", "Open in maps app")} /></p>}
          <p role="status">{proposals.isFetching || notices.isFetching
            ? t("대안 제안을 확인하고 있어요.", "Checking for alternative proposals.")
            : t("아직 선택할 대안을 받지 못했어요. 새 제안이 도착하면 자동으로 보여 드려요.", "No alternative proposal has arrived yet. New proposals appear here automatically.")}</p>
        </section>}
        {/* `[2026-10-06]` 다시 시작한 뒤(72시간 안): 아는 것 · 모르는 것 · 남은 일정의 영향 · 이어가는 세 가지 길. 다시 정지 중이면(새 사건) 그 정지 패널이 먼저다. */}
        {goingOn && (recoveryOpen ? <RecoveryPanel key={goingOn.pauseId} trip={trip} recovery={goingOn} onChosen={chosen} />
          : <section className={styles.act} data-tone="safety" aria-labelledby="trip-recovery-short" data-recovery-short>
            <h4 id="trip-recovery-short">{t("재난 뒤 이어가기", "Going on after the disaster")}</h4>
            <p>{[goingOn.event.label, goingOn.event.at ? noticeWhen(goingOn.event.at) : null].filter(Boolean).join(" · ")}{" — "}
              {goingOn.chosen ? t("고르신 것을 다시 보거나 바꿀 수 있어요.", "You can look at or change your choice.") : t("어떻게 이어갈지 골라 주세요.", "Choose how to go on.")}</p>
            <div className={styles.options}><Button variant={goingOn.chosen ? "secondary" : "primary"} onClick={() => setRecoveryOpen(true)}>
              {goingOn.chosen ? t("고르신 것 보기", "See your choice") : t("이어갈 방법 고르기", "Choose how to go on")}</Button></div>
          </section>)}

        {choices.map(choiceTask)}
        {/* ★Outside the choice cards: after a decision the server closes the proposal and the card goes away, but what happened (no other place / already decided) must still be said.
             `[2026-10-22 사용자 결정 — ST4F-723]` The options coming in say nothing (「다른 곳을 찾았어요 — 위에서 골라 주세요.」 is gone): they stand on the card that asked for them. */}
        {choose.error && <div className={styles.error} role="alert">{chooseFailure(choose.error, t)}</div>}
        {choose.data && !choose.error && chooseOutcome(choose.data.status, t) && <p className={styles.said} role="status">{chooseOutcome(choose.data.status, t)}</p>}

        {undoable && (() => {
          const change = changeOf(undoable, history);
          const kind = noticeKind(undoable.type, t);
          return <NoticeCard {...kind} label={change ? reasonLabel(change, t) : kind.label} unread={fresh([undoable])} at={undoable.at} when={noticeWhen(undoable.at)} data-task data-center-undo>
            {body(undoable.key, undoable.text, false)}
            <div className={c.foot}>
              <button type="button" className={c.button} disabled={undo.isPending} onClick={() => undo.mutate(undoable)}>
                <Undo2 size={15} strokeWidth={1.8} aria-hidden="true" />{undo.isPending ? t("되돌리는 중…", "Undoing…") : t("되돌리기", "Undo")}</button>
            </div>
          </NoticeCard>;
        })()}
        {undo.error && <div className={styles.error} role="alert">{undo.error instanceof LiveError && ["stale_itinerary", "stale", "invalid_version"].includes(undo.error.code)
          ? t("그 사이 일정이 다시 바뀌어 되돌리지 않았어요. 지금 상태를 다시 불러왔어요.", "The plan changed again meanwhile, so nothing was undone. We reloaded the current state.")
          : undo.error.message}</div>}
        {/* `[2026-10-22 ST4F-723]` 서버는 되돌린 결과를 `notice.text` 로 준다(`answer` 는 없다) */}
        {undo.data && !undo.error && <p className={styles.said} role="status">{undo.data.notice?.text ?? undo.data.answer ?? t("바꾸기 전 일정으로 되돌렸어요.", "Your plan is back to how it was.")}</p>}

        {tasks === 0 && !goingOn && !focusedNoticeKey && <p className={styles.empty}>{t("지금 처리할 일은 없어요.", "Nothing to do right now.")}</p>}

        {(riskPanelShown || shownRisks.length > 0 || warnings.length > 0) && <h3 className={styles.secTitle}>{t("살펴볼 점", "Worth a look")}{worth > 0 ? ` ${worth}` : ""}</h3>}
        {(riskPanelShown || shownRisks.length > 0) && <RiskPanel items={shownRisks} at={risks.data?.at} mode={risks.data?.mode} scope={riskPanelShown ? risks.data : undefined}
          loading={riskPanelShown && risks.isPending} busy={risks.isFetching} error={riskPanelShown && risks.isError} retry={risks.refresh}
          onAlternatives={riskAlternatives.ask} alternativeBusy={riskAlternatives.busy} alternativeMessage={riskAlternatives.message} />}
        {warnings.length > 0 && <ul className={styles.list}>{warnings.map((warning, index) => <li key={`${warning.code}-${warning.date ?? ""}-${index}`}>
          {warning.date && <span className={styles.tag}>{warning.date}</span>}
          <p>{warning.reason}</p>
          {warning.remedy && <p className={styles.remedy}>{warning.remedy}</p>}
        </li>)}</ul>}
      </>}
      {tab === "feed" && <>
        <BrowserNotifyOffer />
        {notices.isPending ? <p className={styles.empty}>{t("알림을 불러오고 있어요.", "Loading the notices.")}</p>
          : feed.length === 0 && <p className={styles.empty}>{t("받은 알림이 없어요.", "No notices yet.")}</p>}
        {byDay.map(([date, entries]) => <section key={date} className={styles.day} aria-label={dayHead(date)}>
          <h4 className={styles.dayHead}>{dayHead(date)}</h4>
          {entries.map((entry) => entry.kind === "notice" ? noticeEntry(entry.notice) : entry.kind === "proposal" ? proposalEntry(entry) : versionEntry(entry.change))}
        </section>)}
        {feed.length > shownFeed.length && <p className={styles.cut}>{t(`최근 ${shownFeed.length}개만 보여요. 전체 ${feed.length}개 중 ${feed.length - shownFeed.length}개는 화면에 없어요.`,
          `Showing the latest ${shownFeed.length}. ${feed.length - shownFeed.length} of ${feed.length} are not on screen.`)}</p>}
      </>}
      {tab === "service" && <ServiceNoticeTab />}
    </div>
  </div>;
}

const entryKey = (entry: FeedEntry | null) => !entry ? null : entry.kind === "notice" ? entry.notice.key : entry.kind === "proposal" ? entry.proposalId : null;
const carries = (entry: FeedEntry, key: string) => entry.kind === "notice" ? entry.notice.key === key : entry.kind === "proposal" && entry.notices.some((notice) => notice.key === key);

/**
 * 「소식」 위 한 줄 — 브라우저(운영체제) 알림 켜기. `[2026-10-16 사용자 지시]`
 * 권한은 단추를 눌렀을 때만 묻는다. 켜면 여행 화면이 뒤에 있을 때도 새 알림이 운영체제 알림으로 뜬다(탭을 닫으면 오지 않는다).
 */
const noSubscribe = () => () => undefined;

function BrowserNotifyOffer() {
  const t = useT();
  // 서버에서 그릴 때는 「없음」 — 브라우저에서만 실제 권한을 읽는다(그리기 불일치를 막는다). 단추로 바꾼 값이 있으면 그것.
  const current = useSyncExternalStore(noSubscribe, browserNotifyState, () => "unsupported" as BrowserNotifyState);
  const [asked, setState] = useState<BrowserNotifyState | null>(null);
  const state = asked ?? current;
  if (state === "unsupported") return null;
  if (state === "granted") return <p className={styles.empty}>{t("브라우저 알림이 켜져 있어요. 이 창을 내려 둬도 새 알림이 떠요.", "Browser notifications are on. New notices pop up even when this window is in the background.")}</p>;
  if (state === "denied") return <p className={styles.empty}>{t("브라우저에서 이 사이트 알림이 막혀 있어요. 주소창 왼쪽 자물쇠 → 알림 → 허용으로 바꿀 수 있어요.", "This site's notifications are blocked in your browser. Allow them from the lock icon left of the address bar.")}</p>;
  return <p className={styles.empty}>{t("창을 내려 둬도 알림을 받으려면", "To get notices while this window is in the background,")}{" "}
    <Button onClick={() => void askBrowserNotify().then(setState)}>{t("브라우저 알림 켜기", "Turn on browser notifications")}</Button></p>;
}
