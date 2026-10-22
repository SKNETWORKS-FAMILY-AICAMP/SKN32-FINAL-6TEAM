"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, CloudRain, OctagonAlert, Sparkles } from "lucide-react";
import { chooseProposal, type Notice, type Proposal } from "@/lib/live/extras";
import { LiveError } from "@/lib/live/client";
import { seoul } from "@/lib/live/gateway";
import { useSettings, useT } from "@/lib/settings";
import { LinkedText } from "./linked-text";
import { openChoices, type OpenChoice } from "./attention";
import { proposalAvailable } from "./trip-chat-records";
import { noticesKey, proposalsKey, useProposals } from "./use-trip-extras";
import { tripKey } from "./use-trip";
import { useSlide } from "./use-slide";
import type { Trip } from "./model";
import c from "./trip-chat.module.css";

/** `[2026-10-22 ST4F-719 · 목업 ⓑ]` A notice in the chat: a card with a band of its kind's colour (안전 알림 red · 선택 요청 amber · 안내 grey · 변경 알림 blue) and when it came. */
export function ChatNotice({ notice }: { notice: Notice }) {
  const t = useT();
  const at = seoul(notice.at);
  const label = notice.type === "safety_alert" ? t("안전 알림", "Safety alert")
    : notice.type === "proposal_request" ? t("선택 요청", "Your choice")
    : notice.type === "guidance" ? t("안내", "Guidance") : t("변경 알림", "Change notice");
  const tone = notice.type === "safety_alert" ? "error" : notice.type === "proposal_request" ? "warning" : notice.type === "guidance" ? "muted" : undefined;
  const Icon = notice.type === "safety_alert" ? OctagonAlert : notice.type === "proposal_request" ? CloudRain : Bell;
  return <article className={`${c.card} ${c.notice}`} data-role="assistant" data-tone={tone} data-trip-notice={notice.key}>
    <p className={c.noticeHead}><Icon size={15} strokeWidth={1.9} aria-hidden="true" />{label}<time dateTime={notice.at}>{at.date} {at.time}</time></p>
    <p className={c.body}>{notice.text ? <LinkedText text={notice.text} mapLabel={t("지도 앱으로 열기", "Open in maps app")} />
      : t("이 알림의 본문을 받지 못했어요. 알림을 다시 읽어 주세요.", "This notice has no text. Reload notices.")}</p>
  </article>;
}

/** Buttons use the same authoritative proposal and choose API as the notice center. */
export function ChatProposalChoices({ trip, notices }: { trip: Trip; notices: Notice[] }) {
  const { language } = useSettings();
  const t = useT();
  const client = useQueryClient();
  const proposals = useProposals(trip.id);
  const refresh = () => {
    void client.invalidateQueries({ queryKey: tripKey(trip.id, language) });
    void client.invalidateQueries({ queryKey: proposalsKey(trip.id, language) });
    void client.invalidateQueries({ queryKey: noticesKey(trip.id, language) });
  };
  const choose = useMutation({
    mutationFn: ({ proposalId, key }: { proposalId: string; key: string | null }) => chooseProposal(trip.id, proposalId, key, language),
    onSettled: refresh,
  });
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
    {choose.error && <p className={`${c.status} ${c.statusError}`} role="alert">{choose.error instanceof LiveError && ["already_decided", "stale", "stale_itinerary"].includes(choose.error.code)
      ? t("이미 정해졌거나 일정이 바뀌었어요. 현재 상태를 다시 불러왔어요.", "The choice was already made or the plan changed. The current state has been reloaded.")
      : choose.error.message}</p>}
    {choose.data?.status && !choose.error && <p className={c.status} role="status">{
      choose.data.status === "adjusted" ? t("고르신 대안을 일정에 적용했어요.", "Your chosen alternative was applied.")
      : choose.data.status === "kept" ? t("현재 일정을 그대로 두었어요.", "The current plan was kept.")
      : choose.data.status === "options" ? t("확보한 대안에서 골라 주세요.", "Choose one of the available alternatives.")
      : choose.data.status === "no_alternate" ? t("이번 확인에서 조건을 만족한 대안을 확보하지 못했어요. 현재 일정은 그대로예요.", "No alternative met the current conditions. The current plan is kept.")
      : t("선택 결과를 받았어요. 최신 일정과 제안을 다시 읽고 있어요.", "The result arrived. Reloading the current plan and proposals.")}</p>}
  </section>;
}

/**
 * `[2026-10-22 ST4F-719 · 목업 ⓑ]` One proposal to choose from: its options as cards in a row that slides sideways (`data-no-swipe` — the pane's swipe back does not start there), then what
 * else can be done (look for others · keep the plan). A forecast or indoor question starts with no options — 「예보에 맞게 일정 변경」 · 「다른 곳 찾아보기」 asks the server for them.
 */
function ProposalCard({ proposal, title, time, available, busy, onReload, onChoose }: { proposal: Proposal; title: string | null; time: string | null; available: boolean; busy: boolean;
  onReload: () => void; onChoose: (key: string | null) => void }) {
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
    </div>
  </article>;
}
