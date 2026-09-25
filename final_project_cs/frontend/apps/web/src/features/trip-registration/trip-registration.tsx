"use client";

import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { Button, ButtonLink, PageHeading, QueryState, RegistrationSteps } from "@/components/ui";
import { DATA_MODE, SAMPLE_PLAN, tripGateway } from "@/lib/gateway";
import { tripKey } from "@/features/trip/use-trip";
import type { DemoScenario } from "@/features/trip/model";
import { routes } from "@/lib/routes";
import styles from "./trip-registration.module.css";

const sourceSchema = z.string().trim().min(1, "시간과 장소가 있는 여행 계획을 입력해 주세요.").max(12000, "여행 계획은 12,000자 이내로 입력해 주세요.");
const draftKey = "tripilot.web.registration-draft.v1";

export function TripRegistration() {
  const from = useSearchParams().get("from");
  const router = useRouter();
  const queryClient = useQueryClient();
  const [source, setSource] = useState<{ origin: string | null; value: string }>();
  const [scenario, setScenario] = useState<DemoScenario>("success");
  const [validation, setValidation] = useState("");
  const [draftWarning, setDraftWarning] = useState("");
  const draft = useQuery({
    queryKey: ["registration-draft", from],
    queryFn: async () => {
      if (from) return (await tripGateway.getTrip(from)).source;
      try { return sessionStorage.getItem(draftKey) ?? ""; }
      catch { return ""; }
    },
    retry: false,
    staleTime: Infinity,
  });
  const value = source?.origin === from ? source.value : draft.data ?? "";
  const create = useMutation({
    mutationFn: () => tripGateway.createTrip({ source: value, scenario }),
    onSuccess: (trip) => {
      queryClient.setQueryData(tripKey(trip.id), trip);
      router.push(routes.verification(trip.id));
    },
  });

  function updateSource(next: string) {
    setSource({ origin: from, value: next });
    queryClient.setQueryData(["registration-draft", from], next);
    if (from) queryClient.setQueryData(["registration-draft", null], next);
    setValidation("");
    create.reset();
    try { sessionStorage.setItem(draftKey, next); setDraftWarning(""); }
    catch { setDraftWarning("임시 저장을 사용할 수 없어요. 이 화면을 닫으면 입력 내용이 사라질 수 있어요."); }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (create.isPending) return;
    const parsed = sourceSchema.safeParse(value);
    if (!parsed.success) { setValidation(parsed.error.issues[0].message); return; }
    setValidation("");
    create.mutate();
  }

  if (draft.isPending || draft.error) return <QueryState loading={draft.isPending} error={draft.error} retry={() => void draft.refetch()} />;
  const error = validation || create.error?.message;

  return <div className={styles.container}><form onSubmit={submit} className={styles.form} noValidate>
    <div className={styles.editor}>
      <RegistrationSteps current={0} />
      <PageHeading eyebrow="NEW TRIP" title="준비한 여행 계획을 알려주세요" />
      <div className={styles.labelRow}><label htmlFor="plan-source">여행 계획 <span>필수</span></label>{DATA_MODE === "demo" && <Button variant="quiet" onClick={() => updateSource(SAMPLE_PLAN)} disabled={create.isPending}>예시 계획 불러오기</Button>}</div>
      <textarea id="plan-source" name="planSource" value={value} onChange={(event) => updateSource(event.target.value)} disabled={create.isPending} maxLength={12000} required aria-invalid={Boolean(error)} aria-describedby={`plan-format${error ? " plan-error" : ""}`} placeholder={"일차 제목에 날짜를 적고, 시간과 장소를 나누어 적어주세요.\n\n1일차 · 2026-09-15\n09:00 호텔 조식\n13:00 점심 식당 · 예약 있음\n\n2일차 · 2026-09-16\n10:00 박물관 관람"} />
      <div className={styles.inputMeta}><p id="plan-format">일차별 날짜와 시간·장소를 함께 적어 주세요.</p><span>{value.length.toLocaleString()} / 12,000</span></div>
      {error && <p id="plan-error" className={styles.error} role="alert">{error}</p>}
      {draftWarning && <p className={styles.warning} role="status">{draftWarning}</p>}
      {DATA_MODE === "demo" && <details className={styles.demoOptions}><summary>데모 검증 응답 설정</summary><label htmlFor="demo-scenario">체험할 결과</label><select id="demo-scenario" value={scenario} disabled={create.isPending} onChange={(event) => setScenario(event.target.value as DemoScenario)}><option value="success">검증 완료 · 여러 결과</option><option value="needs-review">검증 완료 · 미확인 항목 포함</option><option value="failed">검증 도중 실패 · 재시도</option></select><p>실제 지도를 연결한 경우, 일정 끝에 [좌표: 위도, 경도]를 적으면 해당 위치에 핀을 표시해요.</p></details>}
    </div>
    <div className={styles.actions}><ButtonLink href={routes.home}>← 내 여행</ButtonLink><span>필수 정보는 날짜 · 여행 계획</span><Button variant="primary" type="submit" disabled={create.isPending}>{create.isPending ? "등록 중…" : "검증 하기 →"}</Button></div>
  </form></div>;
}
