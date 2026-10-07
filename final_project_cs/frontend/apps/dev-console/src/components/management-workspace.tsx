"use client";

import Link from "next/link";
import { useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Badge, Button, Notice, PageHeading, Panel, QueryState } from "@/components/ui";
import { managementGateway } from "@/lib/management-gateway";
import { INCIDENT_SEVERITY, INCIDENT_SOURCE, INCIDENT_STATUS, filterIncidents, incidentEventCount, incidentSources, type ManagementIncident, type ManagementSnapshot } from "@/lib/management";
import styles from "./management-workspace.module.css";

function statusTone(incident: ManagementIncident) {
  return incident.status === "resolved" ? "success" : incident.status === "new" ? "warning" : "neutral";
}

function affectedUsers(incident: ManagementIncident) {
  return incident.affectedUsers === null ? "미수집" : `${incident.affectedUsers}명`;
}

function IncidentBadges({ incident }: { incident: ManagementIncident }) {
  return <div className={styles.badges}><Badge tone={statusTone(incident)}>{INCIDENT_STATUS[incident.status]}</Badge><Badge tone={incident.severity === "high" ? "danger" : incident.severity === "medium" ? "warning" : "neutral"}>심각도 {INCIDENT_SEVERITY[incident.severity]}</Badge><span>{incidentSources(incident).map(source => INCIDENT_SOURCE[source]).join(" · ")}</span></div>;
}

function ManagementHome({ snapshot }: { snapshot: ManagementSnapshot }) {
  const incidents = snapshot.incidents;
  const metrics = [
    { label: "확인 전 오류 묶음", value: incidents.filter(item => item.status === "new").length, href: "/?view=errors&status=new" },
    { label: "미해결 오류 묶음", value: incidents.filter(item => item.status !== "resolved").length },
    { label: "전체 오류 묶음", value: incidents.length, href: "/?view=errors" },
    { label: "가상 발생 건수", value: incidents.reduce((total, item) => total + incidentEventCount(item), 0) },
  ];
  return <>
    <PageHeading eyebrow="MANAGEMENT / M-01" title="관리 홈" description="문제를 찾고 기록을 확인하는 개발자용 관리 작업공간입니다." />
    <div className={styles.metrics}>{metrics.map(metric => <div className={styles.metric} key={metric.label}><span>{metric.label}</span><strong>{metric.value}</strong>{metric.href && <Link href={metric.href}>목록 보기 →</Link>}</div>)}</div>
    <Panel title="먼저 확인할 오류"><p className={styles.help}>확인 전인 가상 오류 묶음입니다. 발생 건수와 영향 사용자 수는 서로 다른 값입니다.</p><div className={styles.incidentList}>{incidents.filter(item => item.status === "new").map(incident => <article className={styles.incident} key={incident.id}><div><Link className={styles.incidentTitle} aria-label={`${incident.code} ${incident.title}`} href={`/?view=errors&incident=${encodeURIComponent(incident.id)}`}><code>{incident.code}</code><strong>{incident.title}</strong></Link><p className={styles.help}>{incident.module} · 발생 {incidentEventCount(incident)}건 · 영향 {affectedUsers(incident)}</p></div><IncidentBadges incident={incident} /></article>)}</div></Panel>
    <div className={styles.twoColumns}><Panel title="연결과 수집 상태"><Notice tone="warning">실제 서버 연결 상태와 오류 기록은 미수집입니다.</Notice><p className={styles.help}>API·DB·모델 상태, 상시 작업 회차, 전체 영향 사용자의 중복 제거 집계는 후속 연동이 필요합니다.</p><Link href="/connections">연결 안내 확인 →</Link></Panel><Panel title="기존 검증 도구"><p>샘플 입력과 기대 결과를 확인하는 시험 도구를 계속 사용할 수 있습니다.</p><div className={styles.toolLinks}><Link href="/teams">팀별 테스트</Link><Link href="/integration">코어 통합 테스트</Link><Link href="/cases">사례·버전 비교</Link></div><p className={styles.help}>이 오류의 실제 재현이나 해결 처리와 연결되지는 않습니다.</p></Panel></div>
  </>;
}

