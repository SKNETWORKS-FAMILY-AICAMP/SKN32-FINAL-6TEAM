'use client';

import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { operationSimulations, saveOperationSimulation } from '../../lib/gateway';
import { SimulationTripPicker, type Audience, type Categories } from './simulation-trip-picker';
import styles from './simulation.module.css';

type Simulation = {
  trip_id: string; title: string; version: number;
  can_simulate?: boolean; paused?: boolean; unavailable_reason?: string;
  configuration: { revision: number; active: boolean; categories: string[]; item_id?: string; expires_at?: string; run_id?: string };
  items: { item_id: string; title: string; starts_at: string; weather_sensitive: boolean | null; ongoing: boolean }[];
  notices: { key: string; text: string; at: string }[];
  reports?: Record<string, { verdict: string; checked_at: string; checks: { category: string; status: string; mode?: string }[] }>;
};
const EFFECTS: Record<string, string> = {
  forecast: '강수·강풍 예보 → 주의 안내와 일정 변경 버튼',
  weather_warning: '호우주의보 → 기존 날씨 변경 정책',
  disaster_msg: '주변 화재 재난문자 → 기존 안전 정책',
  traffic_control: '장소 진입 도로 전면 통제 → 기존 변경 정책',
  air_quality: '미세먼지 경보 → 기존 실내 대체 정책',
  earthquake: '규모 5 지진 → 기존 안전정지 정책',
};

export function DisasterSimulation() {
  const [selection, setSelection] = useState<{ id: string; audience: Audience; categories: Categories } | null>(null);
  return <section className={`panel ${styles.page}`}><h1>재난 6종 시뮬레이션</h1>
    <p>감시 대상 여행 또는 게스트 여행과 대상 일정을 고르고 재난 입력을 켜세요. 다음 감시 회차가 기존 알림·일정 변경·안전정지 규칙으로 처리합니다.</p>
    {(['monitored', 'guest'] as const).map(audience => <SimulationTripPicker key={audience} audience={audience}
      selectedId={selection?.audience === audience ? selection.id : ''}
      onSelect={(id, categories) => setSelection(id ? { id, audience, categories } : null)}
      onClear={() => setSelection(current => current?.audience === audience ? null : current)} />)}
    {selection?.audience === 'guest' && <p>이 게스트 여행은 시험 입력을 켠 동안에만 감시합니다. 중지·시간 만료·일정 판 변경으로 시험이 끝나면 일반 게스트처럼 감시에서 제외됩니다.</p>}
    {selection && <SimulationForm key={selection.id} tripId={selection.id} categories={selection.categories} />}
  </section>;
}

function SimulationForm({ tripId, categories }: { tripId: string; categories: Categories }) {
  const query = useQuery({ queryKey: ['watch-simulation', tripId], queryFn: () => operationSimulations<Simulation>(tripId), refetchInterval: 5000 });
  if (query.isPending) return <p role="status">현재 일정과 설정을 읽는 중…</p>;
  if (query.isError) return <div role="alert"><p className="error">{query.error.message}</p><button onClick={() => void query.refetch()}>현재 일정 다시 읽기</button></div>;
  return <Editor key={`${query.data.version}-${query.data.configuration.revision}`} data={query.data} categories={categories} reload={async () => { await query.refetch(); }} />;
}

