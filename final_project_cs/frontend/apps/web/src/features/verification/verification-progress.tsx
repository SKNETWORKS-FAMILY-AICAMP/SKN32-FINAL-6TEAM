"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ArrowRight, Check, CircleAlert } from "lucide-react";
import { Badge, Button, ButtonLink, PageHeading, Panel, QueryState } from "@/components/ui";
import { useTrip } from "@/features/trip/use-trip";
import { tripGateway, tripKey } from "@/lib/gateway";
import { routes } from "@/lib/routes";
import styles from "./verification.module.css";

const stageLabels = {
  pending: "대기",
  running: "진행 중",
  completed: "완료",
  failed: "중단",
};

export function VerificationProgress({ tripId }: { tripId: string }) {
  const tripQuery = useTrip(tripId);
  const queryClient = useQueryClient();
  const retry = useMutation({
    mutationFn: () => tripGateway.retryVerification(tripId),
    onSuccess: (trip) => queryClient.setQueryData(tripKey(tripId), trip),
  });
  const trip = tripQuery.data;

  if (!trip || tripQuery.error) {
    return <QueryState loading={tripQuery.isPending} error={tripQuery.error} retry={() => void tripQuery.refetch()} />;
  }

  const { verification } = trip;
  const failed = verification.status === "failed";
  const finished = verification.status === "completed";
  const needsReview = verification.results.some((result) => result.status === "needs_review");
  const completedStages = verification.stages.filter((stage) => stage.status === "completed").length;
  const currentStage = verification.stages.find((stage) => stage.status === "running" || stage.status === "failed");
  const progress = Math.round(Math.min(100, Math.max(0, verification.progress)));
  const heading = failed
    ? "검증이 잠시 중단되었어요"
    : finished
      ? needsReview ? "확인이 필요한 항목이 있어요" : "검증 결과가 준비되었어요"
      : "여행 계획을 확인하고 있어요";
  const stageHeading = failed
    ? `${currentStage?.label ?? "일정 검증"} 중단`
    : finished
      ? needsReview ? "검증 결과 확인 필요" : "전체 일정 검증 완료"
      : `${currentStage?.label ?? "여행 계획 확인"} 중`;

  return (
    <div className={styles.progressPage}>
      <PageHeading eyebrow="CHECKING YOUR PLAN" title={heading} description={trip.title} />
      <Panel>
        <div className={styles.progressTop}>
          <div>
            <span className={styles.muted}>전체 검증 진행률</span>
            <h2 className={styles.stageHeading} aria-live="polite" aria-atomic="true">{stageHeading}</h2>
          </div>
          <div className={styles.percent}>{progress}<small>%</small></div>
        </div>
        <div className={styles.track} role="progressbar" aria-label="전체 검증 진행률" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress} aria-valuetext={`${progress}% · ${stageHeading}`}>
          <div className={styles.trackFill} style={{ width: `${progress}%` }} />
        </div>
        <div className={styles.progressMeta}>
          <span>{verification.stages.length}개 단계 중 {completedStages}개 완료</span>
          <span>여행 계획 → 장소 → 이동 → 전체 일정</span>
        </div>
        <ol className={styles.stageList} aria-label="검증 단계">
          {verification.stages.map((stage, index) => (
            <li key={stage.id} className={`${styles.stage} ${stage.status === "running" ? styles.activeStage : ""} ${stage.status === "completed" ? styles.completedStage : ""}`} aria-current={stage.status === "running" ? "step" : undefined}>
              <span className={styles.stageCircle} aria-hidden="true">{stage.status === "completed" ? <Check size={15} /> : index + 1}</span>
              <div><h3>{stage.label}</h3><p>{stage.description}</p></div>
              <span className={styles.stageStatus}>{stageLabels[stage.status]}</span>
            </li>
          ))}
        </ol>
        {failed && <div className={styles.warning} role="alert"><CircleAlert size={18} aria-hidden="true" /><span>{verification.error || "검증을 완료하지 못했어요. 입력한 계획을 유지한 채 다시 시도할 수 있어요."}</span></div>}
        {finished && needsReview && <div className={styles.warning}><Badge tone="warning">확인 필요</Badge><span>모든 단계를 처리했지만 검증을 마치지 못한 항목이 있어요. 결과에서 확인해 주세요.</span></div>}
        {retry.error && <p className={styles.error} role="alert">{retry.error.message}</p>}
        <div className={styles.progressFooter}>
          <p>{failed ? "입력한 여행 계획과 확인된 내용은 보존돼요." : finished ? "결과를 확인한 뒤 여행 관리를 시작할 수 있어요." : "검증이 끝나면 결과를 확인할 수 있어요."}</p>
          {failed ? (
            <Button type="button" variant="primary" disabled={retry.isPending} onClick={() => retry.mutate()}>{retry.isPending ? "다시 요청하는 중…" : "검증 다시 시도"}</Button>
          ) : finished ? (
            <ButtonLink href={routes.results(tripId)} variant="primary">결과 확인 <ArrowRight size={16} aria-hidden="true" /></ButtonLink>
          ) : <Button type="button" variant="primary" disabled>결과 확인 <ArrowRight size={16} aria-hidden="true" /></Button>}
        </div>
      </Panel>
    </div>
  );
}
