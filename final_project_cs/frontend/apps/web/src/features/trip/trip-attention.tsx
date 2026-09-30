"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Badge, Button } from "@/components/ui";
import { seoul } from "@/lib/live/gateway";
import { LiveError } from "@/lib/live/client";
import { chooseProposal, undoChange, type Notice } from "@/lib/live/extras";
import { useSettings, useT } from "@/lib/settings";
import { openChoices, recentNotices, undoableChange } from "./attention";
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
/** Server contract (2026-09-29): a proposal with this reason and no options asks "change it?"; answering with this key makes
 *  the server compute options and fill the same proposal (reason becomes `indoor_unknown_options`). */
const CONSENT_REASON = "indoor_unknown";
const CONSENT_KEY = "change";

export function TripAttention({ trip }: { trip: Trip }) {
  const t = useT();
  const { language } = useSettings();
  const queryClient = useQueryClient();
  const proposals = useProposals(trip.id);
  const notices = useNotices(trip.id);
  const choices = openChoices(proposals.data ?? [], notices.data ?? [], trip.stops);
  const { shown, total, hidden } = recentNotices(notices.data ?? []);
  const undoable = undoableChange(notices.data ?? [], trip.version);

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

  // ★Undo an automatic change (only customers who chose "change it automatically" get those). 409 = the plan moved on.
  const undo = useMutation({
    mutationFn: (notice: Notice) => undoChange(trip.id, notice.rollback!, language),
    onSettled: refresh,
  });

  const readError = proposals.error ?? notices.error;
  const warnings = trip.warnings ?? [];
  const history = trip.history ?? [];

  return <div className={styles.wrap}>
    {trip.planUrl && <p className={styles.plan}><a href={trip.planUrl} target="_blank" rel="noopener noreferrer">{t("여행계획서 열기", "Open your trip plan")}</a><span>{t("로그인 없이 열리는 내 여행 링크예요. 링크를 아는 사람은 누구나 볼 수 있어요.", "This link opens without logging in. Anyone who has it can view your plan.")}</span></p>}
    {readError && <div className={styles.error} role="alert">{t("선택과 알림을 읽지 못했어요 — ", "Could not read your choices and notices — ")}{readError instanceof Error ? readError.message : String(readError)}</div>}

    {undoable && <section className={`${styles.card} ${styles.ask}`} aria-labelledby="trip-undo">
      <h2 id="trip-undo">{t("자동으로 바꾼 일정", "Changed automatically")}</h2>
      <p>{undoable.text ?? t("서버가 문장을 보내지 않았어요.", "The server sent no text.")}</p>
      <div className={styles.options}>
        <Button disabled={undo.isPending} onClick={() => undo.mutate(undoable)}>{undo.isPending ? t("되돌리는 중…", "Undoing…") : t("되돌리기", "Undo")}</Button>
      </div>
    </section>}
    {undo.error && <div className={styles.error} role="alert">{undo.error instanceof LiveError && ["stale_itinerary", "stale", "invalid_version"].includes(undo.error.code)
      ? t("그 사이 일정이 다시 바뀌어 되돌리지 않았어요. 지금 상태를 다시 불러왔어요.", "The plan changed again meanwhile, so nothing was undone. We reloaded the current state.")
      : undo.error.message}</div>}
    {undo.data && !undo.error && <p className={styles.meta}>{undo.data.answer ?? t("바꾸기 전 일정으로 되돌렸어요.", "Your plan is back to how it was.")}</p>}

    {choices.length > 0 && <section className={`${styles.card} ${styles.ask}`} aria-labelledby="trip-choices">
      <h2 id="trip-choices">{t("선택이 필요해요", "Your choice is needed")}<Badge tone="warning">{choices.length}</Badge></h2>
      {choices.map(({ proposal, stop, text }) => <div key={proposal.id} className={styles.choice}>
        <strong>{stop ? `${stop.time} · ${stop.title}` : t("이 여행의 일정", "A stop on this trip")}</strong>
        <p>{text ?? t(`서버가 이 일정에 대한 선택을 기다려요 (이유: ${proposal.reason}).`, `The server is waiting for your choice on this stop (reason: ${proposal.reason}).`)}</p>
        <div className={styles.options}>
          {/* 2026-09-29: "should we change it?" first (indoor/outdoor unknown). The server computes options only after "change". */}
          {proposal.reason === CONSENT_REASON && proposal.options.length === 0 && <Button variant="primary" disabled={choose.isPending}
            onClick={() => choose.mutate({ proposalId: proposal.id, key: CONSENT_KEY })}>{t("바꿔 줘 — 다른 곳 보기", "Change it — show other places")}</Button>}
          {proposal.options.map((option) => <Button key={option.key} variant="primary" disabled={choose.isPending}
            onClick={() => choose.mutate({ proposalId: proposal.id, key: option.key })}>{option.note ? `${option.note} · ` : ""}{option.startsAt ? `${seoul(option.startsAt).time} ` : ""}{option.name}
            {option.warnings.length > 0 && <small className={styles.optionWarning}>{option.warnings.join(" · ")}</small>}</Button>)}
          <Button disabled={choose.isPending} onClick={() => choose.mutate({ proposalId: proposal.id, key: null })}>{t("지금 일정 그대로 두기", "Keep the plan as it is")}</Button>
        </div>
        {(proposal.expiresAt || proposal.safety) && <p className={styles.meta}>{proposal.safety ? t("안전과 관련된 선택이에요. ", "This one is about safety. ") : ""}{proposal.expiresAt ? t(`${when(proposal.expiresAt)} 까지`, `Until ${when(proposal.expiresAt)}`) : ""}</p>}
      </div>)}
    </section>}
    {/* ★Outside the choices card: after a decision the server closes the proposal and the card goes away,
         but what happened (no other place / already decided) must still be said. */}
    {choose.error && <div className={styles.error} role="alert">{choose.error instanceof LiveError && (choose.error.code === "already_decided" || choose.error.code === "stale")
        ? t("이미 정해졌거나 그 사이 일정이 바뀌었어요. 아무것도 바뀌지 않았고, 지금 상태를 다시 불러왔어요.", "It was already decided or the trip changed meanwhile. Nothing was changed; we reloaded the current state.")
        : choose.error.message}</div>}
    {choose.data?.status && !choose.error && <p className={styles.meta}>{
        choose.data.status === "options" ? t("다른 곳을 찾았어요 — 위에서 골라 주세요.", "Found other places — pick one above.")
          : choose.data.status === "no_alternate" ? t("바꿀 수 있는 다른 곳을 찾지 못했어요 — 원래 일정을 그대로 둡니다.", "No other place was found — the plan stays as it is.")
          : choose.data.status === "adjusted" ? t("고르신 곳으로 일정을 바꿨어요.", "Your plan now uses the place you picked.")
          : choose.data.status === "kept" ? t("지금 일정을 그대로 두었어요.", "Your plan stays as it is.")
            : t(`처리 결과: ${choose.data.status}`, `Result: ${choose.data.status}`)}</p>}

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