function Editor({ data, categories, reload }: { data: Simulation; categories: Categories; reload: () => Promise<void> }) {
  const [selected, setSelected] = useState(data.configuration.active ? data.configuration.categories : []);
  const [itemId, setItemId] = useState(data.configuration.item_id && data.items.some(i => i.item_id === data.configuration.item_id) ? data.configuration.item_id : data.items.find(i => i.ongoing)?.item_id || data.items[0]?.item_id || '');
  const [duration, setDuration] = useState(15);
  const [reason, setReason] = useState('');
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState(false);
  const reasonInput = useRef<HTMLInputElement>(null);
  const itemInput = useRef<HTMLSelectElement>(null);
  const submitting = useRef(false);
  const save = async (stop: boolean) => {
    if (submitting.current) return;
    setError(''); setFeedback('');
    if (!reason.trim()) { setError('적용·중지 사유를 입력해 주세요.'); reasonInput.current?.focus(); return; }
    if (!stop && !itemId) { setError('대상 일정을 선택해 주세요.'); itemInput.current?.focus(); return; }
    if (!stop && !selected.length) { setError('시험할 재난을 하나 이상 켜 주세요.'); return; }
    submitting.current = true; setBusy(true);
    try {
      await saveOperationSimulation(data.trip_id, { expected_revision: data.configuration.revision, expected_version: data.version,
        item_id: stop ? null : itemId, categories: stop ? [] : selected, duration_minutes: duration, reason });
      setFeedback(stop ? '시험 입력을 중지했습니다. 이미 바뀐 일정·안전정지는 고객 앱에서 되돌리거나 다시 시작해 주세요.' : `${selected.length}종을 적용했습니다. 다음 감시 회차의 처리 결과를 아래에서 확인하세요.`);
      await reload();
    } catch (cause) { setError(cause instanceof Error ? cause.message : '적용하지 못했습니다. 현재 값을 다시 읽어 주세요.'); }
    finally { submitting.current = false; setBusy(false); }
  };
  return <div style={{ marginTop: '1.5rem' }}>
    <p role="status">{data.configuration.active ? `시뮬레이션 입력 ${data.configuration.categories.length}종 활성 · ${new Date(data.configuration.expires_at!).toLocaleTimeString('ko-KR')}까지` : '시뮬레이션 입력 꺼짐'} · 일정 판 {data.version} · 설정 판 {data.configuration.revision}</p>
    <p>선택한 일정에만 시험 입력을 넣습니다. 실내 일정의 예보·특보·대기질은 해당 없음으로 판정하며, 여러 상황에서는 안전정지가 먼저 처리됩니다. 선택하지 않은 소스와 대체 장소는 실제로 점검합니다.</p>
    {data.can_simulate === false && <p role="status">{data.unavailable_reason}</p>}
    {(data.can_simulate !== false || data.configuration.active) && <form noValidate onSubmit={e => { e.preventDefault(); if (data.can_simulate !== false) void save(false); }} aria-busy={busy}>
      <label>대상 일정<select ref={itemInput} value={itemId} onChange={e => { setItemId(e.target.value); setError(''); }}><option value="">일정 선택</option>{data.items.map(item => <option key={item.item_id} value={item.item_id}>{item.ongoing ? '진행 중' : '다음 일정'} · {item.title} · {new Date(item.starts_at).toLocaleString('ko-KR')}</option>)}</select></label>
      <fieldset className={styles.switches}><legend>재난 활성화 스위치 · 선택 {selected.length}/6</legend>
        {categories.map(category => <label key={category.key}>
          <input type="checkbox" role="switch" checked={selected.includes(category.key)} onChange={e => { setSelected(values => e.target.checked ? [...values, category.key] : values.filter(key => key !== category.key)); setError(''); }} />
          <span>{category.label}<small>{EFFECTS[category.key]}</small></span>
        </label>)}
      </fieldset>
      <label>자동 종료 시간<select value={duration} onChange={e => setDuration(Number(e.target.value))}>{[5, 15, 30, 60].map(minutes => <option key={minutes} value={minutes}>{minutes}분 뒤</option>)}</select></label>
      <label>적용·중지 사유<input ref={reasonInput} value={reason} maxLength={500} onChange={e => { setReason(e.target.value); setError(''); }} onBlur={() => { if (reason && !reason.trim()) setError('적용·중지 사유를 입력해 주세요.'); }} aria-invalid={!!error && !reason.trim()} /></label>
      <p>시험 알림에는 시뮬레이션 표시가 붙고 고객 앱에서 확인합니다. 일정 판이 바뀌거나 시간이 지나면 입력이 종료됩니다. 중지는 이미 적용한 변경·안전정지를 되돌리지 않습니다.</p>
      <div className="toolbar">{data.can_simulate !== false && <button className="primary" type="submit">{busy ? '저장 중…' : `선택한 ${selected.length}종 적용`}</button>}<button type="button" onClick={() => void save(true)}>시뮬레이션 중지</button><button type="button" onClick={() => void reload()}>현재 값 다시 읽기</button></div>
      {error && <p role="alert" className="error">{error}</p>}{feedback && <p role="status" className="success">{feedback}</p>}
    </form>}
    <h2>실제 감시 점검 결과</h2>{Object.entries(data.reports || {}).length ? Object.entries(data.reports!).map(([stage, report]) => <div key={stage}>
      <p>{stage === 'safety' ? '안전정지 점검' : '6종 통합 점검'} · {({ clear: '주요 사건 없음', disrupted: '사건 감지', fatal: '조회 실패' } as Record<string,string>)[report.verdict] || report.verdict} · {new Date(report.checked_at).toLocaleString('ko-KR')}</p>
      <div style={{ overflowX: 'auto' }}><table><thead><tr><th>종류</th><th>입력</th><th>확인 결과</th></tr></thead><tbody>{report.checks.map(check => <tr key={check.category}><td>{categories.find(c => c.key === check.category)?.label || check.category}</td><td>{check.mode === 'simulation' ? '시뮬레이션' : '실제 소스'}</td><td>{({ok:'확인',failed:'조회 실패',not_applicable:'해당 없음',not_connected:'미연결'} as Record<string,string>)[check.status] || check.status}</td></tr>)}</tbody></table></div>
    </div>) : <p>아직 이번 실행의 감시 점검 결과가 없습니다. 입력 적용과 처리 완료는 별개입니다.</p>}
    <h2>이번 시험의 앱 알림</h2>{data.notices.length ? <ol>{data.notices.map(notice => <li key={notice.key}><p>{notice.text}</p><small>{new Date(notice.at).toLocaleString('ko-KR')}</small></li>)}</ol> : <p>아직 이번 실행에 기록된 앱 알림이 없습니다. 다음 감시 회차 뒤 확인해 주세요. 실제 소스 조회 실패나 대상 항목에 해당하지 않는 입력은 처리 결과에 영향을 줍니다.</p>}
  </div>;
}
