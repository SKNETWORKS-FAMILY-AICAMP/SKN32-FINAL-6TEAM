"use client";

import { useT } from "@/lib/settings";
import { PLAN_DAYS, PLAN_PARTY, WISH_MAX, type PlanAsk } from "./model";
import styles from "./trip-registration.module.css";

/**
 * The inside of the third panel, 「계획 짜 주기 (테스트)」 — `[2026-10-03 사용자 지시]` the server plans the days from a first day, a
 * number of days and a number of travelers, plus (optionally) a short sentence about the trip the customer wants. It moved here from the
 * old review screen's 「읽은 일정이 없어요 — 대신 짜 드릴까요?」.
 *
 * ★Pressing 「계획 확인하기」 with this panel chosen plans AND registers: there is no check screen in between (the server registers the
 *   plan once it passes its checks), so the panel says so.
 */
export function PlanAskFields({ ask, today, disabled, onChange }: { ask: PlanAsk; today: string; disabled: boolean; onChange: (next: PlanAsk) => void }) {
  const t = useT();
  return <div className={styles.ask}>
    <p className={styles.askNote}>{t(
      "서울 안에서 하루하루를 서버가 짜 드려요. 이 칸을 고르고 「계획 확인하기」를 누르면, 짠 일정이 서버의 판정을 통과하는 대로 바로 여행으로 등록돼요.",
      "The server plans each day in Seoul. With this box chosen, pressing “Check my plan” registers the trip as soon as the plan passes the server’s checks.")}</p>
    <div className={styles.askGrid}>
      <div className={styles.askField}>
        <label htmlFor="plan-start">{t("첫날", "First day")}</label>
        <input id="plan-start" type="date" value={ask.start} min={today || undefined} disabled={disabled} onChange={(event) => onChange({ ...ask, start: event.target.value })} />
      </div>
      <div className={styles.askField}>
        <label htmlFor="plan-days">{t("일수", "Days")}</label>
        <select id="plan-days" value={ask.days} disabled={disabled} onChange={(event) => onChange({ ...ask, days: Number(event.target.value) })}>
          <option value={0}>{t("고르기", "Choose")}</option>
          {PLAN_DAYS.map((n) => <option key={n} value={n}>{t(`${n}일`, `${n}`)}</option>)}
        </select>
      </div>
      <div className={styles.askField}>
        <label htmlFor="plan-party">{t("인원", "Travelers")}</label>
        <select id="plan-party" value={ask.party} disabled={disabled} onChange={(event) => onChange({ ...ask, party: Number(event.target.value) })}>
          <option value={0}>{t("고르기", "Choose")}</option>
          {PLAN_PARTY.map((n) => <option key={n} value={n}>{t(`${n}명`, `${n}`)}</option>)}
        </select>
      </div>
    </div>
    <div className={styles.askField}>
      <label htmlFor="plan-wish">{t("원하는 여행 (선택)", "The trip you want (optional)")}</label>
      <textarea id="plan-wish" className={styles.wish} rows={3} maxLength={WISH_MAX} value={ask.wish} disabled={disabled} onChange={(event) => onChange({ ...ask, wish: event.target.value })}
        placeholder={t("예: 조용하고 걷기 좋은 곳 위주로, 맛집은 하루 한 곳쯤", "e.g. Quiet, walkable places, and one good restaurant a day")} />
      <span className={styles.askCount}>{ask.wish.length} / {WISH_MAX}</span>
    </div>
  </div>;
}
