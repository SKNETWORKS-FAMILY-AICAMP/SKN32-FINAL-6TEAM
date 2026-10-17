'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { operationSimulations } from '../../lib/gateway';
import styles from './simulation.module.css';

type Mode = 'actual' | 'simulation' | 'all';
type Period = { from: string; to: string };
type Target = { trip_id: string; item_id: string; title: string; starts_at: string; ends_at: string | null; reason: string };
type Receipt = {
  id: string; received_at: string; mode: Exclude<Mode, 'all'>; record_type: string; category: string;
  status: string; source: string | null; trip_id: string | null; target_title: string | null;
  stage: string; text: string | null; published_at: string | null; regions: string[]; payload: Record<string, unknown>;
};
type Receipts = {
  statuses: { region: string; status: string; observed_at: string; fetched_at: string | null; from_cache: boolean; count: number; error_code?: string }[];
  history?: { records: Receipt[]; total: number; page: number; page_size: number; total_pages: number; as_of: string; date_from: string; date_to: string; mode: Mode };
  targets: Target[]; simulation_targets?: Target[]; targets_as_of?: string;
  latest_run: { status: string; started_at: string; finished_at: string | null; counts: Record<string, number> } | null;
};
const CATEGORIES: Record<string, string> = { forecast: '날씨 예보', weather_warning: '기상 특보', disaster_msg: '재난문자', traffic_control: '교통 통제', air_quality: '대기질', earthquake: '지진' };
const STATUSES: Record<string, string> = { ok: '확인', received: '수신', failed: '조회 실패', not_connected: '미연결', not_applicable: '해당 없음' };
const KINDS: Record<string, string> = { disaster_message: '수신 문자', api_receipt: 'API 수신 기록', api_check: 'API 점검 기록', mock_input: 'mock API 입력' };
const time = (value: string | null | undefined) => value ? new Date(value).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul' }) : '확인 기록 없음';