function IncidentDetail({ incident, occurrenceId, href }: { incident: ManagementIncident; occurrenceId: string | null; href: (patch: Record<string, string | null>) => string }) {
  const occurrence = occurrenceId ? incident.occurrences.find(item => item.reference === occurrenceId) : incident.occurrences[0];
  const count = incidentEventCount(incident);
  const maxCount = Math.max(1, ...incident.hourlyCounts);
  return <>
    <Link href={href({ incident: null, occurrence: null })}>← 검색 조건을 유지한 오류 목록</Link>
    <PageHeading eyebrow="MANAGEMENT / M-03" title={incident.title} description={`${incident.code} · ${incident.module}`} />
    <IncidentBadges incident={incident} />
    <Panel title="오류 묶음 요약"><dl className={styles.facts}><div><dt>묶음 식별자</dt><dd><code>{incident.id}</code></dd></div><div><dt>가상 발생 건수</dt><dd>{count}건</dd></div><div><dt>영향 사용자</dt><dd>{affectedUsers(incident)}</dd></div><div><dt>처음 · 마지막 발생</dt><dd>{incident.firstSeen} · {incident.lastSeen}</dd></div></dl><Notice>상태 변경·담당 지정·티켓 연결·오류 재현은 후속 연동이 필요합니다. 현재는 가상 기록을 읽기만 합니다.</Notice></Panel>
    <Panel title="시간별 가상 발생 건수"><p className={styles.help}>가상 운영일 00시부터 14시까지의 기록입니다.</p><div className={styles.chart} role="img" aria-label={incident.hourlyCounts.map((value, hour) => `${hour}시 ${value}건`).join(", ")}>{incident.hourlyCounts.map((value, hour) => <div className={styles.chartColumn} key={hour}><span className={styles.chartValue}>{value}</span><div className={styles.barTrack}><span style={{ height: `${value / maxCount * 100}%` }} /></div><span>{hour}</span></div>)}</div></Panel>
    {incident.hint && <Notice tone="warning"><strong>원인 후보 · 가상 예시</strong><p>{incident.hint}</p></Notice>}
    <Panel title="발생 상세"><p className={styles.help}>샘플 상세 {incident.occurrences.length}건 / 가상 발생 {count}건. {count - incident.occurrences.length}건의 상세는 예시에 포함되지 않았습니다.</p>
      {occurrenceId && !occurrence && <Notice tone="error">요청한 발생 기록을 찾을 수 없습니다. 발생 기록 목록을 확인하세요.</Notice>}
      {incident.occurrences.length === 0 ? <Notice>이 묶음에는 발생 상세 예시가 없습니다. 오류가 없다는 뜻은 아닙니다.</Notice> : <>
        <div className={styles.occurrences} aria-label="발생 기록 선택">{incident.occurrences.map(item => <Link key={item.reference} href={href({ occurrence: item.reference })} aria-current={occurrence?.reference === item.reference ? "true" : undefined}><code>{item.reference}</code><span>{item.occurredAt} · {INCIDENT_SOURCE[item.source]}</span></Link>)}</div>
        {occurrence && <section className={styles.occurrenceDetail} aria-label="선택한 발생 상세"><h3><code>{occurrence.reference}</code> · {occurrence.occurredAt}</h3><dl className={styles.facts}><div><dt>요청 추적 번호</dt><dd><code>{occurrence.traceId}</code></dd></div><div><dt>사용자 키 해시</dt><dd>{occurrence.userHash ?? "기록 없음 · 상시 작업"}</dd></div><div><dt>여행 ID</dt><dd>{occurrence.tripId ?? "기록 없음"}</dd></div><div><dt>Case ID</dt><dd>{occurrence.caseId ?? "기록 없음"}</dd></div></dl><h3>가린 스택 · 가상 예시</h3><pre className={styles.stack}>{incident.maskedStack ?? "스택 예시가 없습니다."}</pre><p className={styles.help}>실제 고객 메시지·원문·비밀 키를 포함하지 않는 고정 예시입니다. 요청 추적과 실제 환경 상세는 후속 연동이 필요합니다.</p></section>}
      </>}
    </Panel>
  </>;
}

