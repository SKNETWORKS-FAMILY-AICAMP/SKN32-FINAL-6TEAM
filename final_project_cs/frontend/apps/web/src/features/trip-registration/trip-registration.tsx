"use client";

import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Button, ButtonLink, Eyebrow, PageHeading, Panel, QueryState } from "@/components/ui";
import { mapConfiguration } from "@/features/map/config";
import { partyLabel } from "@/features/onboarding/model";
import { useOnboarding } from "@/features/onboarding/onboarding-state";
import { toSurvey } from "@/features/onboarding/payload";
import type { DemoScenario } from "@/features/trip/model";
import { tripKey, tripsKey } from "@/features/trip/use-trip";
import { DATA_MODE, SAMPLE_PLANS, tripGateway } from "@/lib/gateway";
import { submitIntake } from "@/lib/live/intake";
import { routes } from "@/lib/routes";
import { useSettings, useT } from "@/lib/settings";
import styles from "./trip-registration.module.css";

const draftKey = "tripilot.web.registration-draft.v1";

function Preferences() {
  const t = useT();
  const [{ complete, answers }] = useOnboarding();
  if (!complete) return null;
  const labels: Record<string, string> = { food: t("맛집 탐방", "Food"), nature: t("자연과 힐링", "Nature"), culture: t("문화와 역사", "Culture"), activity: t("액티비티", "Activities"), shopping: t("쇼핑", "Shopping"), local: t("로컬 일상", "Local life") };
  return <><div className={styles.preferences}>
    <Eyebrow>{t("함께 고른 여행 취향", "YOUR TRAVEL PREFERENCES")}</Eyebrow>
    <div className={styles.tags}>{answers.theme && <span className={styles.pill}>{labels[answers.theme]}</span>}{answers.party && <span className={styles.pill}>{partyLabel(answers, t)}</span>}</div>
    <p>{t("홈에서 고른 취향을 이 여행과 함께 이어가요.", "The preferences you chose stay with this journey.")}</p>
  </div><hr /></>;
}

