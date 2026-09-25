"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { Badge, Button, Notice, PageHeading, Panel } from "@/components/ui";
import { gateway } from "@/lib/gateway";
import { TARGET_NAMES, type Comparison, type SampleVersion, type TestCase } from "@/lib/model";
import { useCases, useComparison, useRun } from "@/lib/queries";
import styles from "./cases-workbench.module.css";

function inputSummary(testCase: TestCase) {
  const { target, input, fixtureMode } = testCase.request;
  const timeLabel = target === "dining" ? "방문 시각" : target === "activity" ? "도착 시각" : "출발 시각";
  const transport = { bus: "버스", walk: "도보", taxi: "택시" }[input.transport];
  const fields = [`${timeLabel} ${input.time}`];
  if (target !== "mobility") fields.push(`${target === "dining" ? "식사" : "체류"} ${input.durationMinutes}분`);
  if (target === "mobility" || target === "core") fields.push(transport);
  fields.push(fixtureMode === "normal" ? "정상 응답 샘플" : "도구 오류 샘플");
  return fields.join(" · ");
}

function CaseInput({ testCase }: { testCase: TestCase }) {
  const { target, fixtureMode, input } = testCase.request;
  return (
    <details className={styles.jsonDetails}>
      <summary>공통 요청 JSON 보기</summary>
      <p className={styles.help}>두 실행에 아래 값을 동일하게 전달하고, version만 각각 A와 B로 지정합니다.</p>
      <pre>{JSON.stringify({ target, fixtureMode, input }, null, 2)}</pre>
    </details>
  );
}

function VersionResult({ runId, version }: { runId: string; version: SampleVersion }) {
  const query = useRun(runId);
  const run = query.data;

  return (
    <section className={styles.versionCard} aria-label={`샘플 버전 ${version} 결과`}>
      <div className={styles.versionHeader}>
        <h3><span className={styles.versionLetter}>{version}</span> 샘플 버전 {version}</h3>
        {run && <Badge tone={run.status === "failed" ? "danger" : run.status === "completed" ? "success" : "neutral"}>
          {run.status === "failed" ? "실행 실패" : run.status === "completed" ? "실행 완료" : "실행 중"}
        </Badge>}
      </div>

      {query.isPending && <p className={styles.help} role="status">실행 기록을 불러오고 있어요.</p>}
      {query.isError && (
        <Notice tone="error">
          <p>{query.error.message}</p>
          <Button variant="secondary" onClick={() => void query.refetch()}>기록 다시 불러오기</Button>
        </Notice>
      )}
      {run && (
        <>
          <p className={styles.runId}>실행 ID · {run.id}</p>
          {run.status === "running" && (
            <div className={styles.pendingResult} role="status">
              <span className={styles.pulse} aria-hidden="true" />
              <div>
                <strong>{run.steps.find((step) => step.status === "running")?.label ?? "샘플 실행 준비 중"}</strong>
                <p>완료 후 실제 출력과 기대 결과를 비교합니다.</p>
              </div>
            </div>
          )}
          {run.status === "failed" && (
            <Notice tone="error">
              <p>{run.error ?? "실행 중 오류가 발생했습니다."}</p>
              <p>실행이 완료되지 않아 기대 결과와의 일치 여부를 판정하지 않았어요. 상세 화면에서 실패 단계를 확인하세요.</p>
            </Notice>
          )}
          {run.status === "completed" && run.result && (
            <>
              <div className={styles.matchStatus}>
                <span>기대 결과 비교</span>
                <Badge tone={run.result.matched ? "success" : "warning"}>
                  {run.result.matched ? "기대와 일치" : "기대와 불일치"}
                </Badge>
              </div>
              <dl className={styles.resultRows}>
                <div><dt>기대 결과</dt><dd>{run.result.expected}</dd></div>
                <div><dt>실제 출력</dt><dd>{run.result.actual}</dd></div>
              </dl>
              <p className={styles.resultSummary}>{run.result.summary}</p>
              {!run.result.matched && <p className={styles.help}>실행은 완료됐지만 기대 결과와 다른 출력을 반환했습니다.</p>}
            </>
          )}
          {run.status === "completed" && !run.result && <Notice tone="warning">완료된 실행에 비교 결과가 없습니다. 상세 기록을 확인하세요.</Notice>}
          <details className={styles.jsonDetails}>
            <summary>이 실행의 요청 JSON</summary>
            <pre>{JSON.stringify(run.request, null, 2)}</pre>
          </details>
          <Link className={styles.textLink} href={`/runs/${encodeURIComponent(run.id)}`}>버전 {version} 실행 상세 →</Link>
        </>
      )}
    </section>
  );
}

