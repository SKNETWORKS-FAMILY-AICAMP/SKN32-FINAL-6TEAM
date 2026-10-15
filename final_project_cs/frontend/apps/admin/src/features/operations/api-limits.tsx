'use client';

import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { operationApiLimits } from '../../lib/gateway';
import { formatNumber, type ScreenProps } from '../../lib/model';
import styles from './api-limits.module.css';

type Setting = { env: string | null; value: number | null; origin: 'configured' | 'default' | 'absent'; zero_meaning: 'unset' | 'blocked' | 'no_interval_limit' | null };
type Record = { used: number; cap: number; updated_at: string };
type Limit = { id: string; name: string; daily: Setting; monthly: Setting; budget_timezone: string; recorded: { day: Record | null; month: Record | null }; operator_cap: { day: number; month: number } | null; adjustable?: boolean; adjust_note?: string | null };
type Snapshot = { as_of: string; timezone: string; usage_error: string | null; limits: Limit[] };
const stamp = (value: string) => new Date(value).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', hour12: false });
const origin = { configured: '명시 설정', default: '기본값', absent: '설정 항목 없음' };
const UNSET_BUDGET_CAP = 2_000_000_000; // CallBudget의 상한 미설정 표시값.

function settingText(value: Setting) {
  const zero = value.zero_meaning === 'unset' ? '미설정 · 세기만' : value.zero_meaning === 'blocked' ? '호출 차단' : '간격 제한 안 함';
  return value.value === null ? '설정 항목 없음' : value.value === 0 ? `0 · ${zero}` : `${formatNumber(value.value)}회`;
}

function SettingValue({ value }: { value: Setting }) {
  return <><strong>{settingText(value)}</strong><small>{origin[value.origin]}</small>{value.env && <code>{value.env}</code>}</>;
}

const WATCH_CHECKS = [
  { id:'forecast', name:'날씨 예보', sources:'기상청·Open-Meteo', judgment:'강수확률·풍속 등의 주의사항', apis:[['kma','기상청 예보'],['open_meteo','Open-Meteo 날씨']] },
  { id:'weather_warning', name:'기상 특보', sources:'기상청', judgment:'야외 활동에 영향을 주는 특보', apis:[['kma_warning','기상청 특보']] },
  { id:'disaster_msg', name:'재난문자', sources:'행정안전부', judgment:'해당 지역의 화재·재난·통제 등', apis:[['disaster_msg','행정안전부 재난문자']] },
  { id:'traffic_control', name:'도로 상황', sources:'UTIC·ITS', judgment:'사고·공사·행사·도로 통제', apis:[['utic','UTIC'],['its','ITS']] },
  { id:'air_quality', name:'대기질', sources:'에어코리아·Open-Meteo', judgment:'야외 활동에 영향을 주는 대기 상태', apis:[['airkorea','에어코리아'],['open_meteo_air','Open-Meteo 대기질']] },
  { id:'earthquake', name:'지진', sources:'기상청', judgment:'장소와의 거리·발생 시각·규모', apis:[['kma_earthquake','기상청 지진']] },
];

export function MonitoringApiLimits() {
  const query = useQuery({ queryKey: ['api-environment-limits'], queryFn: () => operationApiLimits<Snapshot>() });
  return <section className={styles.section} aria-labelledby="watch-api-limits-title">
    <div className={styles.heading}><div><h2 id="watch-api-limits-title">감시 항목·API 한도</h2><p>6개 감시 항목에 사용하는 API의 현재 ENV 한도를 함께 봅니다.</p></div><button disabled={query.isFetching} onClick={() => void query.refetch()}>{query.isFetching ? '한도 읽는 중…' : '감시 API 한도 다시 읽기'}</button></div>
    <p className="muted">API별 한도이며 서로 더하지 않습니다. 예보는 주의사항으로 다룹니다. 이 표는 현재 설정이며 실제 사용한 출처는 아래 회차 로그에서 확인합니다.</p>
    {query.error && <p role="alert">감시 API 한도를 읽지 못했습니다. ‘감시 API 한도 다시 읽기’를 눌러 다시 시도해 주세요.</p>}
    {query.data && <p className="muted">설정 조회 {stamp(query.data.as_of)} · ENV 변경은 운영 앱 재시작 뒤 반영됩니다.</p>}
    <div className={`${styles.table} ${styles.watchTable}`} tabIndex={0} role="region" aria-label="6개 감시 항목과 API 한도 표"><table><thead><tr><th>확인하는 것</th><th>사용하는 정보</th><th>무엇을 판단하나</th><th>API별 ENV 한도</th></tr></thead><tbody>
      {WATCH_CHECKS.map(check => <tr key={check.id}><td><strong>{check.name}</strong></td><td>{check.sources}</td><td>{check.judgment}</td><td>{check.apis.map(([id,name]) => {
        const limit = query.data?.limits.find(item => item.id === id);
        return <div className={styles.sourceLimit} key={id}><strong>{name}</strong>{limit ? <><div>하루 {settingText(limit.daily)} · 월 {settingText(limit.monthly)}</div><details><summary>ENV 이름·출처 보기</summary><small>하루: {origin[limit.daily.origin]}</small>{limit.daily.env && <code>{limit.daily.env}</code>}<small>월: {origin[limit.monthly.origin]}</small>{limit.monthly.env && <code>{limit.monthly.env}</code>}</details></> : <div>{query.isPending ? '한도 읽는 중…' : '한도 미확인'}</div>}</div>;
      })}</td></tr>)}
    </tbody></table></div>
  </section>;
}

