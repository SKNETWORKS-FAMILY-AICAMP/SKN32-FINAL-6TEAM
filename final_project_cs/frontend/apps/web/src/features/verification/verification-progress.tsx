"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check } from "lucide-react";
import { Button, ButtonLink, Eyebrow, PageHeading, Panel, QueryState } from "@/components/ui";
import { useTrip } from "@/features/trip/use-trip";
import { tripGateway, tripKey } from "@/lib/gateway";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import styles from "./verification.module.css";

export function VerificationProgress({ tripId }: { tripId: string }) {
  const t = useT();
  const { language } = useSettings();
  const tripQuery = useTrip(tripId);
  const queryClient = useQueryClient();
  const retry = useMutation({
    mutationFn: () => tripGateway.retryVerification(tripId, language),
    onSuccess: (trip) => queryClient.setQueryData(tripKey(tripId, language), trip),
  });
  const trip = tripQuery.data;

  if (!trip || tripQuery.error) {
    return <QueryState loading={tripQuery.isPending} error={tripQuery.error} retry={() => void tripQuery.refetch()} />;
  }

  const { verification } = trip;
  const failed = verification.status === "failed";
  const ready = verification.status === "completed";
  const current = verification.stages.find((stage) => stage.status === "running" || stage.status === "failed");
  const progress = Math.round(Math.min(100, Math.max(0, verification.progress)));
  const stageState = { completed: t("완료", "Done"), running: t("확인 중", "Checking"), failed: t("중단", "Stopped"), pending: t("대기", "Next") };

  return <>
    <PageHeading eyebrow="A LITTLE CHECK, A BETTER JOURNEY"
      title={failed ? t("잠시 쉬어가는 중이에요.", "Let’s try that once more.") : ready ? t("여행 계획을 살펴봤어요.", "Your plan is ready to review.") : t("더 편한 여행을 준비해요.", "Getting your journey ready.")}
      description={t("계획부터 이동까지, 차근차근 확인하는 과정이에요.", "From your plan to travel details, one step at a time.")} />
    <Panel>
      <div className={styles.progressTop}>
        <div><Eyebrow>{t("여행 계획 확인", "CHECKING YOUR PLAN")}</Eyebrow><h2 aria-live="polite" aria-atomic="true">{ready ? t("결과가 준비되었어요", "Your results are ready") : current?.label}</h2></div>
        <strong className={styles.percent}>{progress}<small>%</small></strong>
      </div>
      <div className={styles.track} role="progressbar" aria-label={t("계획 확인 진행률", "Plan check progress")} aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}>
        <div className={styles.trackFill} style={{ width: `${progress}%` }} />
      </div>
      <ol className={styles.stageList}>
        {verification.stages.map((stage, index) => (
          <li key={stage.id} className={styles.stage} data-status={stage.status} aria-current={stage.status === "running" ? "step" : undefined}>
            <span className={styles.stageNumber} aria-hidden="true">{stage.status === "completed" ? <Check size={18} strokeWidth={1.6} /> : index + 1}</span>
            <div><h3>{stage.label}</h3><p>{stage.description}</p></div>
            <span className={styles.stageState}>{stageState[stage.status]}</span>
          </li>
        ))}
      </ol>
      {failed && <p className={styles.warning} role="alert">{verification.error}</p>}
      {retry.error && <p className={styles.error} role="alert">{retry.error.message}</p>}
      <div className={styles.actions}>
        <ButtonLink href={`${routes.newTrip}?from=${encodeURIComponent(tripId)}`}>{t("계획 보기", "View plan")}</ButtonLink>
        {failed
          ? <Button variant="primary" disabled={retry.isPending} onClick={() => retry.mutate()}>{retry.isPending ? t("다시 요청하는 중…", "Retrying…") : t("다시 시도하기", "Try again")}</Button>
          : ready
            ? <ButtonLink href={routes.results(tripId)} variant="primary">{t("결과 확인하기", "View results")}<ArrowRight size={18} strokeWidth={1.6} aria-hidden="true" /></ButtonLink>
            : <Button variant="primary" disabled>{t("결과 확인하기", "View results")}<ArrowRight size={18} strokeWidth={1.6} aria-hidden="true" /></Button>}
      </div>
    </Panel>
  </>;
}