export function TripRegistration() {
  const t = useT();
  const { language } = useSettings();
  const [onboarding] = useOnboarding();
  const from = useSearchParams().get("from");
  const router = useRouter();
  const queryClient = useQueryClient();
  const [source, setSource] = useState<{ origin: string | null; value: string }>();
  const [scenario, setScenario] = useState<DemoScenario>("success");
  const [validation, setValidation] = useState("");
  const [draftWarning, setDraftWarning] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const live = DATA_MODE === "live";
  const draft = useQuery({
    queryKey: ["registration-draft", from],
    queryFn: async () => {
      if (from) return (await tripGateway.getTrip(from, language)).source;
      try { return sessionStorage.getItem(draftKey) ?? ""; }
      catch { return ""; }
    },
    retry: false,
    staleTime: Infinity,
  });
  const value = source?.origin === from ? source.value : draft.data ?? "";
  const create = useMutation({
    // The survey rides with the registration (backend `constraints.survey`), only once onboarding is finished.
    mutationFn: () => tripGateway.createTrip({ source: value, scenario, ...(onboarding.complete && { survey: toSurvey(onboarding.answers) }) }, language),
    onSuccess: (trip) => {
      queryClient.setQueryData(tripKey(trip.id, language), trip);
      // Drop the cached list: the home card and "My trips" read it again instead of showing it without this trip.
      queryClient.removeQueries({ queryKey: tripsKey });
      router.push(routes.verification(trip.id));
    },
  });
  // ★실제 연결 — 글·파일을 계획 읽기로 보내고 확인 화면으로 간다. 등록은 확인 화면의 「등록하고 관리 시작」이 한다.
  const intake = useMutation({
    mutationFn: () => submitIntake(value, files, language),
    onSuccess: (result) => router.push(routes.intake(result.intake_id)),
  });
  const pending = create.isPending || intake.isPending;

  function updateSource(next: string) {
    setSource({ origin: from, value: next });
    queryClient.setQueryData(["registration-draft", from], next);
    if (from) queryClient.setQueryData(["registration-draft", null], next);
    setValidation("");
    create.reset();
    intake.reset();
    try { sessionStorage.setItem(draftKey, next); setDraftWarning(""); }
    catch { setDraftWarning(t("임시 저장을 사용할 수 없어요. 이 화면을 닫으면 입력 내용이 사라질 수 있어요.", "Drafts cannot be saved here. Closing this page may lose your input.")); }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    if (!value.trim() && !(live && files.length)) { setValidation(t("시간과 장소가 있는 여행 계획을 입력해 주세요.", "Enter a travel plan with times and places.")); return; }
    setValidation("");
    if (live) intake.mutate(); else create.mutate();
  }

  if (draft.isPending || draft.error) return <QueryState loading={draft.isPending} error={draft.error} retry={() => void draft.refetch()} />;
  const error = validation || create.error?.message || intake.error?.message;
  const demo = DATA_MODE === "demo";

  return <>
    <PageHeading eyebrow="A PLAN THAT FEELS LIKE YOU" title={t("이제, 여행을 담아볼까요?", "Let’s put your trip together.")}
      description={t("준비한 계획을 그대로 붙여 넣어 주세요.\n하나씩 살펴보고, 편안한 여행으로 이어갈게요.", "Paste the plan you have prepared.\nWe’ll walk through it, one step at a time.")} />
    <form onSubmit={submit} noValidate>
      <div className={styles.layout}>
        <Panel className={styles.editor}>
          <div className={styles.labelRow}>
            <label htmlFor="plan-source">{t("나의 여행 계획", "Your travel plan")}</label>
            {demo && <Button variant="quiet" className={styles.sample} onClick={() => updateSource(SAMPLE_PLANS[language])} disabled={pending}>{t("예시 불러오기", "Load example")}</Button>}
          </div>
          <textarea id="plan-source" name="planSource" className={styles.input} value={value} onChange={(event) => updateSource(event.target.value)} disabled={pending} maxLength={12000} required aria-invalid={Boolean(error)} aria-describedby={`plan-format${error ? " plan-error" : ""}`}
            placeholder={t("1일차 · 2026-09-15\n09:00 호텔 조식\n13:00 점심 식당 · 예약 있음\n\n2일차 · 2026-09-16\n10:00 박물관 관람", "DAY 1 · 2026-09-15\n09:00 Hotel breakfast\n13:00 Lunch restaurant · reserved\n\nDAY 2 · 2026-09-16\n10:00 Museum visit")} />
          <div className={styles.inputMeta}><span id="plan-format">{t("날짜 · 시간 · 장소를 함께 적어 주세요.", "Include dates, times, and places.")}</span><span>{value.length.toLocaleString()} / 12,000</span></div>
          {live && <div className={styles.files}>
            <label htmlFor="plan-files">{t("사진 · PDF · 워드 · 엑셀로 된 계획도 올릴 수 있어요 (최대 5개, 한 개 10MB)", "You can also upload a photo, PDF, Word or Excel plan (up to 5 files, 10MB each)")}</label>
            <input id="plan-files" type="file" multiple accept="image/*,.pdf,.docx,.xlsx,.txt" disabled={pending}
              onChange={(event) => { setFiles(Array.from(event.target.files ?? []).slice(0, 5)); setValidation(""); intake.reset(); }} />
            {files.length > 0 && <p>{files.map((file) => file.name).join(" · ")}</p>}
          </div>}
          {error && <p id="plan-error" className={styles.error} role="alert">{error}</p>}
          {draftWarning && <p className={styles.warning} role="status">{draftWarning}</p>}
        </Panel>
        <aside className={styles.tips}>
          <Panel>
            <Preferences />
            <h2>{t("작은 준비, 더 편한 여행", "A little preparation goes a long way")}</h2>
            <ol className={styles.tipList}>
              <li>{t("일차 제목에 날짜를 적어요.", "Start each day with a date.")}</li>
              <li>{t("시작 시간과 장소를 한 줄씩 적어요.", "Write each start time and place on a new line.")}</li>
              <li>{t("예약한 일정은 ‘예약 있음’으로 표시해요.", "Mark reserved plans with “reserved”.")}</li>
            </ol>
          </Panel>
          {demo && <details className={styles.demoOptions}>
            <summary>{t("데모 체험 옵션", "Preview options")}</summary>
            <label htmlFor="demo-scenario">{t("검증 결과 시나리오", "Verification scenario")}</label>
            <select id="demo-scenario" value={scenario} disabled={pending} onChange={(event) => setScenario(event.target.value as DemoScenario)}>
              <option value="success">{t("검증 완료", "Completed")}</option>
              <option value="needs-review">{t("확인이 필요한 항목", "Items needing review")}</option>
              <option value="failed">{t("검증 중단 후 재시도", "Failure and retry")}</option>
            </select>
            <p>{t("준비된 응답으로 화면 흐름을 체험해요.", "Explore the flow with prepared responses.")}{mapConfiguration.provider !== "demo" && ` ${t("일정 끝에 [좌표: 위도, 경도]를 적으면 지도에 핀으로 표시해요.", "Add [좌표: latitude, longitude] to a stop to pin it on the map.")}`}</p>
          </details>}
        </aside>
      </div>
      <div className={styles.actions}>
        <ButtonLink href={routes.start}><ArrowLeft size={18} strokeWidth={1.6} aria-hidden="true" />{t("이전", "Back")}</ButtonLink>
        <span className={styles.actionNote}>{t("입력한 계획은 화면을 오가도 유지돼요.", "Your draft stays while you explore.")}</span>
        <Button variant="primary" type="submit" disabled={pending}>{pending ? t("확인을 시작하는 중…", "Starting the check…") : t("계획 확인하기", "Check my plan")}<ArrowRight size={18} strokeWidth={1.6} aria-hidden="true" /></Button>
      </div>
    </form>
  </>;
}
