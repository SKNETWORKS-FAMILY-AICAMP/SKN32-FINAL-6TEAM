"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, ChevronDown } from "lucide-react";
import { Badge, Button, ButtonLink, PageHeading, Panel, QueryState, RegistrationSteps } from "@/components/ui";
import type { VerificationResult } from "@/features/trip/model";
import { useTrip } from "@/features/trip/use-trip";
import { tripGateway, tripKey } from "@/lib/gateway";
import { routes } from "@/lib/routes";
import styles from "./verification.module.css";

const resultLabels = { adjusted: "조정", unchanged: "유지", needs_review: "확인 필요" };

function displayDate(date: string) {
  const [, month, day] = date.split("-");
  return `${Number(month)}.${Number(day)}`;
}

function dayNumber(date: string, start: string) {
  return Math.max(1, Math.round((Date.parse(`${date}T00:00:00Z`) - Date.parse(`${start}T00:00:00Z`)) / 86_400_000) + 1);
}

function ResultItem({ result, showDate = false }: { result: VerificationResult; showDate?: boolean }) {
  const adjusted = result.status === "adjusted";
  const unresolved = result.status === "needs_review";
  return (
    <details className={styles.resultItem} open={unresolved || undefined}>
      <summary>
        <div>
          <div className={styles.resultTitle}>
            <Badge tone={unresolved ? "warning" : adjusted ? "success" : "neutral"}>{resultLabels[result.status]}</Badge>
            <strong>{result.title}</strong>
            {showDate && <span className={styles.muted}>{displayDate(result.date)}</span>}
          </div>
          <div className={styles.brief}>{adjusted ? `${result.originalValue} → ${result.proposedValue ?? "조정 내용 확인"}` : `${result.originalValue} · ${unresolved ? "재확인 필요" : "유지"}`}</div>
        </div>
        <ChevronDown className={styles.chevron} size={16} aria-hidden="true" />
      </summary>
      <div className={styles.resultDetail}>
        {adjusted && <div className={styles.comparison}>
          <div><span className={styles.muted}>입력한 계획</span><div className={styles.comparisonValue}>{result.originalValue}</div></div>
          <ArrowRight size={16} aria-hidden="true" />
          <div className={styles.after}><span className={styles.muted}>조정된 계획</span><div className={styles.comparisonValue}>{result.proposedValue || "조정 내용 없음"}</div></div>
        </div>}
        <p><strong>{unresolved ? "미확인 이유" : "확인 내용"}</strong><br /><span>{result.reason}</span></p>
        <p><strong>다른 일정에 미치는 영향</strong><br /><span>{result.impact}</span></p>
      </div>
    </details>
  );
}

