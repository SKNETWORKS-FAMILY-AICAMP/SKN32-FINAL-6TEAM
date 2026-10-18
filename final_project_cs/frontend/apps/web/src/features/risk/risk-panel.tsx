"use client";

import { useEffect, useState } from "react";
import { problemText, type ItemRisk, type TripRisks } from "@/lib/live/risks";
import { useT } from "@/lib/settings";
import styles from "./risk-panel.module.css";

export function riskTime(value: string | null): string | null {
  if (!value) return null;
  const at = new Date(value);
  if (Number.isNaN(at.getTime())) return null;
  return new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false }).format(at);
}

/** Current server findings stay visible; old notices are never replayed into this panel. */
export function RiskPanel({ items, at = null, mode = null, loading = false, error = false, unavailable = false,
  retry, busy = false, onAlternatives, alternativeBusy, alternativeMessage, compact = false, scope }: {
  items: readonly ItemRisk[]; at?: string | null; mode?: string | null; loading?: boolean; error?: boolean; unavailable?: boolean;
  retry?: () => void; busy?: boolean; onAlternatives?: (itemId: string) => void; alternativeBusy?: string | null;
  alternativeMessage?: string | null; compact?: boolean; scope?: TripRisks;
}) {
  const t = useT();
  const [showLoading, setShowLoading] = useState(false);
  useEffect(() => {
    const timer = setTimeout(() => setShowLoading(loading), loading ? 100 : 0);
    return () => clearTimeout(timer);
  }, [loading]);
  const problems = items.filter((item) => item.status === "problem");
  const unknown = items.filter((item) => item.status === "unknown" || item.unknownCategories.length > 0);
  const current = problems.length ? problems : unknown;
  const shown = compact ? current.slice(0, 2) : current;
  const count = problems.length;
  const skipped = scope?.skipped ?? [];
  const unchecked = skipped.filter((item) => item.reason !== "mobility");
  const atText = riskTime(at ?? items.find((item) => item.checkedAt)?.checkedAt ?? null);
  if (loading && !items.length && !showLoading) return null;
  return <section className={styles.panel} data-risk-panel data-tone={count ? "danger" : error || unavailable || unknown.length || unchecked.length ? "unknown" : "clear"}
    aria-label={t("현재 일정 위험 확인", "Current itinerary risks")} aria-busy={loading || busy}>
    <div className={styles.heading}><strong>{count ? t(`주의할 일정 ${count}개`, `${count} stops need attention`)
      : loading ? t("현재 위험을 확인하고 있어요", "Checking current risks")
      : error || unavailable ? t("현재 위험을 확인하지 못했어요", "Current risks could not be checked")
      : unknown.length ? t(`일부 확인이 안 된 일정 ${unknown.length}개`, `${unknown.length} stops are not fully checked`)
      : unchecked.length ? t("아직 확인하지 못한 일정이 있어요", "Some stops have not been checked yet")
      : !items.length ? t("현재 점검 대상 일정이 없어요", "No stops are currently in the check scope")
      : t("최근 확인에서 겹치는 위험이 없어요", "No overlapping risk in the latest check")}</strong>
      {retry && <button type="button" onClick={retry} disabled={busy || loading}>{t("다시 확인", "Check again")}</button>}</div>
    {(error || unavailable) && <p role="status">{t("현재 일정은 유지돼요. 다시 확인해 주세요.", "Your itinerary is kept. Check again.")}</p>}
    {loading && !items.length && showLoading && <div className={styles.loading} role="status"><span /><span /><span className="sr-only">{t("위험 정보 확인 중", "Checking risks")}</span></div>}
    {shown.length > 0 && <ul className={styles.items}>{shown.map((item, index) => <li key={item.itemId || `${item.title}-${index}`}>
      <b>{item.title || t("일정", "Stop")}</b>
      {item.problems.map((problem, at) => <p key={`${problem.category}-${problem.incidentId ?? at}`}>
        {problemText(problem)}{riskTime(problem.endsAt) && <span> · {t(`종료 예정 ${riskTime(problem.endsAt)}`, `Scheduled end ${riskTime(problem.endsAt)}`)}</span>}
        {problem.asOfNow && <span> · {t("현재 상황이며 방문 시각에 다시 확인해요", "Current conditions; check again near the visit")}</span>}
        {(problem.source || riskTime(problem.confirmedAt)) && <small>{[problem.source, riskTime(problem.confirmedAt)].filter(Boolean).join(" · ")}</small>}
      </p>)}
      {item.unknownCategories.length > 0 && <p className={styles.unknown}>{t("확인 불가", "Not verified")}: {item.unknownCategories.join(" · ")}</p>}
      {item.status === "unknown" && !item.unknownCategories.length && <p className={styles.unknown}>{item.reason ?? t("위험 정보를 확인하지 못했어요.", "Risk information could not be verified.")}</p>}
      {item.stale && <p className={styles.unknown}>{t("최신 자료를 받지 못해 이전 확인 결과를 보여 드려요.", "Showing an earlier result because newer data is unavailable.")}</p>}
      {item.dataConfirmedAt && <small>{t("자료 확인", "Source confirmed")}: {riskTime(item.dataConfirmedAt)}</small>}
      {onAlternatives && item.status === "problem" && <button type="button" className={styles.alternative} disabled={Boolean(alternativeBusy)}
        onClick={() => onAlternatives(item.itemId)} aria-busy={alternativeBusy === item.itemId}>
        {alternativeBusy === item.itemId ? t("실내 대안을 확인하는 중…", "Checking indoor alternatives…") : t("실내 대안 보기", "See indoor alternatives")}</button>}
    </li>)}</ul>}
    {compact && current.length > shown.length && <p>{t(`외 ${current.length - shown.length}개 일정도 확인이 필요해요.`, `${current.length - shown.length} more stops need attention.`)}</p>}
    {count > 0 && unknown.some((item) => item.status !== "problem") && <p className={styles.unknown}>{t(`다른 ${unknown.filter((item) => item.status !== "problem").length}개 일정은 일부 확인하지 못했어요.`, "Other stops could not be fully checked.")}</p>}
    {alternativeMessage && <p role="status">{alternativeMessage}</p>}
    {scope && <p className={styles.when}>{typeof scope.horizonHours === "number" ? t(`지금부터 ${scope.horizonHours}시간 이내 대상 · `, `Within the next ${scope.horizonHours} hours · `) : ""}
      {t(`${items.length}개 점검`, `${items.length} stops checked`)}{skipped.length > 0 && t(` · 제외 ${skipped.length}개`, ` · ${skipped.length} skipped`)}</p>}
    {skipped.length > 0 && <p className={styles.unknown}>{[...new Set(skipped.map((item) => item.note).filter(Boolean))].join(" · ")}</p>}
    <p className={styles.when}>{atText ? t(`확인 ${atText}`, `Checked ${atText}`) : t("확인 시각을 받지 못했어요", "Check time is not available")}
      {mode === "cached" && ` · ${t("저장된 최근 정보", "Recent saved information")}`}
      {busy && !loading && ` · ${t("갱신 중", "Updating")}`}</p>
  </section>;
}