function Recorded({ value, label }: { value: Record | null; label: string }) {
  return <div>{label}: {value === null ? '미계측' : <>{formatNumber(value.used)}회 / {value.cap >= UNSET_BUDGET_CAP ? '상한 미설정' : `${formatNumber(value.cap)}회`}<small>기록 {stamp(value.updated_at)}</small></>}</div>;
}

/** ENV 상한보다 낮게만 정한다 — 서버(`admin_service` api-cap)도 같은 규칙으로 거절한다. 월 ENV 0 은 미설정(제한 없음). */
function CapEditor({ row, onCommand, onDone }: { row: Limit; onCommand: ScreenProps['onCommand']; onDone: () => void }) {
  const envDay = row.daily.value ?? 0;
  const envMonth = row.monthly.value && row.monthly.value > 0 ? row.monthly.value : null;
  const [daily, setDaily] = useState(String(row.operator_cap?.day ?? envDay));
  const [monthly, setMonthly] = useState(String(row.operator_cap?.month ?? envMonth ?? envDay * 31));
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState('');
  async function run(command: Parameters<ScreenProps['onCommand']>[0], message: string) {
    setError(''); setDone(''); setBusy(true);
    try { await onCommand(command); setDone(message); onDone(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : '저장하지 못했습니다. 입력을 확인하고 다시 시도하세요.'); }
    finally { setBusy(false); }
  }
  function save() {
    const day = Number(daily); const month = Number(monthly);
    if (!Number.isSafeInteger(day) || day < 1 || !Number.isSafeInteger(month) || month < 1) { setError('하루 · 월 상한에 1 이상의 정수를 입력하세요.'); return; }
    if (day > month) { setError('월 상한은 하루 상한 이상이어야 합니다.'); return; }
    if (envDay > 0 && day > envDay) { setError(`하루 상한은 ENV 값(${formatNumber(envDay)}회) 이하로만 정할 수 있습니다. 올리려면 .env.apikeys 를 바꾸고 cs 프로젝트 서버를 다시 띄웁니다.`); return; }
    if (envMonth !== null && month > envMonth) { setError(`월 상한은 ENV 값(${formatNumber(envMonth)}회) 이하로만 정할 수 있습니다.`); return; }
    if (!reason.trim()) { setError('바꾸는 사유를 입력하세요.'); return; }
    void run({ type: 'api-cap', apiId: row.id, daily: day, monthly: month, reason: reason.trim() }, `${row.name} 운영자 상한을 저장했습니다. 다음 호출부터 적용됩니다.`);
  }
  function clear() {
    if (!reason.trim()) { setError('해제 사유를 입력하세요.'); return; }
    void run({ type: 'api-cap-clear', apiId: row.id, reason: reason.trim() }, `${row.name} 운영자 상한을 지우고 ENV 상한으로 돌렸습니다.`);
  }
  return <div className={styles.capEditor} role="group" aria-label={`${row.name} 운영자 상한 조정`}>
    <label>하루<input type="number" min="1" max={envDay || undefined} step="1" value={daily} onChange={event => setDaily(event.target.value)} /></label>
    <label>월<input type="number" min="1" max={envMonth ?? undefined} step="1" value={monthly} onChange={event => setMonthly(event.target.value)} /></label>
    <label>사유 (필수)<input value={reason} onChange={event => setReason(event.target.value)} placeholder="바꾸는 이유" /></label>
    <div className={styles.capButtons}><button className="primary" type="button" disabled={busy} onClick={save}>{busy ? '저장 중…' : '상한 저장'}</button>{row.operator_cap && <button type="button" disabled={busy} onClick={clear}>지정 해제 · ENV 로</button>}</div>
    <small>ENV 보다 낮게만 정합니다. 다음 호출부터 적용 · 재시작 필요 없음.</small>
    {error && <p className="error" role="alert">{error}</p>}{done && <p className="success" role="status">{done}</p>}
  </div>;
}

