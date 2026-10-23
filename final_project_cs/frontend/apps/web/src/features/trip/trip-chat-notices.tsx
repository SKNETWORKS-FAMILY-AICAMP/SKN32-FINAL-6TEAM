"use client";

import type { ReactNode } from "react";
import { Bell, CloudRain, OctagonAlert, Sparkles } from "lucide-react";
import type { Notice, Proposal, ProposalOption } from "@/lib/live/extras";
import { seoul } from "@/lib/live/gateway";
import { useT } from "@/lib/settings";
import { LinkedText } from "./linked-text";
import { openChoices, proposalText, type OpenChoice } from "./attention";
import { proposalAvailable } from "./trip-chat-records";
import { chooseFailure, chooseOutcome, useChooseProposal } from "./proposal-ask";
import { useProposals } from "./use-trip-extras";
import { useSlide } from "./use-slide";
import type { Trip } from "./model";
import c from "./trip-chat.module.css";

/** A notice's kind in the cards' words and colour (안전 알림 red · 선택 요청 amber · 안내 grey · 변경 알림 blue). */
export function noticeKind(type: string, t: ReturnType<typeof useT>): { label: string; tone: "error" | "warning" | "muted" | undefined; Icon: typeof Bell } {
  if (type === "safety_alert") return { label: t("안전 알림", "Safety alert"), tone: "error", Icon: OctagonAlert };
  if (type === "proposal_request") return { label: t("선택 요청", "Your choice"), tone: "warning", Icon: CloudRain };
  if (type === "guidance") return { label: t("안내", "Guidance"), tone: "muted", Icon: Bell };
  return { label: t("변경 알림", "Change notice"), tone: undefined, Icon: Bell };
}

/**
 * `[2026-10-22 사용자 결정 — ST4F-723 카드 ⓑ]` A notice as a card — the chat's, and the notice center's (the same part): a band of its kind's colour with its name, what state it is in,
 * when it came; then what is in it.
 */
export function NoticeCard({ tone, Icon, label, state, unread, at, when, children, ...rest }: {
  tone: "error" | "warning" | "muted" | undefined; Icon: typeof Bell; label: string; state?: { text: string; done?: boolean } | null; unread?: string | null;
  at: string; when: string; children: ReactNode } & Record<`data-${string}`, string | boolean | undefined>) {
  return <article className={`${c.card} ${c.notice}`} data-role="assistant" data-tone={tone} {...rest}>
    <p className={c.noticeHead}><Icon size={15} strokeWidth={1.9} aria-hidden="true" />{label}
      {state && <span className={c.noticeState} data-done={state.done || undefined}>{state.text}</span>}
      {unread && <span className={c.noticeNew} role="img" aria-label={unread} />}
      <time dateTime={at}>{when}</time></p>
    {children}
  </article>;
}

/** `[2026-10-22 ST4F-719 · 목업 ⓑ]` A notice in the chat. `cover`: what a card drawn below already shows — the server's proposal sentence leaves it out (`proposalText`). */
export function ChatNotice({ notice, cover }: { notice: Notice; cover?: readonly ProposalOption[] }) {
  const t = useT();
  const at = seoul(notice.at);
  const kind = noticeKind(notice.type, t);
  const text = notice.text && cover ? proposalText(notice.text, { options: cover }) : notice.text;
  return <NoticeCard {...kind} at={notice.at} when={`${at.date} ${at.time}`} data-trip-notice={notice.key}>
    <p className={c.body}>{text ? <LinkedText text={text} mapLabel={t("지도 앱으로 열기", "Open in maps app")} />
      : t("이 알림의 본문을 받지 못했어요. 알림을 다시 읽어 주세요.", "This notice has no text. Reload notices.")}</p>
  </NoticeCard>;
}

