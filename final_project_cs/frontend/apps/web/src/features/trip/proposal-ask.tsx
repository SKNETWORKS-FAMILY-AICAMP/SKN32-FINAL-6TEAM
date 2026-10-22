"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import sq from "@/features/plan-check/stop-question.module.css";
import type { Translate } from "@/lib/i18n";
import { LiveError } from "@/lib/live/client";
import { chooseProposal } from "@/lib/live/extras";
import { seoul } from "@/lib/live/gateway";
import { useSettings, useT } from "@/lib/settings";
import type { OpenChoice } from "./attention";
import { noticeWhen } from "./trip-attention";
import { tripKey } from "./use-trip";
import { noticesKey, proposalsKey } from "./use-trip-extras";
import styles from "./trip-screen.module.css";

/**
 * Server contract (2026-09-29 — the notice center's): a proposal with one of these reasons and no options asks "change it?" first; answering with `CONSENT_KEY` makes the server
 * find the options then and fill the same proposal (`pending._consented` — finding them checks each candidate outside, so it is not done before the customer asks).
 */
export const ASK_FIRST_REASONS = ["indoor_unknown", "forecast_advisory"];
export const CONSENT_KEY = "change";

/** A choice answered on a stop's detail — the notice center's call (`POST …/proposals/{id}/choose`). The trip, the choices and the notices are read again after it. */
export function useChooseProposal(tripId: string) {
  const { language } = useSettings();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ proposalId, key }: { proposalId: string; key: string | null }) => chooseProposal(tripId, proposalId, key, language),
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: tripKey(tripId, language) });
      void queryClient.invalidateQueries({ queryKey: proposalsKey(tripId, language) });
      void queryClient.invalidateQueries({ queryKey: noticesKey(tripId, language) });
    },
  });
}

/**
 * What came of a choice, in the notice center's words — null while it goes on (`options`: the options stand on the card now).
 * `[2026-10-22 ST4F-723 · 실서버 확인]` The server answers a picked option with `chosen` (`pending.py` choose), not `adjusted` — the screen showed 「처리 결과: chosen」. The notice center,
 * a stop's detail and the chat all say the result with this one function.
 */
export function chooseOutcome(status: string | undefined, t: Translate): string | null {
  if (status === "options") return null;
  if (status === "no_alternate") return t("바꿀 수 있는 다른 곳을 찾지 못했어요 — 원래 일정을 그대로 둡니다.", "No other place was found — the plan stays as it is.");
  if (status === "chosen") return t("고르신 곳으로 일정을 바꿨어요.", "Your plan now uses the place you picked.");
  if (status === "kept") return t("지금 일정을 그대로 두었어요.", "Your plan stays as it is.");
  return t(`처리 결과: ${status ?? "-"}`, `Result: ${status ?? "-"}`);
}

/** A refused choice, in the notice center's words: decided already or the trip moved on (nothing changed — the state was read again), else the server's own message. */
export function chooseFailure(error: Error, t: Translate): string {
  return error instanceof LiveError && (error.code === "already_decided" || error.code === "stale")
    ? t("이미 정해졌거나 그 사이 일정이 바뀌었어요. 아무것도 바뀌지 않았고, 지금 상태를 다시 불러왔어요.", "It was already decided or the trip changed meanwhile. Nothing was changed; we reloaded the current state.")
    : error.message;
}

/**
 * `[2026-10-21 사용자 결정 — ST4F-704 · 목업 tripilot-trip-card-proposal-mark.html ②③]` The choice the server waits for, inside the stop's card on its detail — the plan check's question
 * (`stop-question.module.css`): what it is (「선택 요청」), the server's sentence, the options (「예보에 맞게 일정 변경」 · 「다른 곳 찾아보기」 first when the server asks before finding any),
 * 「직접 수정」 (the edit on this stop with 「직접 고치기」 open) and 「지금 일정 그대로 두기」, and until when. Only the server's words and values; where it sent no sentence, the center's line.
 */
export function ProposalAsk({ choice, busy, onChoose, onEdit }: {
  choice: OpenChoice; busy: boolean; onChoose: (key: string | null) => void; onEdit: () => void;
}) {
  const t = useT();
  const { proposal, text } = choice;
  const titleId = `trip-proposal-ask-${proposal.id}`;
  const asksFirst = ASK_FIRST_REASONS.includes(proposal.reason) && proposal.options.length === 0;
  return <section className={`${sq.box} ${styles.detailAsk}`} aria-labelledby={titleId} data-proposal-ask={proposal.id}>
    <span className={sq.kind}>{t("선택 요청", "Your choice")}</span>
    <p id={titleId} className={sq.question}>{text ?? t("이 일정을 어떻게 할지 골라 주세요.", "Choose what to do with this stop.")}</p>
    {(asksFirst || proposal.options.length > 0) && <div className={sq.options}>
      {asksFirst && <button type="button" className={sq.option} disabled={busy} onClick={() => onChoose(CONSENT_KEY)}>
        <span className={sq.optionTop}>{proposal.reason === "forecast_advisory" ? t("예보에 맞게 일정 변경", "Adjust the plan for the forecast") : t("다른 곳 찾아보기", "Show other places")}</span></button>}
      {proposal.options.map((option) => <button key={option.key} type="button" className={sq.option} disabled={busy} onClick={() => onChoose(option.key)}>
        <span className={sq.optionTop}>{option.note ? `${option.note} · ` : ""}{option.startsAt ? `${seoul(option.startsAt).time} ` : ""}{option.name}</span>
        {option.warnings.length > 0 && <span className={sq.line}>{option.warnings.join(" · ")}</span>}</button>)}
    </div>}
    <div className={sq.buttons} data-two>
      <button type="button" className={sq.button} disabled={busy} onClick={onEdit}>{t("직접 수정", "Edit myself")}</button>
      <button type="button" className={sq.button} disabled={busy} onClick={() => onChoose(null)}>{t("지금 일정 그대로 두기", "Keep the plan as it is")}</button>
    </div>
    {(proposal.safety || proposal.expiresAt) && <p className={styles.detailAskMeta}>
      {proposal.safety ? t("안전과 관련된 선택이에요. ", "This one is about safety. ") : ""}{proposal.expiresAt ? t(`${noticeWhen(proposal.expiresAt)} 까지`, `Until ${noticeWhen(proposal.expiresAt)}`) : ""}</p>}
  </section>;
}