function recentWeek(): Period {
  const pieces = new Intl.DateTimeFormat('en', { timeZone: 'Asia/Seoul', year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(new Date());
  const part = (type: string) => pieces.find(value => value.type === type)!.value;
  const to = `${part('year')}-${part('month')}-${part('day')}`;
  const first = new Date(`${to}T00:00:00Z`);
  first.setUTCDate(first.getUTCDate() - 6);
  return { from: first.toISOString().slice(0, 10), to };
}

function pageNumbers(current: number, total: number) {
  const pages = new Set([1, total]);
  for (let page = Math.max(1, current - 2); page <= Math.min(total, current + 2); page++) pages.add(page);
  return [...pages].sort((a, b) => a - b);
}

export function DisasterReceiptPanel() {
  const [period, setPeriod] = useState(recentWeek);
  const [draft, setDraft] = useState(period);
  const [mode, setMode] = useState<Mode>('actual');
  const [page, setPage] = useState(1);
  const [asOf, setAsOf] = useState<string>();
  const [error, setError] = useState('');
  const query = useQuery({
    queryKey: ['disaster-receipts', period, mode, page, asOf],
    queryFn: () => {
      const params = new URLSearchParams({ mode, date_from: period.from, date_to: period.to, page: String(page) });
      if (asOf) params.set('as_of', asOf);
      return operationSimulations<Receipts>('receipts', params);
    },
    refetchInterval: page === 1 ? 10000 : false,
  });
  const history = query.data?.history;
  const resetPage = () => { setPage(1); setAsOf(undefined); };
  const changePage = (next: number) => { setAsOf(history?.as_of); setPage(next); };
  const actualTargets = query.data?.targets || [];
  const simulationTargets = query.data?.simulation_targets || [];

  return <section className={styles.receipts} aria-labelledby="receipt-heading">
    <h2 id="receipt-heading">재난문자·API 수신 및 점검 기록</h2>
    <p>실제 들어온 재난문자와 6종 API 점검, mock API 입력을 함께 조회합니다. 수신·점검 시각을 한국 시간으로 조회하며, 새로 읽기는 저장된 기록만 읽습니다.</p>
    <form className={styles.receiptFilters} noValidate onSubmit={event => {
      event.preventDefault();
      if (!draft.from || !draft.to || draft.from > draft.to) { setError('시작일과 종료일을 확인해 주세요. 시작일은 종료일보다 늦을 수 없습니다.'); return; }
      setError(''); setPeriod(draft); resetPage();
      if (draft.from === period.from && draft.to === period.to && page === 1 && !asOf) void query.refetch();
    }}>
      <label>입력 구분<select value={mode} onChange={event => { setMode(event.target.value as Mode); resetPage(); }}>
        <option value="simulation">모의</option><option value="actual">실제</option><option value="all">둘 다</option>
      </select></label>
      <label>수신·점검 시작일<input type="date" value={draft.from} max={draft.to || undefined} onChange={event => { setDraft({ ...draft, from: event.target.value }); setError(''); }} /></label>
      <label>수신·점검 종료일<input type="date" value={draft.to} min={draft.from || undefined} onChange={event => { setDraft({ ...draft, to: event.target.value }); setError(''); }} /></label>
      <div className={styles.receiptActions}>
        <button type="submit">기간 조회</button>
        <button type="button" onClick={() => { const week = recentWeek(); setDraft(week); setPeriod(week); setError(''); resetPage(); if (page === 1 && !asOf) void query.refetch(); }}>최근 7일 보기</button>
        <button type="button" onClick={() => { resetPage(); if (page === 1 && !asOf) void query.refetch(); }}>수신 기록 새로 읽기</button>
      </div>
    </form>
    {error && <p role="alert">{error}</p>}
    <p role="status">조회 기간 {period.from} ~ {period.to} · {mode === 'all' ? '모의·실제 모두' : mode === 'actual' ? '실제 기록' : '모의 기록'} · 한 페이지 50건</p>
    {query.isPending ? <p role="status">수신 기록을 읽는 중…</p> : query.isError ? <div role="alert"><p>{query.error.message}</p><button onClick={() => void query.refetch()}>수신 기록 다시 읽기</button></div> : !history ?
      <p role="alert">기간별 수신 기록 조회가 준비되지 않았습니다. 관리자 앱과 운영 API의 적용 판을 확인해 주세요.</p> : <>
      <p role="status">총 {history.total}건 · {history.page}/{history.total_pages}페이지 · 조회 기준 {time(history.as_of)}</p>
      <nav className={styles.pagination} aria-label="수신 기록 페이지">
        <button disabled={history.page <= 1} onClick={() => changePage(history.page - 1)}>이전 페이지</button>
        {pageNumbers(history.page, history.total_pages).map((number, index, numbers) => <span key={number}>
          {index > 0 && number - numbers[index - 1] > 1 && <span aria-hidden="true"> … </span>}
          <button aria-label={`수신 기록 ${number}페이지`} aria-current={number === history.page ? 'page' : undefined} onClick={() => changePage(number)}>{number}</button>
        </span>)}
        <button disabled={history.page >= history.total_pages} onClick={() => changePage(history.page + 1)}>다음 페이지</button>
      </nav>
      {history.records.length ? <ol className={styles.recordList} start={(history.page - 1) * history.page_size + 1}>{history.records.map(record => <li key={record.id}>
        <div className={styles.recordHeading}><strong>{CATEGORIES[record.category] || record.category} · {KINDS[record.record_type] || record.record_type}</strong><span className={styles.recordMode}>{record.mode === 'simulation' ? '모의' : '실제'}</span></div>
        <p>수신·점검 {time(record.received_at)} · {STATUSES[record.status] || record.status || '상태 미기록'}<br />출처 {record.source || '출처 미기록'}</p>
        {record.target_title && <p>점검 일정 {record.target_title}{record.trip_id && ` · 여행 ${record.trip_id.slice(0, 8)}`}</p>}
        {record.text && <p className={styles.receiptText}>{record.text}</p>}
        {record.published_at && <p>발표 {time(record.published_at)} · {record.regions.join(' · ')}</p>}
        <details><summary>API 데이터·점검 결과 펼치기</summary><pre className={styles.payload}>{JSON.stringify(record.payload, null, 2)}</pre></details>
      </li>)}</ol> : <p role="status">선택한 구분과 기간에 저장된 기록이 없습니다. 기간을 넓히거나 입력 구분을 바꿔 주세요. 이 표시가 현재 재난이 없다는 뜻은 아닙니다.</p>}
    </>}
    {query.data && <details className={styles.currentMonitoring}>
      <summary>현재 수신 상태·검사 대상 펼치기</summary>
      <p>아래는 현재 상태입니다. 위에서 선택한 기간의 과거 기록과 구별해 표시합니다. 확인 {time(query.data.targets_as_of)}</p>
      {mode !== 'simulation' && <>
        {query.data.statuses.map(status => <p key={status.region}>{status.region} · {status.status === 'received' ? '재난문자 API 응답 확인' : '재난문자 수신 확인 실패'} · 응답 {status.count}건<br />원본 수신 {time(status.fetched_at)} · 마지막 검사 {time(status.observed_at)} · {status.from_cache ? '저장된 API 응답 재사용' : '외부 API 응답'}{status.error_code && ` · 오류 ${status.error_code}`}</p>)}
        <h3>현재 실제 검사 대상 {actualTargets.length}건</h3>
        <p>진행 중인 방문과 앞으로 90분 안에 시작하는 방문입니다. 모의 시험으로 포함된 일정은 아래 모의 대상으로 구분합니다. 재난 정지 중인 여행은 안전 확인 경로에서 처리합니다.</p>
        <TargetList targets={actualTargets} />
      </>}
      {mode !== 'actual' && <>
        <h3>현재 모의 시험 대상 {simulationTargets.length}건</h3>
        <p>관리자가 선택한 시험 일정입니다. 실제 방문 시각이 90분보다 뒤여도 시험이 켜진 동안 포함됩니다.</p>
        <TargetList targets={simulationTargets} />
      </>}
      <p>{query.data.latest_run ? `최근 감시 회차 ${query.data.latest_run.status} · 시작 ${time(query.data.latest_run.started_at)} · 종료 ${time(query.data.latest_run.finished_at)}` : '기록된 감시 회차가 없습니다.'}</p>
    </details>}
  </section>;
}

function TargetList({ targets }: { targets: Target[] }) {
  return targets.length ? <ul>{targets.map(item => <li key={item.trip_id + item.item_id}>{item.title} · 여행 {item.trip_id.slice(0, 8)} · {time(item.starts_at)} · {item.reason === 'simulation' ? '모의 시험' : item.reason === 'ongoing' ? '현재 방문 중' : '90분 안에 시작'}</li>)}</ul> : <p>현재 해당 대상이 없습니다.</p>;
}
