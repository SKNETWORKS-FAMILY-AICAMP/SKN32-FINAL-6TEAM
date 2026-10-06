"use client";

import { useMutation } from "@tanstack/react-query";
import { Phone, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui";
import { formatDistance } from "@/features/map/map-geometry";
import { resumeSafety, type Notice, type Shelter } from "@/lib/live/extras";
import type { Recovery } from "@/lib/live/recovery";
import { useSettings, useT } from "@/lib/settings";
import type { Trip } from "./model";
import styles from "./trip-safety.module.css";

/** The newest safety alert that carries guidance: what to follow and where to go, in the server's words. */
export function latestSafetyAlert(notices: readonly Notice[]): Notice | null {
  return [...notices].filter((notice) => notice.type === "safety_alert" && notice.safety).sort((a, b) => Date.parse(b.at) - Date.parse(a.at))[0] ?? null;
}

/** 「직선 320m · 걸어서 약 5분(추정)」 - only what the server sent; the walk is an estimate along a straight line and says so. */
function shelterMeta(shelter: Shelter, t: ReturnType<typeof useT>): string {
  return [
    shelter.distanceM !== null ? t(`직선 ${formatDistance(shelter.distanceM)}`, `${formatDistance(shelter.distanceM)} in a straight line`) : "",
    shelter.walkMinutes !== null ? t(`걸어서 약 ${shelter.walkMinutes}분(추정)`, `about ${shelter.walkMinutes} min on foot (estimate)`) : "",
    shelter.underground === true ? t("지하", "underground") : "",
  ].filter(Boolean).join(" · ");
}

/**
 * `[2026-10-06 사용자 결정 — 재난 시 일정 정지 + 대피 안내]` The top of the trip screen while the trip is paused for a disaster: that it is paused, why (the server's label), until when, the safety guidance of the
 * newest alert, and the customer's 「일정 다시 시작」. ★Safety first: the guidance comes before the button; the button is said to be pressed only once the customer knows they are safe, and NOTHING resumes by
 * itself (the server cannot know). The plan is not changed by a pause. Every sentence of the guidance is the server's; the reference point is the place in the plan, and the server's note says so.
 */
export function SafetyPanel({ trip, notices, onChanged, onResumed }: { trip: Trip; notices: readonly Notice[]; onChanged: () => void; /** The brief of the disaster that was just lifted (null when there was nothing to lift). */ onResumed?: (recovery: Recovery | null) => void }) {
  const t = useT();
  const { language } = useSettings();
  const resume = useMutation({ mutationFn: () => resumeSafety(trip.id, language), onSuccess: (data) => onResumed?.(data.recovery), onSettled: onChanged });
  const safety = trip.safety;
  if (!safety?.paused) return null;
  const alert = latestSafetyAlert(notices);
  const guidance = alert?.safety ?? null;
  const resumeLabel = safety.resume ? safety.resume.label || t("일정 다시 시작", "Resume the itinerary") : null;
  // ★`[2026-10-06 사용자 결정]` A trip that has not started yet is also paused by a serious event (nobody knows the local situation): the words differ, and there is NO shelter card at all
  //   (the customer is not there; the server sends official guidance to check the situation before going, not a list of places).
  const upcoming = safety.phase === "upcoming" || guidance?.phase === "upcoming";
  return <section className={styles.panel} aria-labelledby="trip-safety-title" data-level={safety.level ?? undefined} data-phase={upcoming ? "upcoming" : undefined} data-testid="safety-panel">
    <header className={styles.head}>
      <ShieldAlert size={22} strokeWidth={1.8} aria-hidden="true" />
      <h2 id="trip-safety-title">{t("일정 정지 중", "Itinerary paused")}</h2>
    </header>
    {safety.label && <p className={styles.label}>{safety.label}</p>}
    {upcoming && <p className={styles.label}>{t("아직 시작하지 않은 여행이지만 현지 상황을 몰라 멈췄어요.", "The trip has not started, but we paused it because we cannot tell what it is like there.")}</p>}
    <p className={styles.when}>{[
      safety.since ? t(`${safety.since}부터`, `Since ${safety.since}`) : "",
      // ★`[2026-10-06 사용자 결정 — 그날 정지도 자정에 풀리지 않는다]` Nothing releases a pause by itself, a day's pause included: the server sends `until: null` and the customer's 「일정 다시 시작」 is the only way out. So no end time = said that way, whatever the level; a time is shown only when an older server still sends one for a day.
      safety.level === "trip" || !safety.until ? t("다시 시작할 때까지 멈춰 있어요", "Stays paused until you resume") : t(`${safety.until}까지`, `Until ${safety.until}`),
      safety.released ? t("해제됐다는 공식 안내가 나왔어요", "An official all-clear came") : "",
    ].filter(Boolean).join(" · ")}</p>

    {guidance && alert && <div className={styles.guidance}>
      {alert.text && <p className={styles.text}>{alert.text}</p>}
      {guidance.emergencyCall && <a className={styles.call} href={`tel:${guidance.emergencyCall}`}><Phone size={18} strokeWidth={1.8} aria-hidden="true" />{t(`${guidance.emergencyCall}에 전화`, `Call ${guidance.emergencyCall}`)}</a>}
      {!upcoming && guidance.shelters.length > 0 && <>
        <h3>{t("가까운 대피 장소", "Nearby shelters")}</h3>
        <ul className={styles.shelters}>{guidance.shelters.map((shelter) => <li key={`${shelter.name}-${shelter.address ?? ""}`}>
          <strong>{shelter.name}</strong>
          {shelter.address && <span>{shelter.address}</span>}
          <span className={styles.meta}>{shelterMeta(shelter, t)}</span>
          {shelter.mapUrl && <a href={shelter.mapUrl} target="_blank" rel="noopener noreferrer">{t("걸어서 길 찾기", "Walking directions")}</a>}
        </li>)}</ul>
      </>}
      {guidance.reference?.note && <p className={styles.note}>{guidance.reference.place ? `${guidance.reference.place} · ` : ""}{guidance.reference.note}</p>}
    </div>}

    {resumeLabel !== null && <div className={styles.resume}>
      <p id="trip-safety-resume-hint">{upcoming ? t("가기 전에 현지 상황을 확인한 뒤에 눌러 주세요.", "Press it after you have checked the situation there.") : t("안전한 곳에 계신 것을 확인한 뒤에 눌러 주세요.", "Press it only after you are somewhere safe.")}</p>
      <Button variant="primary" disabled={resume.isPending} aria-describedby="trip-safety-resume-hint" onClick={() => resume.mutate()}>{resume.isPending ? t("다시 시작하는 중…", "Resuming…") : resumeLabel}</Button>
      {resume.error && <p className={styles.error} role="alert">{resume.error instanceof Error ? resume.error.message : String(resume.error)}</p>}
    </div>}
  </section>;
}
