"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import { Badge, Button, ButtonLink, Eyebrow, PageHeading, Panel, QueryState } from "@/components/ui";
import { useOnboarding } from "@/features/onboarding/onboarding-state";
import type { VerificationResult } from "@/features/trip/model";
import { useTrip } from "@/features/trip/use-trip";
import { tripGateway, tripKey } from "@/lib/gateway";
import type { Translate } from "@/lib/i18n";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import styles from "./verification.module.css";

function ResultItem({ result, t }: { result: VerificationResult; t: Translate }) {
  const adjusted = result.status === "adjusted";
  const review = result.status === "needs_review";
  return <details className={`${styles.result} ${adjusted ? styles.adjusted : ""}`} open={review || undefined}>
    <summary>
      <div>
        <Badge tone={review ? "warning" : "success"}>{review ? t("확인 필요", "Review") : adjusted ? t("조정", "Adjusted") : t("유지", "Kept")}</Badge>
        <strong>{result.title}</strong>
        <p className={styles.brief}>{result.originalValue}{adjusted ? ` → ${result.proposedValue}` : ` · ${t("입력한 시간", "Original time")}`}</p>
      </div>
      <span aria-hidden="true">+</span>
    </summary>
    <div className={styles.detail}>
      {adjusted && <div className={styles.change}>
        <span>{t("변경 전", "Before")}<strong>{result.originalValue}</strong></span>
        <ArrowRight size={18} strokeWidth={1.6} aria-hidden="true" />
        <span>{t("변경 후", "After")}<strong>{result.proposedValue}</strong></span>
      </div>}
      <p>{result.reason}</p>
      <p className={styles.muted}>{result.impact}</p>
    </div>
  </details>;
}