/** Buttons use the same authoritative proposal and choose API as the notice center. */
export function ChatProposalChoices({ trip, notices }: { trip: Trip; notices: Notice[] }) {
  const t = useT();
  const proposals = useProposals(trip.id);
  const choose = useChooseProposal(trip.id, trip.version);
  const choices = openChoices(proposals.data ?? [], notices, trip.stops);
  const availableChoices: OpenChoice[] = [];
  const unavailableChoices: OpenChoice[] = [];
  for (const choice of choices) {
    const available = Boolean(choice.stop) && proposalAvailable(choice.proposal, trip.version);
    (available ? availableChoices : unavailableChoices).push(choice);
  }
  const renderChoice = ({ proposal, stop }: OpenChoice, available: boolean) => <ProposalCard key={proposal.id} proposal={proposal} title={stop?.title ?? null} time={stop?.time ?? null}
    available={available} busy={choose.isPending} onReload={() => void proposals.refetch()} onChoose={(key) => choose.mutate({ proposalId: proposal.id, key })} />;
  return <section aria-label={t("채팅에서 대안 선택", "Choose an alternative in chat")}>
    {proposals.error && <p className={`${c.status} ${c.statusError}`} role="alert">{t("대안 제안을 읽지 못했어요. 다시 불러와 주세요.", "Proposals could not be loaded. Try again.")}
      <button type="button" className={c.chip} onClick={() => void proposals.refetch()}>{t("대안 다시 읽기", "Reload alternatives")}</button></p>}
    {unavailableChoices.length > 0 && <details className={c.older} data-chat-unavailable>
      <summary className={c.chip}>{t(`이전 대안 ${unavailableChoices.length}개 보기`, `View ${unavailableChoices.length} previous alternatives`)}</summary>
      {unavailableChoices.map(choice => renderChoice(choice, false))}
    </details>}
    {availableChoices.map(choice => renderChoice(choice, true))}
    {choose.error && <p className={`${c.status} ${c.statusError}`} role="alert">{chooseFailure(choose.error, t)}</p>}
    {/* `[2026-10-22 사용자 결정 — ST4F-723]` The options coming in say nothing (「확보한 대안에서 골라 주세요.」 is gone) — they stand on the card. */}
    {choose.data && !choose.error && chooseOutcome(choose.data.status, t) && <p className={c.status} role="status">{chooseOutcome(choose.data.status, t)}</p>}
  </section>;
}

/**
 * `[2026-10-22 ST4F-719 · 목업 ⓑ]` One proposal to choose from: its options as cards in a row that slides sideways (`data-no-swipe` — the pane's swipe back does not start there), then what
 * else can be done (look for others · keep the plan). A forecast or indoor question starts with no options — 「예보에 맞게 일정 변경」 · 「다른 곳 찾아보기」 asks the server for them.
 * `[2026-10-22 ST4F-723]` The notice center's 「할 일」 draws the same card; `meta` is a line it adds at the foot (until when the server waits for the answer).
 */
export function ProposalCard({ proposal, title, time, available, busy, onReload, onChoose, meta }: { proposal: Proposal; title: string | null; time: string | null; available: boolean;
  busy: boolean; onReload: () => void; onChoose: (key: string | null) => void; meta?: string | null }) {
  const t = useT();
  const row = useSlide<HTMLDivElement>(`${proposal.id}:${proposal.options.length}`);
  const search = ["indoor_unknown", "forecast_advisory"].includes(proposal.reason) && proposal.options.length === 0;
  return <article className={c.card} data-role="assistant" data-chat-proposal={proposal.id}>
    <div className={c.head}><span className={c.badge} data-tone="warning"><Sparkles size={13} strokeWidth={2.2} aria-hidden="true" />{t("선택할 대안", "Alternatives to choose")}</span>
      {title && <span className={c.when}>{title}{time ? ` ${time}` : ""}</span>}</div>
    {!available && <p className={c.body} role="status">{t("이 제안은 이전 일정이거나 유효 시간이 지났어요. 최신 제안을 다시 읽어 주세요.", "This proposal is outdated or expired. Reload the current proposals.")}
      <button type="button" className={c.chip} onClick={onReload}>{t("대안 다시 읽기", "Reload alternatives")}</button></p>}
    {proposal.options.length > 0 && <div ref={row} className={`${c.carousel} ${c.slide}`} data-slide data-no-swipe>
      {proposal.options.map((option) => <button key={option.key} type="button" className={c.option} disabled={!available || busy} onClick={() => onChoose(option.key)}>
        <b>{option.name}</b><span>{[option.note, option.startsAt ? seoul(option.startsAt).time : ""].filter(Boolean).join(" · ")}</span>
        {option.warnings.length > 0 && <small>{option.warnings.join(" · ")}</small>}</button>)}
    </div>}
    <div className={c.foot}>
      {search && <button type="button" className={c.button} data-primary disabled={!available || busy} onClick={() => onChoose("change")}>
        {proposal.reason === "forecast_advisory" && <CloudRain size={15} strokeWidth={1.8} aria-hidden="true" />}
        {proposal.reason === "forecast_advisory" ? t("예보에 맞게 일정 변경", "Adjust the plan for the forecast") : t("다른 곳 찾아보기", "Find other places")}</button>}
      <button type="button" className={c.button} disabled={!available || busy} onClick={() => onChoose(null)}>{t("지금 일정 그대로 두기", "Keep the current plan")}</button>
      {meta && <span className={c.footTitle}>{meta}</span>}
    </div>
  </article>;
}
