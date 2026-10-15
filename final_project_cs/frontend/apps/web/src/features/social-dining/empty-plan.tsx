"use client";

import { useId, useState, useSyncExternalStore, type FormEvent } from "react";
import { PLAN_DAYS, PLAN_PARTY, seoulToday, askProblem } from "@/features/trip-registration/model";
import type { TripSurvey } from "@/features/onboarding/payload";
import type { ReviewedIntakeView } from "@/lib/live/intake-review";
import { useSettings, useT } from "@/lib/settings";
import { progressText, type OpProgress } from "@/lib/live/stream";
import { generateWithDiningLinks } from "./start";
import styles from "./social-dining.module.css";

const subscribe = () => () => undefined;
export function EmptyDiningPlan({ intakeId, revision, survey, onRefresh, onApplied }: { intakeId: string; revision: number; survey?: TripSurvey; onRefresh: () => void; onApplied: (view: ReviewedIntakeView) => void }) {
  const t = useT(), { language } = useSettings(), id = useId();
  const today = useSyncExternalStore(subscribe, seoulToday, () => "");
  const [start, setStart] = useState(""), [days, setDays] = useState(0), [party, setParty] = useState(0);
  const [busy, setBusy] = useState(false), [error, setError] = useState("");
  const [progress, setProgress] = useState<OpProgress | null>(null);
  async function generate(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    const problem = askProblem({ start, days, party, wish: "" }, today);
    if (problem) { setError(problem === "past" ? t("첫날은 오늘(서울 기준) 이후로 골라 주세요.", "Choose today or a later date in Seoul.") : t("첫날·일수·인원을 모두 골라 주세요.", "Choose the first day, days and travelers.")); return; }
    setBusy(true); setError(""); setProgress(null);
    try {
      const result = await generateWithDiningLinks(intakeId, revision, { start_date: start, days, party_size: party, ...(survey && { survey }) }, language, setProgress);
      onApplied(result);
      setBusy(false);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : t("일정을 만들지 못했어요. 후보는 보관되어 있어요.", "The itinerary could not be created. Your candidates are saved."));
      if ((failure as { code?: string } | null)?.code === "stale_revision") onRefresh();
      setBusy(false);
    }
  }
  return <form onSubmit={generate}>
    <h3>{t("아직 일정이 없으신가요?", "No itinerary yet?")}</h3>
    <p className={styles.note}>{t("먼저 서울 일정 초안을 만들고 맛집 반영안을 확인해요. 여행 등록은 확인 후 직접 진행해 주세요. 넣지 못한 식당은 후보에 남아요.", "Create a Seoul draft first, then review the restaurant proposal. Register the trip yourself after checking it. Restaurants that do not fit remain saved as candidates.")}</p>
    <div className={styles.grid}>
      <label className={styles.field} htmlFor={`${id}-start`}>{t("첫날", "First day")}<input id={`${id}-start`} type="date" min={today || undefined} value={start} disabled={busy} onChange={(event) => setStart(event.target.value)} /></label>
      <label className={styles.field} htmlFor={`${id}-days`}>{t("일수", "Days")}<select id={`${id}-days`} value={days} disabled={busy} onChange={(event) => setDays(Number(event.target.value))}><option value={0}>{t("선택", "Choose")}</option>{PLAN_DAYS.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
      <label className={styles.field} htmlFor={`${id}-party`}>{t("인원", "Travelers")}<select id={`${id}-party`} value={party} disabled={busy} onChange={(event) => setParty(Number(event.target.value))}><option value={0}>{t("선택", "Choose")}</option>{PLAN_PARTY.map((value) => <option key={value} value={value}>{value}</option>)}</select></label>
    </div>
    {error && <p role="alert" className={styles.error}>{error}</p>}
    {busy && <p role="status" className={styles.note}>{progressText(progress, t, ["일정을 짜 달라고 보냈어요…", "Sent your planning request…"])}</p>}
    <button className={styles.primary} type="submit" disabled={busy}>{busy ? t("일정 만드는 중…", "Creating itinerary…") : t("후보를 보관하고 일정 초안 만들기", "Keep candidates and create a draft")}</button>
  </form>;
}