export function VerificationResults({ tripId }: { tripId: string }) {
  const tripQuery = useTrip(tripId);
  const queryClient = useQueryClient();
  const router = useRouter();
  const [confirmedTripId, setConfirmedTripId] = useState<string | null>(null);
  const start = useMutation({
    mutationFn: () => tripGateway.startTrip(tripId),
    onSuccess: (trip) => {
      queryClient.setQueryData(tripKey(tripId), trip);
      router.push(routes.trip(tripId));
    },
  });
  const retry = useMutation({
    mutationFn: () => tripGateway.retryVerification(tripId),
    onSuccess: (trip) => {
      queryClient.setQueryData(tripKey(tripId), trip);
      router.push(routes.verification(tripId));
    },
  });
  const trip = tripQuery.data;

  if (!trip || tripQuery.error) {
    return <QueryState loading={tripQuery.isPending} error={tripQuery.error} retry={() => void tripQuery.refetch()} />;
  }

  if (trip.verification.status === "running") {
    return <div className={styles.resultsPage}>
      <RegistrationSteps current={1} />
      <PageHeading title="여행 계획을 검증하고 있어요" description="검증이 끝나면 이 화면에서 결과를 확인할 수 있어요." />
      <Panel><p className={styles.statusMessage}>현재 {Math.round(trip.verification.progress)}% 진행했어요.</p><ButtonLink href={routes.verification(tripId)} variant="primary">검증 진행 상황 보기 <ArrowRight size={16} aria-hidden="true" /></ButtonLink></Panel>
    </div>;
  }

  const results = trip.verification.results;
  const unresolved = results.filter((result) => result.status === "needs_review");
  const adjustedCount = results.filter((result) => result.status === "adjusted").length;
  const unchangedCount = results.filter((result) => result.status === "unchanged").length;
  const failed = trip.verification.status === "failed";
  const ready = trip.verification.status === "completed" && unresolved.length === 0 && results.length > 0;
  const active = trip.status === "active";
  const confirmed = confirmedTripId === trip.id;
  const dates = Array.from(new Set(results.filter((result) => result.status !== "needs_review").map((result) => result.date))).sort();
  const editHref = `${routes.newTrip}?from=${encodeURIComponent(tripId)}`;
  const title = failed ? "검증을 완료하지 못했어요" : unresolved.length ? "검증을 마치지 못한 항목이 있어요" : results.length ? "여행 계획의 검증 결과를 확인해 주세요" : "확인할 검증 결과가 없어요";
  const startBlockReason = failed ? "검증을 다시 완료한 뒤 여행 관리를 시작할 수 있어요." : unresolved.length ? `미확인 항목 ${unresolved.length}건이 남아 있어요.` : !results.length ? "검증 결과가 있어야 여행 관리를 시작할 수 있어요." : null;

  return (
    <div className={styles.resultsPage}>
      <RegistrationSteps current={2} />
      <PageHeading eyebrow="YOUR PLAN · CHECK RESULTS" title={title} description={`${trip.title} · ${trip.startDate} – ${trip.endDate}`} />
      <div className={styles.resultsGrid}>
        <Panel>
          <div className={styles.panelHeading}><h2>첫 검증 결과</h2><span className={styles.muted}>{ready ? "전체 검증 완료" : "전체 검증 미완료"} · 결과 {results.length}건</span></div>
          <div className={styles.counts} aria-label="검증 결과 건수"><span>조정 <strong>{adjustedCount}</strong></span><span>유지 <strong>{unchangedCount}</strong></span><span>확인 필요 <strong>{unresolved.length}</strong></span></div>
          {failed && <div className={styles.warning} role="alert">{trip.verification.error || "검증을 완료하지 못했어요. 입력한 계획과 확인된 내용은 보존돼요."}</div>}
          {unresolved.length > 0 && <>
            <p className={styles.warning}>확인을 마치지 못한 항목이 있어요. 이 항목을 해결한 뒤 여행 관리를 시작할 수 있어요.</p>
            <section aria-labelledby="review-first-title"><div className={styles.dayHeading}><h3 id="review-first-title">먼저 확인해 주세요</h3><small>{unresolved.length}건</small></div>{unresolved.toSorted((a, b) => a.date.localeCompare(b.date)).map((result) => <ResultItem key={result.id} result={result} showDate />)}</section>
          </>}
          {dates.map((date) => {
            const dayResults = results.filter((result) => result.date === date && result.status !== "needs_review").toSorted((a, b) => {
              const aTime = trip.stops.find((stop) => stop.id === a.stopId)?.time ?? a.originalValue;
              const bTime = trip.stops.find((stop) => stop.id === b.stopId)?.time ?? b.originalValue;
              return aTime.localeCompare(bTime);
            });
            return <section key={date} aria-label={`${dayNumber(date, trip.startDate)}일차 검증 결과`}>
              <div className={styles.dayHeading}><h3>{dayNumber(date, trip.startDate)}일차</h3><small>{displayDate(date)}</small></div>
              {dayResults.map((result) => <ResultItem key={result.id} result={result} />)}
            </section>;
          })}
          {results.length === 0 && <p className={styles.emptyMessage}>표시할 항목별 결과가 아직 없어요. 입력한 계획을 확인하거나 검증을 다시 시도해 주세요.</p>}
          <p className={styles.footnote}>{ready ? "조정한 항목을 포함해 전체 일정 검증을 완료했어요." : "입력한 계획과 완료한 결과는 보존돼요. 미완료 항목을 해결한 뒤 전체 일정을 다시 검증해요."}</p>
          <div className={styles.actions}>
            <ButtonLink href={editHref} variant="secondary">조건 수정 후 다시 검증</ButtonLink>
            {(failed || !results.length) && <Button type="button" variant="primary" disabled={retry.isPending} onClick={() => retry.mutate()}>{retry.isPending ? "다시 요청하는 중…" : "검증 다시 시도"}</Button>}
          </div>
          {retry.error && <p className={styles.error} role="alert">{retry.error.message}</p>}
        </Panel>
        <Panel>
          <h2>여행 관리 시작</h2>
          <ul className={styles.help}>
            <li><strong>일정에 영향을 주는 변화</strong><p>활동·식당·이동 상황을 살피고 일정 변경을 안내해요.</p></li>
            <li><strong>변경 안내는 일정과 채팅에</strong><p>변경 내역과 이유를 같은 여행에서 확인해요. 원하는 경우 다시 조정을 요청할 수 있어요.</p></li>
            <li><strong>예약은 별도 확인</strong><p>업체 예약 변경·취소는 별도로 확인해요.</p></li>
          </ul>
          {active ? <><p className={styles.activeMessage}>이미 여행 관리를 시작했어요. 여행 홈에서 현재 일정을 확인할 수 있어요.</p><ButtonLink href={routes.trip(tripId)} variant="primary" className={styles.fullWidth}>여행 홈으로 <ArrowRight size={16} aria-hidden="true" /></ButtonLink></> : <>
            <label className={styles.confirm}><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmedTripId(event.target.checked ? trip.id : null)} disabled={start.isPending} /><span>전체 검증 결과와 일정 조정·안내 범위를 확인했어요.</span></label>
            {startBlockReason && <p className={styles.warning} id="start-block-reason">{startBlockReason}</p>}
            <Button type="button" variant="primary" className={styles.fullWidth} disabled={!ready || !confirmed || start.isPending} aria-describedby={startBlockReason ? "start-block-reason" : undefined} onClick={() => { if (ready && confirmed) start.mutate(); }}>{start.isPending ? "여행 관리를 시작하는 중…" : "여행 관리 시작"}<ArrowRight size={16} aria-hidden="true" /></Button>
            {start.error && <p className={styles.error} role="alert">{start.error.message}</p>}
          </>}
        </Panel>
      </div>
    </div>
  );
}