export function ManagementWorkspace() {
  const router = useRouter();
  const searchForm = useRef<HTMLFormElement>(null);
  const searchParams = useSearchParams();
  const query = useQuery({ queryKey: ["management-snapshot"], queryFn: () => managementGateway.getSnapshot() });
  const view = searchParams.get("view") ?? "home";
  const filters = { query: searchParams.get("q") ?? "", status: searchParams.get("status") ?? "", severity: searchParams.get("severity") ?? "", source: searchParams.get("source") ?? "" };
  const incidentId = searchParams.get("incident");
  const snapshot = query.data;

  function href(patch: Record<string, string | null>) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("view", "errors");
    Object.entries(patch).forEach(([key, value]) => { if (value) params.set(key, value); else params.delete(key); });
    return `/?${params.toString()}`;
  }

  function setFilter(key: string, value: string) {
    router.replace(href({ [key]: value, incident: null, occurrence: null }), { scroll: false });
  }

  const visible = snapshot ? filterIncidents(snapshot.incidents, filters) : [];
  const selected = snapshot?.incidents.find(item => item.id === incidentId);
  return <div className={styles.workspace}>
    <nav className={styles.tabs} aria-label="관리 화면 선택"><Link href="/" aria-current={view === "home" ? "page" : undefined}>관리 홈</Link><Link href={href({ incident: null, occurrence: null })} aria-current={view === "errors" ? "page" : undefined}>오류 목록</Link></nav>
    <QueryState loading={query.isPending} error={query.error} retry={() => void query.refetch()} />
    {snapshot && <><Notice tone="warning"><strong>가상 오류 예시 · 실제 운영 데이터 아님</strong><p>기준: {snapshot.asOf}. 실제 API·오류 수집·운영 앱과 연결되지 않았습니다.</p></Notice>
      {view === "home" ? <ManagementHome snapshot={snapshot} /> : view !== "errors" ? <Notice tone="error">요청한 관리 화면을 찾을 수 없습니다. <Link href="/">관리 홈으로 돌아가기</Link></Notice> : incidentId ? selected ? <IncidentDetail incident={selected} occurrenceId={searchParams.get("occurrence")} href={href} /> : <Notice tone="error">요청한 오류 묶음을 찾을 수 없습니다. <Link href={href({ incident: null, occurrence: null })}>검색 조건을 유지한 오류 목록으로 돌아가기</Link></Notice> : <>
        <PageHeading eyebrow="MANAGEMENT / M-02" title="오류 목록" description="참조번호·요청 추적 번호·오류 코드·제목으로 원인 묶음을 찾습니다." />
        <Panel title="검색과 필터"><form ref={searchForm} className={styles.search} onSubmit={event => { event.preventDefault(); const data = new FormData(event.currentTarget); setFilter("q", String(data.get("q") ?? "").trim()); }}><label htmlFor="incident-search">오류 검색<input id="incident-search" key={filters.query} name="q" defaultValue={filters.query} placeholder="ERR-7F3A2C · tr_… · LLM_TIMEOUT" /></label><Button type="submit" variant="primary">검색</Button></form>
          <div className={styles.filters}>{([
            ["status", "처리 상태", INCIDENT_STATUS], ["severity", "심각도", INCIDENT_SEVERITY], ["source", "발생 출처", INCIDENT_SOURCE],
          ] as const).map(([key, label, options]) => <div className={styles.filterField} key={key}><label htmlFor={`incident-${key}`}>{label}</label><select id={`incident-${key}`} value={filters[key]} onChange={event => setFilter(key, event.target.value)}><option value="">전체</option>{Object.entries(options).map(([value, text]) => <option key={value} value={value}>{text}</option>)}</select></div>)}<Link href="/?view=errors" onClick={() => searchForm.current?.reset()}>검색·필터 초기화</Link></div>
        </Panel>
        <Panel title="조회 결과"><p className={styles.help} role="status">현재 조건 {visible.length} / 전체 {snapshot.incidents.length}개 묶음</p>
          {visible.length === 0 ? <div className={styles.empty}><strong>조건에 맞는 오류 묶음이 없습니다.</strong><p>검색어와 필터를 확인하거나 초기화하세요.</p><Link href="/?view=errors" onClick={() => searchForm.current?.reset()}>전체 오류 목록 보기</Link></div> : <div className={styles.incidentList}>{visible.map(incident => {
            const matchedOccurrence = filters.query.trim() ? incident.occurrences.find(item => [item.reference, item.traceId].some(value => value.toLowerCase().includes(filters.query.trim().toLowerCase()))) : undefined;
            return <article key={incident.id} className={styles.incident}><div><Link className={styles.incidentTitle} aria-label={`${incident.code} ${incident.title}`} href={href({ incident: incident.id, occurrence: matchedOccurrence?.reference ?? null })}><code>{incident.code}</code><strong>{incident.title}</strong></Link><p className={styles.help}>{incident.module} · {incident.firstSeen}–{incident.lastSeen}</p><p className={styles.help}>가상 발생 {incidentEventCount(incident)}건 · 영향 {affectedUsers(incident)}</p>{matchedOccurrence && <p className={styles.help}>이 묶음의 발생: <code>{matchedOccurrence.reference}</code></p>}</div><IncidentBadges incident={incident} /></article>;
          })}</div>}
        </Panel>
      </>}
    </>}
  </div>;
}
