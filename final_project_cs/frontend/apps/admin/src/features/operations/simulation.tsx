'use client';

import { useId, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { operationSimulations, saveOperationSimulation, receiveOperationSimulation } from '../../lib/gateway';
import { SimulationTripPicker, type Audience, type Categories } from './simulation-trip-picker';
import styles from './simulation.module.css';
import { DisasterReceiptPanel } from './receipt-panel';

type Simulation = {
  trip_id: string; title: string; version: number;
  can_simulate?: boolean; paused?: boolean; unavailable_reason?: string;
  configuration: { revision: number; disaster_scenario?: string; external_delivery?: boolean; started_at?: string; active: boolean; categories: string[]; item_id?: string; expires_at?: string; run_id?: string };
  items: { item_id: string; title: string; starts_at: string; weather_sensitive: boolean | null; ongoing: boolean }[];
  notices: { key: string; text: string; at: string; delivery?: string; attempts?: number; error?: string }[];
  receipt?: { mode: string; received_at: string; sources: Record<string, unknown> } | null;
  delivery?: { channel: string | null; discord_connected: boolean; customer_created_at: string; customer_external_enabled: boolean };
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
  const views = [{ key: 'simulation', label: '재난 시뮬레이션' }, { key: 'receipts', label: '수신·모니터링 기록' }] as const;
  const [view, setView] = useState<'simulation' | 'receipts'>('simulation');
  const tabId = useId();
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const [selection, setSelection] = useState<{ id: string; audience: Audience; categories: Categories } | null>(null);
  return <section className={`panel ${styles.page}`}><h1>재난 6종 시뮬레이션</h1>
    <div className={styles.tabs} role="tablist" aria-label="재난 시험·실제 수신 보기">
      {views.map((entry, index) => <button key={entry.key} ref={element => { tabs.current[index] = element; }}
        id={`${tabId}-tab-${entry.key}`} type="button" role="tab" aria-selected={view === entry.key}
        aria-controls={`${tabId}-panel-${entry.key}`} tabIndex={view === entry.key ? 0 : -1}
        onClick={() => setView(entry.key)} onKeyDown={event => {
          const next = event.key === 'ArrowRight' ? (index + 1) % views.length : event.key === 'ArrowLeft' ? (index + views.length - 1) % views.length : event.key === 'Home' ? 0 : event.key === 'End' ? views.length - 1 : null;
          if (next !== null) { event.preventDefault(); setView(views[next].key); tabs.current[next]?.focus(); }
        }}>{entry.label}</button>)}
    </div>
    <div id={`${tabId}-panel-simulation`} role="tabpanel" aria-labelledby={`${tabId}-tab-simulation`} hidden={view !== 'simulation'}>
    <p>감시 대상 여행 또는 게스트 여행과 대상 일정을 고르고 재난 입력을 켜세요. 다음 감시 회차가 기존 알림·일정 변경·안전정지 규칙으로 처리합니다.</p>
    {(['monitored', 'guest'] as const).map(audience => <SimulationTripPicker key={audience} audience={audience}
      selectedId={selection?.audience === audience ? selection.id : ''}
      onSelect={(id, categories) => setSelection(id ? { id, audience, categories } : null)}
      onClear={() => setSelection(current => current?.audience === audience ? null : current)} />)}
    {selection?.audience === 'guest' && <p>이 게스트 여행은 시험 입력을 켠 동안에만 감시합니다. 중지·시간 만료·일정 판 변경으로 시험이 끝나면 일반 게스트처럼 감시에서 제외됩니다.</p>}
    {selection && <SimulationForm key={selection.id} tripId={selection.id} categories={selection.categories} />}
    </div>
    <div id={`${tabId}-panel-receipts`} role="tabpanel" aria-labelledby={`${tabId}-tab-receipts`} hidden={view !== 'receipts'}>
      <DisasterReceiptPanel />
    </div>
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
  const [duration, setDuration] = useState(() => {
    const { started_at, expires_at } = data.configuration;
    const saved = started_at && expires_at ? Math.round((Date.parse(expires_at) - Date.parse(started_at)) / 60000) : 15;
    return [5, 15, 30, 60].includes(saved) ? saved : 15;
  });
  const [disasterScenario, setDisasterScenario] = useState(data.configuration.disaster_scenario || 'fire');
  const [reason, setReason] = useState('');
  const [externalDelivery, setExternalDelivery] = useState(data.configuration.external_delivery ?? false);
  const [error, setError] = useState('');
  const [feedback, setFeedback] = useState('');
  const [busy, setBusy] = useState(false);
  const reasonInput = useRef<HTMLInputElement>(null);
  const itemInput = useRef<HTMLSelectElement>(null);
  const submitting = useRef(false);
  const save = async (stop: boolean) => {
    if (submitting.current) return;
    setError(''); setFeedback('');
    if (!reason.trim()) { reasonInput.current?.focus(); setError('적용·중지 사유를 입력해 주세요.'); return; }
    if (!stop && !itemId) { setError('대상 일정을 선택해 주세요.'); itemInput.current?.focus(); return; }
    if (!stop && externalDelivery && !data.delivery?.discord_connected) { setError('이 여행 계정에 디스코드를 먼저 연결해 주세요.'); return; }
    if (!stop && !selected.length) { setError('시험할 재난을 하나 이상 켜 주세요.'); return; }
    submitting.current = true; setBusy(true);
    try {
      const send = stop ? saveOperationSimulation : receiveOperationSimulation;
      await send(data.trip_id, { expected_revision: data.configuration.revision, expected_version: data.version,
        item_id: stop ? null : itemId, categories: stop ? [] : selected, duration_minutes: duration, external_delivery: stop ? false : externalDelivery, disaster_scenario: disasterScenario, reason });
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
      {selected.includes('disaster_msg') && <label>재난문자 시험 상황<select value={disasterScenario} onChange={e => setDisasterScenario(e.target.value)}><option value="fire">주변 화재 · 안전정지 확인</option><option value="closure">대상 장소 출입 통제 · 대안 선택 확인</option></select></label>}
      <fieldset className={styles.delivery}><legend>선택한 여행의 고객 디스코드 발송</legend>
        <p>계정 생성일 {data.delivery?.customer_created_at ? new Date(data.delivery.customer_created_at).toLocaleString('ko-KR') : '확인 전'} · {data.delivery?.discord_connected ? '디스코드 연결됨' : '디스코드 미연결'} · 전체 외부 알림 {data.delivery?.customer_external_enabled ? '켜짐' : '꺼짐'}</p>
        <label><input type="checkbox" checked={externalDelivery} onChange={e => { setExternalDelivery(e.target.checked); setError(''); }} />이 여행의 시뮬레이션 알림을 고객 디스코드로 보내기</label>
        <p>이 실행에만 적용됩니다. 메시지에 [시뮬레이션]을 붙이며 중지하거나 자동 종료 시간이 지나면 외부 발송을 막습니다.</p>
      </fieldset>
      <label>자동 종료 시간<select value={duration} onChange={e => setDuration(Number(e.target.value))}>{[5, 15, 30, 60].map(minutes => <option key={minutes} value={minutes}>{minutes}분 뒤</option>)}</select></label>
      <label>적용·중지 사유<input ref={reasonInput} value={reason} maxLength={500} onChange={e => { setReason(e.target.value); setError(''); }} onFocus={() => setError('')} onBlur={() => { if (!reason.trim()) setError('적용·중지 사유를 입력해 주세요.'); }} aria-invalid={!!error && !reason.trim()} /></label>
      <p>시험 알림에는 시뮬레이션 표시가 붙고 고객 앱에서 확인합니다. 일정 판이 바뀌거나 시간이 지나면 입력이 종료됩니다. 중지는 이미 적용한 변경·안전정지를 되돌리지 않습니다.</p>
      <div className="toolbar">{data.can_simulate !== false && <button className="primary" type="submit">{busy ? '저장 중…' : `선택한 ${selected.length}종 적용`}</button>}<button type="button" onClick={() => void save(true)}>시뮬레이션 중지</button><button type="button" onClick={() => void reload()}>현재 값 다시 읽기</button></div>
      {error && <p role="alert" className="error">{error}</p>}{feedback && <p role="status" className="success">{feedback}</p>}
    </form>}
    <h2>mock API 수신 내용</h2>
    <p>mock API에 실제 저장한 이번 실행의 수신 내용입니다. 재난문자는 공식 API와 같은 파서·판정을 거칩니다. 아래 감시 결과에서 실제로 적용됐는지 확인할 수 있습니다.</p>
    {data.receipt ? <><p>저장 시각 {new Date(data.receipt.received_at).toLocaleString('ko-KR')} · 시뮬레이션 입력</p><pre className={styles.payload}>{JSON.stringify(data.receipt.sources, null, 2)}</pre></> : <p>아직 이번 실행의 mock API 수신 기록이 없습니다.</p>}
    <h2>실제 감시 점검 결과</h2>{Object.entries(data.reports || {}).length ? Object.entries(data.reports!).map(([stage, report]) => <div key={stage}>
      <p>{stage === 'safety' ? '안전정지 점검' : '6종 통합 점검'} · {({ clear: '주요 사건 없음', disrupted: '사건 감지', fatal: '조회 실패' } as Record<string,string>)[report.verdict] || report.verdict} · {new Date(report.checked_at).toLocaleString('ko-KR')}</p>
      <div style={{ overflowX: 'auto' }}><table><thead><tr><th>종류</th><th>입력</th><th>확인 결과</th></tr></thead><tbody>{report.checks.map(check => <tr key={check.category}><td>{categories.find(c => c.key === check.category)?.label || check.category}</td><td>{check.mode === 'simulation' ? '시뮬레이션' : '실제 소스'}</td><td>{({ok:'확인',failed:'조회 실패',not_applicable:'해당 없음',not_connected:'미연결'} as Record<string,string>)[check.status] || check.status}</td></tr>)}</tbody></table></div>
    </div>) : <p>아직 이번 실행의 감시 점검 결과가 없습니다. 입력 적용과 처리 완료는 별개입니다.</p>}
    <h2>이번 시험의 고객 알림·외부 배달 결과</h2>{data.notices.length ? <ol>{data.notices.map(notice => <li key={notice.key}><p>{notice.text}</p><small>{new Date(notice.at).toLocaleString('ko-KR')} · 디스코드 배달 {({delivered:'전송 성공',pending:'대기',processing:'발송 중',skipped:'발송 안 함',unknown:'결과 확인 필요',failed:'실패'} as Record<string,string>)[notice.delivery || ''] || notice.delivery || '확인 전'} · 시도 {notice.attempts ?? 0}회</small>{notice.error && <p>{notice.error}</p>}</li>)}</ol> : <p>아직 이번 실행에 기록된 앱 알림이 없습니다. 다음 감시 회차 뒤 확인해 주세요. 실제 소스 조회 실패나 대상 항목에 해당하지 않는 입력은 처리 결과에 영향을 줍니다.</p>}
  </div>;
}
