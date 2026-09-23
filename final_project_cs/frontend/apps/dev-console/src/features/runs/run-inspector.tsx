"use client";

import Link from "next/link";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Badge, Button, ButtonLink, Notice, Panel } from "@/components/ui";
import { gateway } from "@/lib/gateway";
import { TARGET_NAMES, type FactRow, type Run } from "@/lib/model";
import { queryKeys } from "@/lib/queries";
import styles from "./run-inspector.module.css";

type Props = { run: Run; onRetry?: (run: Run) => void; compact?: boolean };
const stepStatus = { pending: "대기", running: "진행 중", completed: "완료", failed: "실패" };

export function RunInspector(props: Props) { return <Inspector key={props.run.id} {...props} />; }

function Facts({ rows, empty }: { rows: FactRow[]; empty: string }) {
  if (!rows.length) return <p className={styles.muted}>{empty}</p>;
  return <table className={styles.table}><thead><tr><th scope="col">항목</th><th scope="col">값</th><th scope="col">기준·출처</th></tr></thead><tbody>{rows.map((row, index) => <tr key={`${row.label}-${index}`}><th scope="row">{row.label}</th><td>{row.value}</td><td>{row.reference || "—"}</td></tr>)}</tbody></table>;
}

function Inspector({ run, onRetry, compact = false }: Props) {
  const client = useQueryClient();
  const [selectedId, select] = useState<string>();
  const [tab, setTab] = useState<"input" | "observations" | "comparisons" | "output">("comparisons");
  const [name, setName] = useState(`${TARGET_NAMES[run.request.target]} ${run.request.input.time} 테스트`);
  const save = useMutation({ mutationFn: () => gateway.saveCase(run.id, name.trim()), onSuccess: () => client.invalidateQueries({ queryKey: queryKeys.cases }) });
  const selected = run.steps.find(step => step.id === selectedId) || run.steps.find(step => step.status === "running" || step.status === "failed") || run.steps.find(step => step.comparisons.length > 0) || run.steps[0];
  const finished = run.status !== "running";
  const completed = run.steps.filter(step => step.status === "completed").length;
  const badge = run.status === "failed" ? "실행 실패" : run.status === "running" ? `진행 중 · ${completed}/${run.steps.length} 단계` : "실행 완료";
  return <Panel title="실행 결과" aside={<span role="status"><Badge tone={run.status === "failed" ? "danger" : run.status === "completed" ? "success" : "neutral"}>{badge}</Badge></span>}>
    <div className={styles.meta}><code>{run.id}</code><span>{TARGET_NAMES[run.request.target]} · 샘플 {run.request.version}</span><span>샘플 실행 기록</span></div>
    {run.retryOf && <p className={styles.retryOf}>재실행 원본: <Link href={`/runs/${run.retryOf}`}>{run.retryOf}</Link></p>}
    {run.error && <div className={styles.error}><Notice tone="error">{run.error}</Notice></div>}
    <div className={`${styles.steps} ${compact ? styles.compact : ""}`} aria-label="실행 단계">
      {run.steps.map(step => <button type="button" key={step.id} className={styles.step} aria-pressed={selected?.id === step.id} onClick={() => select(step.id)}><span className={styles.stepMeta}>{step.phase + 1}구간 · {stepStatus[step.status]}</span><strong>{step.label}</strong><span>{TARGET_NAMES[step.owner]}</span></button>)}
    </div>
    {selected && <section className={styles.detail} aria-label="선택한 단계 상세"><div className={styles.detailTitle}><h3>{selected.label}</h3><Badge tone={selected.status === "failed" ? "danger" : "neutral"}>{stepStatus[selected.status]}</Badge></div>
      <div className={styles.tabs} aria-label="단계 기록 종류">{([ ["input", "입력"], ["observations", "조회값"], ["comparisons", "비교·판정"], ["output", "출력"] ] as const).map(([id, label]) => <button type="button" key={id} aria-pressed={tab === id} onClick={() => setTab(id)}>{label}</button>)}</div>
      {selected.status === "pending" || selected.status === "running" ? <Notice>이 단계가 {selected.status === "pending" ? "시작되면" : "완료되면"} 수집된 기록을 확인할 수 있습니다.</Notice> : <>
        {tab === "input" && <pre className={styles.json}>{JSON.stringify(selected.input, null, 2)}</pre>}
        {tab === "observations" && <Facts rows={selected.observations} empty="이 단계에서 조회한 외부 데이터가 없습니다." />}
        {tab === "comparisons" && <><Facts rows={selected.comparisons} empty="이 단계에는 조건 비교가 없습니다. 입력·조회값·출력 탭에서 기록을 확인하세요." /><div className={styles.summary}>{selected.summary}</div></>}
        {tab === "output" && <pre className={styles.json}>{JSON.stringify(selected.output, null, 2)}</pre>}
        {selected.error && <Notice tone="error">{selected.error}</Notice>}
        {selected.evidenceRefs.length > 0 && <p className={styles.evidence}>근거: {selected.evidenceRefs.join(" · ")}</p>}
      </>}
    </section>}
    {run.result && <section className={styles.result} aria-label="기대 결과 대조"><div className={styles.detailTitle}><h3>{run.result.actual}</h3><Badge tone={run.result.matched ? "success" : "danger"}>{run.result.matched ? "기대 결과 일치" : "기대 결과 불일치"}</Badge></div><p>기대 결과: {run.result.expected}</p><p>{run.result.summary}</p></section>}
    <div className={styles.actions}>{onRetry && finished && <Button onClick={() => onRetry(run)}>{run.status === "failed" ? "같은 입력으로 재실행" : "동일 조건 재실행"}</Button>}<ButtonLink href={`/runs/${run.id}`}>실행 상세 링크</ButtonLink></div>
    {finished && <details className={styles.save}><summary>테스트 사례로 저장</summary><form onSubmit={event => { event.preventDefault(); save.mutate(); }}><label htmlFor={`case-name-${run.id}`}>사례 이름</label><div className={styles.saveRow}><input id={`case-name-${run.id}`} value={name} onChange={event => setName(event.target.value)} required maxLength={100} /><Button type="submit" disabled={save.isPending || !name.trim()}>사례 저장</Button></div></form>{save.error && <Notice tone="error">{save.error.message}</Notice>}{save.data && <p role="status">사례를 저장했습니다. <Link href={`/cases?case=${save.data.id}`}>이 입력으로 A/B 비교하기</Link></p>}</details>}
  </Panel>;
}
