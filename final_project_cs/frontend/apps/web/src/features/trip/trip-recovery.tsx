"use client";

import { useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { CircleHelp, HeartHandshake, ShieldCheck, TriangleAlert } from "lucide-react";
import { useAppToast } from "@/components/app-toast";
import { Button } from "@/components/ui";
import { seoul } from "@/lib/live/gateway";
import {
  chooseRecovery, NO_CANDIDATE_STATUSES, type ItemStatus, type Recovery, type RecoveryAnswer, type RecoveryChoice, type RecoveryQuestionKey, type RecoveryResult,
} from "@/lib/live/recovery";
import { useSettings, useT } from "@/lib/settings";
import type { Trip } from "./model";
import styles from "./trip-recovery.module.css";

/** The words of an answer (the questions and their sentences are the server's; only these three words are ours). */
const ANSWER_WORDS: Record<RecoveryAnswer, [string, string]> = { yes: ["예", "Yes"], no: ["아니요", "No"], unknown: ["잘 모르겠어요", "Not sure"] };

/** How a stop's status is said. ★「범위 모름」 is its own word: an unknown is never shown as 「영향 없음」. */
const STATUS_WORDS: Record<ItemStatus, [string, string]> = { affected: ["영향 확정", "Affected"], unknown: ["범위 모름", "Not known"], unaffected: ["영향 없음", "Not affected"] };
const STATUS_ICON = { affected: TriangleAlert, unknown: CircleHelp, unaffected: ShieldCheck } as const;

/**
 * `[2026-10-06 사용자 결정 — 재난 뒤 다시 시작]` Right after the customer lifts a disaster pause (and for 72 hours): what is known (with its source) and what is NOT known, the status of every remaining stop, and three
 * ways to go on - 「그대로 이어가기」 · 「영향받은 것만 바꾸기」(recommended) · 「남은 일정 새로 받기」 - with 「오늘은 가볍게」 and two questions the customer may answer.
 * ★We do not decide: nothing is chosen for them, the density is not lowered on our own, an unknown is never drawn as 「영향 없음」, and what we cannot do (a booking, postponing, cancelling) is said as the server wrote
 * it. A choice only RECORDS; 「영향받은 것만 바꾸기」 makes proposals the customer may take or leave (the plan does not change by this press). Every sentence about the disaster is the server's.
 */
export function RecoveryPanel({ trip, recovery, onChosen }: { trip: Trip; recovery: Recovery; onChosen: () => void }) {
  const t = useT();
  const { language } = useSettings();
  const toast = useAppToast();
  const id = useId();
  const [choice, setChoice] = useState<RecoveryChoice | null>(recovery.chosen?.choice ?? null);
  const [lighter, setLighter] = useState(recovery.chosen?.lighterDay ?? recovery.lighterDay?.byDefault ?? false);
  const [answers, setAnswers] = useState<Partial<Record<RecoveryQuestionKey, RecoveryAnswer>>>(recovery.chosen?.answers ?? {});
  const [editing, setEditing] = useState(recovery.chosen === null);
  const [result, setResult] = useState<RecoveryResult | null>(null);

  const send = useMutation({
    mutationFn: () => chooseRecovery(trip.id, { pauseId: recovery.pauseId, choice: choice!, lighterDay: lighter, answers }, language),
    onSuccess: (data) => {
      setResult(data);
      setEditing(false);
      // ★A choice the server could not write down is not passed over quietly (the plan was not touched either way).
      if (!data.recorded) toast.show({ text: t("선택을 기록하지 못했어요", "We could not record your choice"), sub: t("일정은 그대로예요. 잠시 뒤 다시 정해 주세요.", "Your plan is as it was. Please choose again in a moment."), ms: 9_000, chip: { text: t("확인 필요", "Needs a look"), tone: "warn" } });
      onChosen();
    },
  });

  const said = recovery.options.find((option) => option.key === (result?.choice ?? choice));
  const at = recovery.event.at ? seoul(recovery.event.at) : null;
  const countText = [
    recovery.counts.affected ? t(`영향 확정 ${recovery.counts.affected}곳`, `${recovery.counts.affected} affected`) : "",
    recovery.counts.unknown ? t(`범위 모름 ${recovery.counts.unknown}곳`, `${recovery.counts.unknown} not known`) : "",
    recovery.counts.unaffected ? t(`영향 없음 ${recovery.counts.unaffected}곳`, `${recovery.counts.unaffected} not affected`) : "",
  ].filter(Boolean).join(" · ");

  return <section className={styles.panel} aria-labelledby={`${id}-title`} data-testid="recovery-panel" data-phase={recovery.phase ?? undefined}>
    {toast.node}
    <header className={styles.head}>
      <HeartHandshake size={22} strokeWidth={1.8} aria-hidden="true" />
      <div>
        <h2 id={`${id}-title`}>{t("재난 뒤 이어가기", "Going on after the disaster")}</h2>
        <p className={styles.event}>{[recovery.event.label, at ? `${at.date} ${at.time}` : null].filter(Boolean).join(" · ")}</p>
      </div>
    </header>
    <p className={styles.lead}>{t("어떻게 이어갈지는 직접 정해 주세요. 우리가 대신 정하지 않고, 아는 것과 모르는 것을 그대로 보여 드려요.", "How to go on is yours to decide. We do not decide for you; here is what we know and what we do not.")}</p>

    <div className={styles.known}>
      {recovery.facts.length > 0 && <div>
        <h3>{t("알려진 것", "What is known")}</h3>
        <ul>{recovery.facts.map((fact) => <li key={fact}>{fact}</li>)}</ul>
      </div>}
      {recovery.unknowns.length > 0 && <div data-unknown>
        <h3>{t("우리가 모르는 것", "What we do not know")}</h3>
        <ul>{recovery.unknowns.map((unknown) => <li key={unknown}>{unknown}</li>)}</ul>
      </div>}
    </div>

    {recovery.items.length > 0 && <div className={styles.items}>
      <h3>{t("남은 일정", "Stops still ahead")}</h3>
      {countText && <p className={styles.counts}>{countText}</p>}
      <ul>{recovery.items.map((item) => {
        const Icon = STATUS_ICON[item.status];
        return <li key={item.id} data-status={item.status}>
          <span className={styles.chip} data-status={item.status}><Icon size={13} strokeWidth={2} aria-hidden="true" />{t(...STATUS_WORDS[item.status])}</span>
          <div>
            <strong>{item.title}</strong>
            <small>{[item.startsAt ? seoul(item.startsAt).time : null, item.placeName && item.placeName !== item.title ? item.placeName : null, item.district].filter(Boolean).join(" · ")}</small>
            {item.reason && <small>{item.reason}</small>}
          </div>
        </li>;
      })}</ul>
    </div>}

    {!editing && (result || recovery.chosen) ? <div className={styles.done} role="status">
      <h3>{t("고르신 것", "Your choice")}</h3>
      <p><strong>{said?.label ?? t("기록했어요", "Recorded")}</strong>{(result?.lighterDay ?? lighter) && ` · ${recovery.lighterDay?.label ?? t("오늘은 가볍게", "A lighter day")}`}</p>
      {said?.detail && <p className={styles.detail}>{said.detail}</p>}
      {(result?.choice ?? choice) === "replace_affected" && <ul className={styles.proposals}>
        {result && result.proposals.length === 0 && <li>{t("바꿀 곳으로 확정된 일정이 없어서 제안을 만들지 않았어요. 바꾸고 싶은 곳은 채팅으로 말씀해 주세요.", "No stop is confirmed as affected, so nothing was proposed. Tell the chat what you want to change.")}</li>}
        {result?.proposals.map((proposal) => <li key={proposal.itemId}>{
          NO_CANDIDATE_STATUSES.includes(proposal.status ?? "")
            ? t(`「${proposal.title}」: 대신 갈 곳 후보가 없어서 일정은 그대로 두었어요.`, `"${proposal.title}": no place to go instead, so the plan is as it was.`)
            : proposal.proposalId && proposal.options.length > 0
              ? t(`「${proposal.title}」: 대신 갈 곳 ${proposal.options.length}곳을 제안했어요. 「선택이 필요해요」에서 고르면 바뀌고, 안 고르면 그대로예요.`, `"${proposal.title}": ${proposal.options.length} places proposed. Pick one under "Your choice" to change it; otherwise it stays.`)
              : t(`「${proposal.title}」: 제안을 만들지 못했어요. 일정은 그대로예요.`, `"${proposal.title}": no proposal could be made. The plan is as it was.`)
        }</li>)}
      </ul>}
      <Button onClick={() => setEditing(true)}>{t("다시 고르기", "Choose again")}</Button>
    </div> : <form className={styles.form} onSubmit={(event) => { event.preventDefault(); if (choice) send.mutate(); }}>
      <fieldset className={styles.options}>
        <legend>{t("어떻게 이어갈까요?", "How do you want to go on?")}</legend>
        {recovery.options.map((option) => <label key={option.key} className={styles.option} data-picked={choice === option.key || undefined}>
          <input type="radio" name={`${id}-choice`} value={option.key} checked={choice === option.key} onChange={() => setChoice(option.key)} />
          <span>
            <strong>{option.label}{option.recommended && <em>{t("추천", "Suggested")}</em>}</strong>
            {option.detail && <small>{option.detail}</small>}
          </span>
        </label>)}
      </fieldset>

      {recovery.lighterDay && <label className={styles.extra}>
        <input type="checkbox" checked={lighter} onChange={(event) => setLighter(event.target.checked)} />
        <span><strong>{recovery.lighterDay.label}</strong>{recovery.lighterDay.detail && <small>{recovery.lighterDay.detail}</small>}</span>
      </label>}

      {recovery.questions.length > 0 && <div className={styles.questions}>
        <h3>{t("알려 주시면 도움이 돼요(안 해도 돼요)", "It helps if you tell us (optional)")}</h3>
        {recovery.questions.map((question) => <fieldset key={question.key} className={styles.question}>
          <legend>{question.text}</legend>
          <div role="group" aria-label={question.text}>{question.answers.map((answer) => {
            const on = answers[question.key] === answer;
            return <button key={answer} type="button" aria-pressed={on} data-on={on || undefined}
              onClick={() => setAnswers((current) => { const next = { ...current }; if (on) delete next[question.key]; else next[question.key] = answer; return next; })}>{t(...ANSWER_WORDS[answer])}</button>;
          })}</div>
        </fieldset>)}
      </div>}

      {recovery.scopeNote && <p className={styles.scope}>{recovery.scopeNote}</p>}
      {send.error && <p className={styles.error} role="alert">{send.error instanceof Error ? send.error.message : String(send.error)}</p>}
      <Button type="submit" variant="primary" disabled={!choice || send.isPending}>{send.isPending ? t("기록하는 중…", "Recording…") : t("이대로 정하기", "Confirm")}</Button>
      {!choice && <p className={styles.hint}>{t("하나를 고르면 정할 수 있어요.", "Pick one to confirm.")}</p>}
    </form>}
  </section>;
}
