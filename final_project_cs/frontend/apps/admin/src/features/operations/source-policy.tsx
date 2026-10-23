'use client';
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { operationSourcePolicy, operationDiagnostics, saveSourcePolicy, saveDiagnosticResolution } from '../../lib/gateway';

type Policy = { allow_paid: boolean; daily_paid_cap: number; trip_paid_cap: number; check_interval_seconds: number };
type Response = { revision: number; policy: Policy; bounds: Record<string, [number, number]> };
const labels: Record<string, string> = { daily_paid_cap: '전체 하루 유료 재조회 상한', trip_paid_cap: '여행별 하루 유료 재조회 상한', check_interval_seconds: '같은 장소 유료 재조회 최소 간격(초)' };

export function SourcePolicySettings() {
  const query = useQuery({ queryKey: ['source-policy'], queryFn: () => operationSourcePolicy<Response>() });
  const [draft, setDraft] = useState<Partial<Policy>>({});
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const current = query.data && { ...query.data.policy, ...draft };
  return <section className="panel"><h1>자료 조회 정책</h1><p>무료 자료를 먼저 확인합니다. 확인 실패는 검증 불가로 표시합니다. 유료 허용을 켜도 기존 제공처 예산과 구글 새벽 확인 창은 유지됩니다.</p>
    {query.isPending ? <p role="status">조회 정책 읽는 중…</p> : query.isError ? <><p role="alert" className="error">{query.error.message}</p><button onClick={() => void query.refetch()}>조회 정책 다시 읽기</button></> : current && <form onSubmit={async event => {
      event.preventDefault(); if (busy) return; setError(''); setNotice('');
      if (!reason.trim()) { setError('변경 사유를 입력해 주세요.'); return; }
      setBusy(true); try { await saveSourcePolicy({ expected_revision: query.data!.revision, policy: current, reason }); setDraft({}); setReason(''); setNotice('조회 정책을 저장했습니다. 다음 조회부터 적용됩니다.'); await query.refetch(); } catch (cause) { setError(cause instanceof Error ? cause.message : '저장하지 못했습니다. 다시 읽어 주세요.'); } finally { setBusy(false); }
    }}><p>현재 정책 판 {query.data?.revision}</p><label style={{ display: 'block', margin: '1rem 0' }}>유료 재조회 허용<select value={String(current.allow_paid)} onChange={e => { setDraft(d => ({ ...d, allow_paid: e.target.value === 'true' })); setError(''); }}><option value="false">허용 안 함</option><option value="true">기존 예산 안에서 허용</option></select></label>
      {Object.entries(labels).map(([name, label]) => <label key={name} style={{ display: 'block', margin: '1rem 0' }}>{label}<input type="number" required min={query.data?.bounds[name][0]} max={query.data?.bounds[name][1]} value={String(current[name as keyof Policy])} onChange={e => { setDraft(d => ({ ...d, [name]: e.target.valueAsNumber })); setError(''); }} /></label>)}
      <label style={{ display: 'block', margin: '1rem 0' }}>변경 사유<input required maxLength={500} value={reason} onFocus={() => setError('')} onChange={e => { setReason(e.target.value); setError(''); }} /></label><button type="submit" className="primary" aria-disabled={busy}>{busy ? '저장 중…' : '조회 정책 저장'}</button><button type="button" onClick={() => { setDraft({}); setError(''); setNotice(''); void query.refetch(); }}>현재 정책 다시 읽기</button>{error && <p role="alert" className="error">{error}</p>}{notice && <p role="status">{notice}</p>}
    </form>}
  </section>;
}

type Defect = { fingerprint: string; kind: string; code: string; occurrences: number; affected_customers: number; deployment: string; policy_version: string; resolved_version: string | null; conditions: string[]; last_at: string };
type Page = { items: Defect[]; next: { at: string; fingerprint: string } | null };
const kinds: Record<string, string> = { suggestion: '고객 건의', processing_error: '처리 오류', place_unmatched: '장소 미확인' };

