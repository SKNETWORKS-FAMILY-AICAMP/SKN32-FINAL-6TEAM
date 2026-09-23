"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState, useSyncExternalStore } from "react";
import { FlaskConical, Play, RotateCcw } from "lucide-react";
import { Badge, Button, Notice, PageHeading, Panel } from "@/components/ui";
import { RunInspector } from "@/features/runs/run-inspector";
import { defaultRequest, TEAM_IDS, TARGET_NAMES, type Run, type TestRequest, type TestTarget } from "@/lib/model";
import { useCreateRun, useRun, useTestCase } from "@/lib/queries";
import { testRequestSchema } from "@/lib/validation";
import styles from "./team-tests-screen.module.css";

const DRAFT_EVENT = "tripilot-console-draft-change";
const memoryDrafts = new Map<string, string>();

function subscribeDraft(listener: () => void) {
  window.addEventListener(DRAFT_EVENT, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(DRAFT_EVENT, listener);
    window.removeEventListener("storage", listener);
  };
}

function readDraft(key: string) {
  if (memoryDrafts.has(key)) return memoryDrafts.get(key)!;
  try {
    return window.sessionStorage.getItem(key);
  } catch {
    return memoryDrafts.get(key) ?? null;
  }
}

function saveDraft(key: string, scope: string, request: TestRequest) {
  const value = JSON.stringify({ scope, request });
  let persisted = true;
  try {
    window.sessionStorage.setItem(key, value);
    memoryDrafts.delete(key);
  } catch {
    memoryDrafts.set(key, value);
    persisted = false;
  }
  window.dispatchEvent(new Event(DRAFT_EVENT));
  return persisted;
}

function parseDraft(value: string | null, scope: string) {
  if (!value) return undefined;
  try {
    const stored = JSON.parse(value) as { scope?: unknown; request?: Partial<TestRequest> };
    if (stored.scope !== scope) return undefined;
    const request = stored.request;
    if (!request || !["activity", "dining", "mobility", "core"].includes(request.target ?? "")
      || !["A", "B"].includes(request.version ?? "")
      || !["normal", "tool-error"].includes(request.fixtureMode ?? "")
      || typeof request.input?.time !== "string"
      || !Number.isFinite(request.input.durationMinutes)
      || !["bus", "walk", "taxi"].includes(request.input.transport)) return undefined;
    // Drafts retain incomplete edits; execution applies the strict request schema.
    return request as TestRequest;
  } catch {
    return undefined;
  }
}

const getServerDraft = () => null;

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.";
}