function ComparisonResults({ comparison }: { comparison: Comparison }) {
  return (
    <Panel title="A/B 비교 결과" aside={<Badge tone="neutral">샘플 실행</Badge>}>
      <div className={styles.snapshot}>
        <div className={styles.snapshotTop}>
          <strong>{comparison.caseSnapshot.name}</strong>
          <span>{TARGET_NAMES[comparison.caseSnapshot.request.target]}</span>
        </div>
        <p>{inputSummary(comparison.caseSnapshot)}</p>
        <p className={styles.help}>비교를 시작할 때 저장한 입력입니다. 위에서 다른 사례를 선택해도 이 실행의 입력은 바뀌지 않습니다.</p>
        <CaseInput testCase={comparison.caseSnapshot} />
      </div>
      <div className={styles.comparisonGrid}>
        <VersionResult key={comparison.runAId} runId={comparison.runAId} version="A" />
        <VersionResult key={comparison.runBId} runId={comparison.runBId} version="B" />
      </div>
    </Panel>
  );
}

export function CasesWorkbench() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const comparisonId = searchParams.get("comparison") ?? undefined;
  const requestedCaseId = searchParams.get("case");
  const casesQuery = useCases();
  const comparisonQuery = useComparison(comparisonId);
  const cases = casesQuery.data ?? [];
  const selectedId = requestedCaseId ?? comparisonQuery.data?.caseSnapshot.id;
  const selectedCase = selectedId ? cases.find((item) => item.id === selectedId) : cases[0];
  const builtInCount = cases.filter((item) => item.builtIn).length;
  const savedCount = cases.length - builtInCount;
  const createComparison = useMutation({
    mutationFn: (caseId: string) => gateway.createComparison(caseId),
    onSuccess: (comparison) => {
      router.push(`/cases?comparison=${encodeURIComponent(comparison.id)}&case=${encodeURIComponent(comparison.caseSnapshot.id)}`);
    },
  });

  function selectCase(id: string) {
    const nextParams = new URLSearchParams(searchParams.toString());
    nextParams.set("case", id);
    router.replace(`/cases?${nextParams.toString()}`, { scroll: false });
    createComparison.reset();
  }

  return (
    <div className={styles.workbench}>
      <PageHeading eyebrow="TEST CASES" title="테스트 사례 · 버전 비교" description="같은 입력을 다시 실행하고, 샘플 버전 A와 B가 반환한 값을 나란히 확인하세요." />
      <Notice tone="info">현재는 정해진 샘플 로직으로 진행되는 데모입니다. 실제 AI 모델을 호출하거나 모델 성능·비용을 측정하지 않습니다.</Notice>

      <div className={styles.workspaceGrid}>
        <Panel title="테스트 사례" aside={<span className={styles.count}>{cases.length}개</span>}>
          <p className={styles.help}>기본 사례 {builtInCount}개 · 직접 저장한 사례 {savedCount}개</p>
          {casesQuery.isPending && <p role="status" className={styles.help}>사례를 불러오고 있어요.</p>}
          {casesQuery.isError && (
            <Notice tone="error">
              <p>{casesQuery.error.message}</p>
              <Button variant="secondary" onClick={() => void casesQuery.refetch()}>사례 다시 불러오기</Button>
            </Notice>
          )}
          {casesQuery.isSuccess && cases.length === 0 && (
            <div className={styles.empty}>
              <strong>저장된 테스트 사례가 없어요.</strong>
              <p>팀 테스트 실행 상세에서 입력을 사례로 저장할 수 있습니다.</p>
              <Link className={styles.textLink} href="/teams">팀별 테스트 열기 →</Link>
            </div>
          )}
          <div className={styles.caseList}>
            {cases.map((item) => (
              <button key={item.id} className={`${styles.caseButton} ${selectedCase?.id === item.id ? styles.selected : ""}`} type="button" disabled={createComparison.isPending} aria-pressed={selectedCase?.id === item.id} onClick={() => selectCase(item.id)}>
                <span className={styles.caseMeta}>{TARGET_NAMES[item.request.target]}<span>{item.builtIn ? "기본 사례" : "저장한 사례"}</span></span>
                <strong>{item.name}</strong>
                <span className={styles.caseDescription}>{inputSummary(item)}</span>
              </button>
            ))}
          </div>
        </Panel>

        <Panel title="비교할 입력" aside={<Badge tone="neutral">동일 입력 · 두 버전</Badge>}>
          {selectedCase ? (
            <div className={styles.selectedInput}>
              <div>
                <h2 className={styles.caseTitle}>{selectedCase.name}</h2>
                <p className={styles.help}>{TARGET_NAMES[selectedCase.request.target]} · {selectedCase.builtIn ? "기본 테스트 사례" : "직접 저장한 테스트 사례"}</p>
              </div>
              <dl className={styles.inputRows}>
                <div><dt>입력 시각</dt><dd>{selectedCase.request.input.time}</dd></div>
                {selectedCase.request.target !== "mobility" && <div><dt>{selectedCase.request.target === "dining" ? "예정 식사 시간" : "체류 시간"}</dt><dd>{selectedCase.request.input.durationMinutes}분</dd></div>}
                {(selectedCase.request.target === "mobility" || selectedCase.request.target === "core") && <div><dt>이동 수단</dt><dd>{{ bus: "버스", walk: "도보", taxi: "택시" }[selectedCase.request.input.transport]}</dd></div>}
                <div><dt>도구 응답</dt><dd>{selectedCase.request.fixtureMode === "normal" ? "정상 샘플" : "오류 샘플"}</dd></div>
              </dl>
              <CaseInput testCase={selectedCase} />
              <p className={styles.help}>샘플 A와 B는 액티비티의 입장 마감 확인 여부가 다릅니다. 요식업·이동은 같은 로직을 사용하며, 입력에 따라 액티비티 결과도 같을 수 있습니다.</p>
              {createComparison.isError && <Notice tone="error">{createComparison.error.message} 다시 실행해 주세요.</Notice>}
              <div className={styles.actions}>
                <Button variant="primary" disabled={createComparison.isPending} onClick={() => createComparison.mutate(selectedCase.id)}>
                  {createComparison.isPending ? "비교 실행 준비 중…" : "A/B 비교 실행"}
                </Button>
                <Link className={styles.textLink} href={`${selectedCase.request.target === "core" ? "/integration" : "/teams"}?case=${encodeURIComponent(selectedCase.id)}`}>입력 불러오기 →</Link>
              </div>
            </div>
          ) : (
            <div className={styles.empty}>
              <strong>{selectedId && casesQuery.isSuccess ? "요청한 사례를 찾을 수 없어요." : "비교할 사례를 선택하세요."}</strong>
              <p>{selectedId && casesQuery.isSuccess ? "이 브라우저에 저장된 사례인지 확인하거나 목록에서 다른 사례를 선택하세요." : "실행 버튼을 눌러야 비교가 시작됩니다."}</p>
            </div>
          )}
        </Panel>
      </div>

      {comparisonId ? (
        <>
          {comparisonQuery.isPending && <Panel title="비교 기록"><p role="status">저장된 비교 기록을 불러오고 있어요.</p></Panel>}
          {comparisonQuery.isError && (
            <Notice tone="error">
              <p>{comparisonQuery.error.message}</p>
              <div className={styles.actions}>
                <Button variant="secondary" onClick={() => void comparisonQuery.refetch()}>비교 기록 다시 불러오기</Button>
                <Link className={styles.textLink} href="/cases">사례 목록으로 돌아가기</Link>
              </div>
            </Notice>
          )}
          {comparisonQuery.data && <ComparisonResults comparison={comparisonQuery.data} />}
        </>
      ) : (
        <Panel>
          <div className={styles.comparisonEmpty}>
            <span className={styles.emptyMark} aria-hidden="true">A / B</span>
            <div><strong>한 가지 입력으로 두 버전을 비교하세요.</strong><p>실행 상태와 기대 결과의 일치 여부를 구분해서 보여줍니다. 각 실행을 열면 조회값과 비교 근거까지 확인할 수 있어요.</p></div>
          </div>
        </Panel>
      )}
    </div>
  );
}