export function ApiEnvironmentLimits({ onCommand }: { onCommand?: ScreenProps['onCommand'] }) {
  const [editing, setEditing] = useState<string | null>(null);
  const query = useQuery({ queryKey: ['api-environment-limits'], queryFn: () => operationApiLimits<Snapshot>() });
  const [search, setSearch] = useState('');
  const rows = (query.data?.limits ?? []).filter(row => `${row.id} ${row.name} ${row.daily.env ?? ''} ${row.monthly.env ?? ''}`.toLowerCase().includes(search.trim().toLowerCase()));
  return <section className={`panel ${styles.section}`} aria-labelledby="api-env-title">
    <div className={styles.heading}><div><h2 id="api-env-title">API 환경설정 한도</h2><p className="muted">현재 운영 앱이 읽은 일·월 상한입니다. 호출 이력이 없는 API도 표시합니다.</p></div><button disabled={query.isFetching} onClick={() => void query.refetch()}>{query.isFetching ? '설정 읽는 중…' : '한도 다시 읽기'}</button></div>
    <p className="muted">ENV를 지정하지 않은 항목은 기본값으로 표시합니다. ENV 파일 변경은 운영 앱을 재시작한 뒤 반영됩니다. 공급자 무료 제공량과는 별개입니다.</p>
    <label className={styles.search}>API·환경변수 찾기<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="예: ITS, 기상청, ACOP_RATE" /></label>
    {query.error && <p role="alert">한도 설정을 읽지 못했습니다. {query.error.message} ‘한도 다시 읽기’를 눌러 다시 시도해 주세요.</p>}
    {query.data?.usage_error && <p role="alert">{query.data.usage_error} 환경설정 한도만 표시하고 있습니다.</p>}
    {query.data && <p className="muted">{rows.length}/{query.data.limits.length}개 표시 · 조회 {stamp(query.data.as_of)} · 한국 시각</p>}
    <div className={styles.table} tabIndex={0} role="region" aria-label="API 한도 표 · 좁은 화면에서는 가로로 이동"><table><caption className={styles.caption}>API별 ENV 한도와 현재 일·월 DB 기록</caption><thead><tr><th>API</th><th>ENV 하루 상한</th><th>ENV 월 상한</th><th>DB 사용 / 마지막 기록 상한</th><th>운영자 지정 상한</th></tr></thead><tbody>
      {rows.map(row => <tr key={row.id}><td><strong>{row.name}</strong><small>{row.id}</small></td><td><SettingValue value={row.daily} /></td><td><SettingValue value={row.monthly} /></td><td><Recorded value={row.recorded.day} label="일" /><Recorded value={row.recorded.month} label="월" /><small>계측 기준 {row.budget_timezone}</small></td><td>{row.operator_cap ? <>일 {formatNumber(row.operator_cap.day)}회<small>월 {formatNumber(row.operator_cap.month)}회</small></> : query.data?.usage_error ? '미확인' : '별도 지정 없음'}{onCommand && (row.adjustable ? (editing === row.id ? <CapEditor row={row} onCommand={onCommand} onDone={() => void query.refetch()} /> : <button type="button" className={styles.adjust} onClick={() => setEditing(row.id)}>조정</button>) : row.adjust_note ? <small>{row.adjust_note}</small> : null)}</td></tr>)}
      {!rows.length && <tr><td colSpan={5}>{query.isPending ? '현재 프로세스의 한도를 읽고 있습니다.' : query.error ? '설정을 읽은 뒤 목록이 표시됩니다.' : <>검색 조건에 해당하는 API가 없습니다. <button onClick={() => setSearch('')}>검색어 지우기</button></>}</td></tr>}
    </tbody></table></div>
    <p className="muted">DB 상한은 마지막 호출 당시 기록입니다. 지금 읽은 ENV와 다를 수 있으며, 미계측은 0회가 아닙니다. 같은 이름의 DB 기록만 비교합니다. Google·카카오 과금 단위별 예산은 아래 ‘외부 API별 현황’에서 확인하세요.</p>
  </section>;
}