export function TeamTestsScreen({ integration = false }: { integration?: boolean }) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const path = integration ? "/integration" : "/teams";
  const draftKey = `tripilot-dev-console:${integration ? "integration" : "team"}-draft:v1`;
  const runId = searchParams.get("run") || undefined;
  const caseId = searchParams.get("case") || undefined;
  const scope = caseId ? `case:${caseId}` : runId ? `run:${runId}` : "new";
  const runQuery = useRun(runId);
  const caseQuery = useTestCase(caseId);
  const createRun = useCreateRun();
  const storedDraft = useSyncExternalStore(subscribeDraft, () => readDraft(draftKey), getServerDraft);
  const [formError, setFormError] = useState<string | null>(null);
  const [storageWarning, setStorageWarning] = useState(false);
  const acceptsTarget = (target: TestTarget) => integration ? target === "core" : target !== "core";
  const sourceRequest = caseId ? caseQuery.data?.request : runQuery.data?.request;
  const draft = parseDraft(storedDraft, scope);
  const request = draft && acceptsTarget(draft.target)
    ? draft
    : sourceRequest && acceptsTarget(sourceRequest.target)
      ? sourceRequest
      : defaultRequest(integration ? "core" : "activity");
  const sourceLoading = caseId ? caseQuery.isPending : runId ? runQuery.isPending : false;
  const sourceError = caseId ? caseQuery.error : runId ? runQuery.error : null;
  const wrongTarget = Boolean(sourceRequest && !acceptsTarget(sourceRequest.target));
  const run = runQuery.data;
  const running = createRun.isPending || run?.status === "running";
  const disabled = running || sourceLoading || Boolean(sourceError) || wrongTarget;
  const changed = Boolean(run && JSON.stringify(run.request) !== JSON.stringify(request));
  const timeLabel = integration ? "이동 출발 시각" : request.target === "activity" ? "예상 도착 시각" : request.target === "dining" ? "예약 시각" : "출발 시각";
  const durationLabel = integration ? "식사·관람 시간 (분)" : request.target === "activity" ? "관람 시간 (분)" : "식사 시간 (분)";
  const targetLabel = integration || request.target === "mobility" ? "이동 구간" : "대상 장소";
  const targetPlace = integration || request.target === "mobility" ? "샘플 식당 B → 샘플 전시관 A" : request.target === "activity" ? "샘플 전시관 A" : "샘플 식당 B";

  function updateRequest(next: TestRequest) {
    setFormError(null);
    createRun.reset();
    setStorageWarning(!saveDraft(draftKey, scope, next));
  }

  function updateInput(change: Partial<TestRequest["input"]>) {
    updateRequest({ ...request, input: { ...request.input, ...change } });
  }

  function execute(next: TestRequest, retryOf?: string) {
    const checked = testRequestSchema.safeParse(next);
    if (!checked.success) {
      setFormError(checked.error.issues.map((issue) => issue.message).join(" "));
      return;
    }
    setFormError(null);
    createRun.mutate({ request: checked.data, retryOf }, {
      onSuccess: (created) => {
        setStorageWarning(!saveDraft(draftKey, `run:${created.id}`, created.request));
        router.replace(`${path}?run=${encodeURIComponent(created.id)}`, { scroll: false });
      },
    });
  }

  function retry(previous: Run) {
    if (!createRun.isPending) execute(previous.request, previous.id);
  }

  return (
    <div className={styles.page}>
      <PageHeading
        eyebrow="개발 작업공간"
        title={integration ? "코어 통합 테스트" : "에이전트 테스트"}
        description={integration ? "코어가 세 팀에 전달한 입력과 반환 결과를 같은 실행에서 확인하세요." : "입력부터 조회값, 비교, 출력까지 한 화면에서 확인하세요."}
        action={<Badge>{integration ? "세 팀 연결 샘플" : "단일 팀 실행"}</Badge>}
      />

      {!integration && (
        <div className={styles.teams} role="group" aria-label="에이전트팀 선택">
          {TEAM_IDS.map((team) => (
            <button
              key={team}
              type="button"
              aria-pressed={request.target === team}
              disabled={disabled}
              onClick={() => updateRequest({ ...defaultRequest(team), version: request.version, fixtureMode: request.fixtureMode })}
            >
              {TARGET_NAMES[team]}
            </button>
          ))}
        </div>
      )}

      {storageWarning && <Notice tone="warning">브라우저 저장소를 사용할 수 없어 현재 입력은 이 화면에서만 유지됩니다.</Notice>}
      {sourceError && (
        <Notice tone="error">
          <p>{caseId ? "테스트 사례" : "실행 기록"}를 불러오지 못했습니다. {errorMessage(sourceError)}</p>
          <div className={styles.recoveryActions}>
            <Button variant="secondary" onClick={() => void (caseId ? caseQuery.refetch() : runQuery.refetch())}>다시 불러오기</Button>
            <Link href={path}>새 테스트 입력 열기</Link>
          </div>
        </Notice>
      )}
      {wrongTarget && (
        <Notice tone="warning">
          이 {caseId ? "사례" : "실행"}는 {integration ? "팀별 테스트" : "코어 통합 테스트"}에서 확인할 수 있습니다.{" "}
          <Link href={`${integration ? "/teams" : "/integration"}?${caseId ? "case" : "run"}=${encodeURIComponent((caseId ?? runId)!)}`}>해당 테스트로 이동</Link>
        </Notice>
      )}

      <div className={styles.workspace}>
        <Panel title="테스트 입력" aside={<span className={styles.muted}>{TARGET_NAMES[request.target]}</span>}>
          <form className={styles.form} onSubmit={(event) => { event.preventDefault(); if (!disabled) execute(request); }}>
            {caseId && caseQuery.data && !wrongTarget && <p className={styles.caseLoaded}>불러온 사례 · {caseQuery.data.name}</p>}
            <label className={styles.field}>
              <span>{targetLabel}</span>
              <input value={targetPlace} readOnly aria-readonly="true" className={styles.fixedInput} />
            </label>
            {integration && <p className={styles.hint}>식당 예약 14:30 고정 · 이동 결과를 액티비티팀에 전달하는 샘플입니다.</p>}
            <label className={styles.field}>
              <span>{timeLabel}</span>
              <input type="time" required value={request.input.time} disabled={disabled} onChange={(event) => updateInput({ time: event.target.value })} />
            </label>
            {(integration || request.target !== "mobility") && (
              <label className={styles.field}>
                <span>{durationLabel}</span>
                <input type="number" required min={1} max={240} step={1} value={request.input.durationMinutes || ""} disabled={disabled} onChange={(event) => updateInput({ durationMinutes: Number(event.target.value) })} />
              </label>
            )}
            {(integration || request.target === "mobility") && (
              <label className={styles.field}>
                <span id="test-transport-label">선호 이동수단</span>
                <select aria-labelledby="test-transport-label" value={request.input.transport} disabled={disabled} onChange={(event) => updateInput({ transport: event.target.value as TestRequest["input"]["transport"] })}>
                  <option value="bus">버스</option>
                  <option value="walk">도보</option>
                  <option value="taxi">택시</option>
                </select>
              </label>
            )}
            <div className={styles.separator} />
            <label className={styles.field}>
              <span id="test-version-label">테스트 버전</span>
              <select aria-labelledby="test-version-label" value={request.version} disabled={disabled} onChange={(event) => updateRequest({ ...request, version: event.target.value as TestRequest["version"] })}>
                <option value="B">샘플 B · 개선 버전</option>
                <option value="A">샘플 A · 기준 버전</option>
              </select>
            </label>
            <label className={styles.field}>
              <span id="test-fixture-label">샘플 응답 조건</span>
              <select aria-labelledby="test-fixture-label" value={request.fixtureMode} disabled={disabled} onChange={(event) => updateRequest({ ...request, fixtureMode: event.target.value as TestRequest["fixtureMode"] })}>
                <option value="normal">정상 응답</option>
                <option value="tool-error">도구 조회 실패</option>
              </select>
            </label>
            <p className={styles.hint}>고정 샘플 응답 · Asia/Seoul<br />실제 모델·외부 API 호출 없음</p>
            {formError && <p role="alert" className={styles.formError}>{formError}</p>}
            {createRun.error && <p role="alert" className={styles.formError}>{errorMessage(createRun.error)}</p>}
            <Button type="submit" variant="primary" disabled={disabled}><Play size={15} aria-hidden="true" />{running ? "샘플 실행 중…" : "샘플 테스트 실행"}</Button>
            <Button type="button" variant="secondary" disabled={disabled} onClick={() => updateRequest(defaultRequest(request.target))}><RotateCcw size={14} aria-hidden="true" />기본 입력 불러오기</Button>
          </form>
        </Panel>

        <section className={styles.results} aria-label="테스트 실행 결과" aria-busy={sourceLoading}>
          {sourceLoading ? (
            <Panel title="실행 결과"><p role="status" className={styles.loading}>{caseId ? "테스트 사례" : "실행 기록"}를 불러오고 있습니다.</p></Panel>
          ) : run && !wrongTarget ? (
            <>
              {changed && <Notice tone="warning">입력이 변경되었습니다. 아래 결과는 이전 실행의 입력 기준입니다. 다시 실행하면 변경 사항이 반영됩니다.</Notice>}
              <RunInspector run={run} onRetry={retry} />
            </>
          ) : (
            <Panel title="실행 결과">
              <div className={styles.empty}>
                <span className={styles.emptyIcon}><FlaskConical size={28} strokeWidth={1.5} aria-hidden="true" /></span>
                <h2>입력을 확인하고 첫 테스트를 실행하세요</h2>
                <p>{integration ? "코어의 요청 전달, 팀별 조회, 결과 연결과 계약 확인 과정을 살펴볼 수 있습니다." : "팀을 선택하고 실행하면 전달된 입력, 가져온 값, 비교 기준과 최종 출력이 표시됩니다."}</p>
                <ol className={styles.emptySteps}>
                  <li><span>01</span>입력 전달</li>
                  <li><span>02</span>조회 응답</li>
                  <li><span>03</span>비교·판정</li>
                  <li><span>04</span>최종 출력</li>
                </ol>
                <p className={styles.emptyNote}>샘플 테스트는 버튼을 눌렀을 때 시작됩니다.</p>
              </div>
            </Panel>
          )}
        </section>
      </div>
      <div className={styles.footer}><span>{integration ? "호출 대상과 순서는 실제 코어 구현에 따라 달라집니다." : "같은 입력으로 반복 실행하고, 완료한 실행을 테스트 사례로 저장하세요."}</span><span>샘플 데이터 · Core 미연결</span></div>
    </div>
  );
}