export function VerificationResults({ tripId }: { tripId: string }) {
  const t = useT();
  const { language } = useSettings();
  const tripQuery = useTrip(tripId);
  const queryClient = useQueryClient();
  const router = useRouter();
  const [, setOnboarding] = useOnboarding();
  const [scope, setScope] = useState<string | null>(null);
  const [day, setDay] = useState<string | null>(null);
  const start = useMutation({
    mutationFn: () => tripGateway.startTrip(tripId, language),
    onSuccess: (trip) => {
      queryClient.setQueryData(tripKey(tripId, language), trip);
      setOnboarding((current) => ({ ...current, activeTripId: trip.id }));
      router.push(routes.trip(tripId));
    },
  });
  const retry = useMutation({
    mutationFn: () => tripGateway.retryVerification(tripId, language),
    onSuccess: (trip) => {
      queryClient.setQueryData(tripKey(tripId, language), trip);
      router.push(routes.verification(tripId));
    },
  });
  const trip = tripQuery.data;

  if (!trip || tripQuery.error) {
    return <QueryState loading={tripQuery.isPending} error={tripQuery.error} retry={() => void tripQuery.refetch()} />;
  }

  if (trip.verification.status !== "completed") {
    return <Panel className={styles.gate}>
      <h1>{t("계획 확인이 아직 끝나지 않았어요", "Your plan check isn’t finished yet")}</h1>
      <p>{t("확인이 끝나면 이 화면에서 결과를 볼 수 있어요.", "You can see the results here once the check is complete.")}</p>
      <ButtonLink href={routes.verification(tripId)} variant="primary">{t("확인 진행 보기", "View the check")}<ArrowRight size={18} strokeWidth={1.6} aria-hidden="true" /></ButtonLink>
    </Panel>;
  }

  const results = trip.verification.results;
  const unresolved = results.filter((result) => result.status === "needs_review");
  const adjusted = results.filter((result) => result.status === "adjusted");
  const days = [...new Set(trip.stops.map((stop) => stop.date))].sort();
  const activeDay = day && days.includes(day) ? day : days[0];
  const active = trip.status === "active";
  const agreed = scope === trip.id;
  const stats: [number, string][] = [[adjusted.length, t("조정한 일정", "Adjusted")], [results.length - adjusted.length - unresolved.length, t("유지한 일정", "Kept")], [unresolved.length, t("확인이 필요한 일정", "Needs review")]];

  return <>
    <PageHeading eyebrow="READY, WITH A LITTLE MORE CARE"
      title={unresolved.length ? t("한 번 더 확인해 주세요.", "A little more checking is needed.") : t("여행의 준비가 끝났어요.", "You’re ready for your journey.")}
      description={t("바뀐 부분은 한눈에, 지켜야 할 계획은 그대로.", "See what changed and what stays just as planned.")} />
    <div className={styles.stats}>{stats.map(([count, label]) => <div key={label} className={styles.stat}><strong>{count}<small>{t("개", "")}</small></strong><span>{label}</span></div>)}</div>
    <div className={styles.resultsLayout}>
      <Panel>
        <div className={styles.cardHeader}><h2>{t("여행 계획 살펴보기", "A closer look at your plan")}</h2><Badge>{results.length}{t("개 일정", " stops")}</Badge></div>
        {unresolved.length > 0 && <>
          <div className={styles.warning}><strong>{t("여행 관리를 시작하기 전에", "Before starting your trip")}</strong><p>{t("확인이 필요한 항목을 수정한 뒤 다시 검증해 주세요.", "Edit the items needing review and check the plan again.")}</p></div>
          <div className={styles.resultList}>{unresolved.map((result) => <ResultItem key={result.id} result={result} t={t} />)}</div>
        </>}
        <div className={styles.dayTabs} role="group" aria-label={t("결과 일차", "Result days")}>{days.map((date, index) => (
          <button key={date} type="button" aria-pressed={date === activeDay} onClick={() => setDay(date)}>{t(`${index + 1}일차`, `Day ${index + 1}`)}<small>{date.slice(5).replace("-", ".")}</small></button>
        ))}</div>
        <div className={styles.resultList}>{results.filter((result) => result.date === activeDay && result.status !== "needs_review").map((result) => <ResultItem key={result.id} result={result} t={t} />)}</div>
      </Panel>
      <Panel className={styles.scopeCard}>
        <Eyebrow>WITH YOU, ALONG THE WAY</Eyebrow>
        <h2>{t("이제 여행에 집중하세요.", "Make room for the journey.")}</h2>
        <p className={styles.muted}>{t("확인한 계획을 일정과 지도에 모으고, 여행 채팅으로 이어가요.", "Bring your checked plan into your itinerary, visit diagram, and travel chat.")}</p>
        <ul className={styles.tipList}>
          <li>{t("조정 전후를 언제든 다시 확인", "Revisit changes whenever you need")}</li>
          <li>{t("예약이 있는 일정의 시간 유지", "Keep the times of reserved plans")}</li>
          <li>{t("일정·지도·채팅을 한곳에서", "Itinerary, map, and chat together")}</li>
        </ul>
        {active
          ? <ButtonLink href={routes.trip(tripId)} variant="primary">{t("내 여행으로 돌아가기", "Back to my trip")}<ArrowRight size={18} strokeWidth={1.6} aria-hidden="true" /></ButtonLink>
          : <>
            <label className={styles.scope}><input type="checkbox" checked={agreed} disabled={start.isPending} onChange={(event) => setScope(event.target.checked ? trip.id : null)} /><span>{t("관리 범위를 확인했어요. 예약 변경·취소와 결제는 별도이며, 이 데모에서는 실제 감시나 예약을 실행하지 않아요.", "I understand the scope. Booking changes, cancellations, and payments are separate. This preview does not monitor or book anything.")}</span></label>
            <Button variant="primary" disabled={!agreed || unresolved.length > 0 || start.isPending} onClick={() => start.mutate()}>{start.isPending ? t("시작하는 중…", "Starting…") : t("여행 관리 시작", "Start my trip")}<ArrowRight size={18} strokeWidth={1.6} aria-hidden="true" /></Button>
            {start.error && <p className={styles.error} role="alert">{start.error.message}</p>}
          </>}
        {unresolved.length > 0 && <>
          <p className={styles.error}>{t("미확인 항목을 해결해야 시작할 수 있어요.", "Resolve the items needing review before starting.")}</p>
          <Button disabled={retry.isPending} onClick={() => retry.mutate()}>{retry.isPending ? t("다시 요청하는 중…", "Retrying…") : t("검증 다시 시도", "Retry verification")}</Button>
          {retry.error && <p className={styles.error} role="alert">{retry.error.message}</p>}
        </>}
        <ButtonLink href={`${routes.newTrip}?from=${encodeURIComponent(tripId)}`}>{t("계획 수정 후 다시 확인", "Edit and check again")}</ButtonLink>
      </Panel>
    </div>
  </>;
}