export function DiagnosticsPanel() {
  const [cursor, setCursor] = useState('');
  const query = useQuery({ queryKey: ['diagnostics', cursor], queryFn: () => operationDiagnostics<Page>(cursor) });
  return <section className="panel"><h1>결함 사후 분석</h1><p>발생 수는 누적 건수이며 영향 고객 수는 보존 기간 안의 중복 없는 고객 수입니다. 이 화면은 고객 일정 수정이나 상담원 배정을 하지 않습니다.</p><button onClick={() => void query.refetch()}>진단 기록 다시 읽기</button>
    {query.isPending ? <p role="status">진단 기록 읽는 중…</p> : query.isError ? <p role="alert" className="error">{query.error.message}</p> : <><ul>{query.data?.items.map(item => <li key={item.fingerprint}><details><summary>{kinds[item.kind] || item.kind} · {item.code} · 발생 {item.occurrences}건</summary><p>영향 고객 {item.affected_customers}명 · 최근 {new Date(item.last_at).toLocaleString('ko-KR')}</p><p>배포 판 {item.deployment} · 정책 판 {item.policy_version} · 해결 판 {item.resolved_version || '미기록'}</p><p>재현 조건 {item.conditions.join(', ') || '미기록'}</p><AffectedCustomers fingerprint={item.fingerprint} /><OccurrenceRecords fingerprint={item.fingerprint} /><ResolutionForm fingerprint={item.fingerprint} onSaved={() => { void query.refetch(); }} /></details></li>)}</ul>{!query.data?.items.length && <p>조회 범위에 진단 기록이 없습니다. 자료 수집과 실제 운영 상태는 별도로 확인해 주세요.</p>}{cursor && <button onClick={() => setCursor('')}>첫 페이지 보기</button>}{query.data?.next && <button onClick={() => { const n = query.data!.next!; setCursor(`?before_at=${encodeURIComponent(n.at)}&before_key=${n.fingerprint}`); }}>다음 진단 보기</button>}</>}
  </section>;
}

function AffectedCustomers({ fingerprint }: { fingerprint: string }) {
  const [enabled, setEnabled] = useState(false);
  const [after, setAfter] = useState('');
  const query = useQuery({ queryKey: ['diagnostic-customers', fingerprint, after], queryFn: () => operationDiagnostics<{ customers: string[]; next: string | null }>(`/${fingerprint}/customers${after ? `?after=${after}` : ''}`), enabled });
  return <div><button onClick={() => { setEnabled(true); if (enabled) void query.refetch(); }}>영향 고객 식별자 조회</button>{enabled && (query.isPending ? <p role="status">고객 연결 읽는 중…</p> : query.isError ? <p role="alert">{query.error.message}</p> : <><ul>{query.data?.customers.map(id => <li key={id} style={{ overflowWrap: 'anywhere' }}>{id}</li>)}</ul>{query.data?.next && <button onClick={() => setAfter(query.data!.next!)}>다음 고객 연결 보기</button>}</>)}</div>;
}

function OccurrenceRecords({ fingerprint }: { fingerprint: string }) {
  const [enabled, setEnabled] = useState(false);
  const [after, setAfter] = useState('');
  type Occurrence = { event_id: string; case_id: string | null; request_id: string | null; occurred_at: string };
  const query = useQuery({ queryKey: ['diagnostic-events', fingerprint, after], queryFn: () => operationDiagnostics<{ events: Occurrence[]; next: string | null }>(`/${fingerprint}/events${after ? `?after=${after}` : ''}`), enabled });
  return <div><button onClick={() => { setEnabled(true); if (enabled) void query.refetch(); }}>발생·요청 식별자 조회</button>{enabled && (query.isPending ? <p role="status">발생 기록 읽는 중…</p> : query.isError ? <p role="alert">{query.error.message}</p> : <><ul>{query.data?.events.map(item => <li key={item.event_id} style={{ overflowWrap: 'anywhere' }}>발생 {item.event_id} · {new Date(item.occurred_at).toLocaleString('ko-KR')}<br />사건 {item.case_id || '미연결'} · 요청 {item.request_id || '미연결'}</li>)}</ul>{!query.data?.events.length && <p>보존 기간 안의 발생 연결이 없습니다.</p>}{query.data?.next && <button onClick={() => setAfter(query.data!.next!)}>다음 발생 기록 보기</button>}</>)}</div>;
}

function ResolutionForm({ fingerprint, onSaved }: { fingerprint: string; onSaved: () => void }) {
  const [version, setVersion] = useState('');
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  return <form onSubmit={async event => {
    event.preventDefault(); if (busy) return; setError(''); setNotice('');
    if (!reason.trim()) { setError('해결 기록의 변경 사유를 입력해 주세요.'); return; }
    setBusy(true); try { await saveDiagnosticResolution(fingerprint, { version, reason }); setReason(''); setNotice('해결 판을 기록했습니다.'); onSaved(); } catch (cause) { setError(cause instanceof Error ? cause.message : '해결 판을 기록하지 못했습니다. 다시 시도해 주세요.'); } finally { setBusy(false); }
  }}><p>검증한 수정 판본을 기록합니다. 고객 일정은 바뀌지 않습니다.</p><label style={{ display: 'block', margin: '1rem 0' }}>해결 판<input required pattern="[A-Za-z0-9_.-]+" maxLength={80} value={version} onChange={e => { setVersion(e.target.value); setError(''); }} /></label><label style={{ display: 'block', margin: '1rem 0' }}>해결 기록의 변경 사유<input required maxLength={500} value={reason} onChange={e => { setReason(e.target.value); setError(''); }} /></label><button type="submit" aria-disabled={busy}>{busy ? '해결 판 기록 중…' : '해결 판 기록'}</button>{error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}</form>;
}
