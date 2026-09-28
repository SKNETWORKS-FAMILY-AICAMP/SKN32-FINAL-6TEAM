"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Badge, Button } from "@/components/ui";
import { seoul } from "@/lib/live/gateway";
import { LiveError } from "@/lib/live/client";
import { chooseProposal } from "@/lib/live/extras";
import { useSettings, useT } from "@/lib/settings";
import { openChoices, recentNotices } from "./attention";
import type { Trip } from "./model";
import { tripKey } from "./use-trip";
import { noticesKey, proposalsKey, useNotices, useProposals } from "./use-trip-extras";
import styles from "./trip-attention.module.css";

const NOTICE_LABEL: Record<string, [string, string]> = {
  guidance: ["안내", "Guidance"], proposal_request: ["선택 요청", "Your choice"],
  safety_alert: ["안전 알림", "Safety alert"], change_notice: ["변경 알림", "Change"],
};

const when = (iso: string) => { const at = seoul(iso); return `${at.date} ${at.time}`; };

/**
 * Live only: what the server is waiting for, found and sent about this trip.
 * ★Every sentence here is the server's — its notice text, its warning reason, its history. Where it sent none,
 * the screen shows the server's own code instead of writing a line of its own.
 */
export function TripAttention({ trip }: { trip: Trip }) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const proposals = useProposals(trip.id);
  const notices = useNotices(trip.id);
  const choices = openChoices(proposals.data ?? [], notices.data ?? [], trip.stops);
  const { shown, total, hidden } = recentNotices(notices.data ?? []);

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: tripKey(trip.id, language) });
    void queryClient.invalidateQueries({ queryKey: proposalsKey(trip.id, language) });
    void queryClient.invalidateQueries({ queryKey: noticesKey(trip.id, language) });
  };
  const choose = useMutation({
    mutationFn: ({ proposalId, key }: { proposalId: string; key: string | null }) => chooseProposal(trip.id, proposalId, key, language),
    // Refused because it was already decided or the trip moved on: nothing changed, so re-read what is true now.
    onSettled: refresh,
  });

  const readError = proposals.error ?? notices.error;
  const warnings = trip.warnings ?? [];
  const history = trip.history ?? [];

  return <div className={styles.wrap}>
    {trip.planUrl && <p className={styles.plan}><a href={trip.planUrl} target="_blank" rel="noopener noreferrer">{t("여행계획서 열기", "Open your trip plan")}</a><span>{t("로그인 없이 열리는 내 여행 링크예요. 링크를 아는 사람은 누구나 볼 수 있어요.", "This link opens without logging in. Anyone who has it can view your plan.")}</span></p>}
    {readError && <div className={styles.error} role="alert">{t("선택과 알림을 읽지 못했어요 — ", "Could not read your choices and notices — ")}{readError instanceof Error ? readError.message : String(readError)}</div>}

    {choices.length > 0 && <section className={`${styles.card} ${styles.ask}`} aria-labelledby="trip-choices">
      <h2 id="trip-choices">{t("선택이 필요해요", "Your choice is needed")}<Badge tone="warning">{choices.length}</Badge></h2>
      {choices.map(({ proposal, stop, text }) => <div key={proposal.id} className={styles.choice}>
        <strong>{stop ? `${stop.time} · ${stop.title}` : t("이 여행의 일정", "A stop on this trip")}</strong>
        <p>{text ?? t(`서버가 이 일정에 대한 선택을 기다려요 (이유: ${proposal.reason}).`, `The server is waiting for your choice on this stop (reason: ${proposal.reason}).`)}</p>
        <div className={styles.options}>
          {proposal.options.map((option) => <Button key={option.key} variant="primary" disabled={choose.isPending}
            onClick={() => choose.mutate({ proposalId: proposal.id, key: option.key })}>{option.startsAt ? `${seoul(option.startsAt).time} ` : ""}{option.name}</Button>)}
          <Button disabled={choose.isPending} onClick={() => choose.mutate({ proposalId: proposal.id, key: null })}>{t("지금 일정 그대로 두기", "Keep the plan as it is")}</Button>
        </div>
        {(proposal.expiresAt || proposal.safety) && <p className={styles.meta}>{proposal.safety ? t("안전과 관련된 선택이에요. ", "This one is about safety. ") : ""}{proposal.expiresAt ? t(`${when(proposal.expiresAt)} 까지`, `Until ${when(proposal.expiresAt)}`) : ""}</p>}
      </div>)}
      {choose.error && <div className={styles.error} role="alert">{choose.error instanceof LiveError && (choose.error.code === "already_decided" || choose.error.code === "stale")
        ? t("이미 정해졌거나 그 사이 일정이 바뀌었어요. 아무것도 바뀌지 않았고, 지금 상태를 다시 불러왔어요.", "It was already decided or the trip changed meanwhile. Nothing was changed; we reloaded the current state.")
        : choose.error.message}</div>}
      {choose.data?.status && !choose.error && <p className={styles.meta}>{t(`처리 결과: ${choose.data.status}`, `Result: ${choose.data.status}`)}</p>}
    </section>}

    {warnings.length > 0 && <section className={`${styles.card} ${styles.warn}`} aria-labelledby="trip-warnings">
      <h2 id="trip-warnings">{t("살펴볼 점", "Worth a look")}<Badge tone="warning">{warnings.length}</Badge></h2>
      <ul className={styles.list}>{warnings.map((warning, index) => <li key={`${warning.code}-${warning.date ?? ""}-${index}`}>
        {warning.date && <span className={styles.tag}>{warning.date}</span>}{warning.reason}
        {warning.remedy && <span className={styles.remedy}>{warning.remedy}</span>}
      </li>)}</ul>
    </section>}

    {total > 0 && <details className={`${styles.card} ${styles.details}`}>
      <summary>{t(`받은 알림 ${total}개`, `Notices (${total})`)}</summary>
      <ul className={styles.list}>{shown.map((notice) => {
        const label = NOTICE_LABEL[notice.type];
        return <li key={notice.key}>
          <span className={styles.tag}>{label ? t(label[0], label[1]) : notice.type}</span>{when(notice.at)}
          <span className={styles.remedy}>{notice.text ?? t("서버가 문장을 보내지 않았어요.", "The server sent no text.")}</span>
        </li>;
      })}</ul>
      {hidden > 0 && <p className={styles.cut}>{t(`최근 ${shown.length}개만 보여요. 전체 ${total}개 중 ${hidden}개는 화면에 없어요.`, `Showing the latest ${shown.length}. ${hidden} of ${total} are not on screen.`)}</p>}
    </details>}

    {history.length > 0 && <details className={`${styles.card} ${styles.details}`}>
      <summary>{t(`변경 이력 ${history.length}개`, `Change history (${history.length})`)}</summary>
      <ul className={styles.list}>{[...history].reverse().map((entry) => <li key={entry.version}>
        <span className={styles.tag}>v{entry.version}</span>{entry.at} · {entry.reason === "created" ? t("처음 등록", "Registered") : entry.reason}
        {entry.causes.map((cause) => <span key={cause} className={styles.remedy}>{cause}</span>)}
      </li>)}</ul>
    </details>}
  </div>;
}
