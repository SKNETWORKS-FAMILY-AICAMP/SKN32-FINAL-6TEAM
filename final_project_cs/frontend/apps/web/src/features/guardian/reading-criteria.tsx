"use client";

import { useId, type KeyboardEvent } from "react";
import { Check } from "lucide-react";
import { Panel } from "@/components/ui";
import { useT } from "@/lib/settings";
import { PACES, type Pace } from "./model";
import styles from "./reading-criteria.module.css";

/**
 * `[2026-10-06 사용자 지시 — 설문 화면 구현 인계 · 목업 v9 §3-1]` 「읽는 기준」 under the plan panels: how full a day is made. 「적당히」 is chosen from the start - left alone, it is sent
 * (`pace: "moderate"`). Three radios, the arrow keys move between them. The help line names no number (「한 곳쯤」 is the only measure said). The 「일정이 바뀌면」 question is not here:
 * the Course Keeper is asked on its own card once 「계획 확인하기」 is pressed.
 */
export function ReadingCriteria({ pace, onChange }: { pace: Pace; onChange: (pace: Pace) => void }) {
  const t = useT();
  const titleId = useId(), groupId = useId();

  function move(event: KeyboardEvent<HTMLElement>) {
    const step = event.key === "ArrowRight" || event.key === "ArrowDown" ? 1 : event.key === "ArrowLeft" || event.key === "ArrowUp" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const at = PACES.findIndex((entry) => entry.value === pace);
    const next = PACES[(at + step + PACES.length) % PACES.length];
    onChange(next.value);
    const group = event.currentTarget.parentElement;                      // ★React empties `currentTarget` once the handler returns - taken before the frame, or the focus never follows
    requestAnimationFrame(() => group?.querySelector<HTMLElement>(`[data-pace="${next.value}"]`)?.focus());
  }

  return <Panel className={styles.settings} aria-labelledby={titleId}>
    <h2 id={titleId}>{t("읽는 기준", "How to read it")}</h2>
    <p className={styles.lead}>{t("처음부터 골라 두었어요. 바꾸고 싶을 때만 눌러 주세요.", "It is already chosen. Change it only if you want to.")}</p>
    <div className={styles.group}>
      <h3 id={groupId}>{t("하루 일정의 여유", "How full a day is")}</h3>
      <p className={styles.help}>{t("하루를 얼마나 채울까요?", "How full should a day be?")}</p>
      <div className={styles.chips} role="radiogroup" aria-labelledby={groupId}>
        {PACES.map((entry) => {
          const on = entry.value === pace;
          return <button key={entry.value} type="button" role="radio" aria-checked={on} tabIndex={on ? 0 : -1} data-pace={entry.value} className={styles.chip} onClick={() => onChange(entry.value)} onKeyDown={move}>
            {on && <Check size={16} strokeWidth={1.8} aria-hidden="true" />}{t(entry.ko, entry.en)}</button>;
        })}
      </div>
      <p className={styles.hint}>{t("「적당히」는 「여유롭게」보다 하루에 한 곳쯤 더 담아요.", "“Balanced” fits about one more place a day than “Relaxed”.")}</p>
    </div>
  </Panel>;
}
