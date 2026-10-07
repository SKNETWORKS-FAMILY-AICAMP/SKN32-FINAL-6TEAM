'use client';

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { chatLimitFor, formatNumber, watchState, type AdminCommand, type AdminSnapshot, type ApiUsage, type ScreenProps, type User, type UsersListState, type WatchRule } from '../../lib/model';
import styles from './screens.module.css';

const NEAR_CAP_PERCENT = 80; // 화면 검토용 제안값. 실제 운영 기준은 팀 합의 전이다.
const MAX_QUOTA = 100_000_000; // AdminGateway의 시연 명령 입력 범위.
const MAX_WATCH_RULES = 5;
const MAX_WATCH_MULTIPLIER = 20;
const NEW_RULE_THRESHOLDS = [80, 90, 95, 98, 99];
const MILLISECONDS_PER_DAY = 86_400_000;
const KST_OFFSET = 9 * 60 * 60 * 1000;
const number = formatNumber;
const measured = (value: number | null, unit = '') => value === null ? '미계측' : `${number(value)}${unit}`;
const money = (value: number | null) => value === null ? '단가 미정' : `$${value.toFixed(2)}`;
const sum = <T,>(items: T[], pick: (item: T) => number) => items.reduce((total, item) => total + pick(item), 0);
const instant = (date: string) => new Date(/(?:[zZ]|[+-]\d{2}:\d{2})$/.test(date) ? date : `${date.replace(' ', 'T')}+09:00`);
const kstDay = (date: string) => new Date(instant(date).getTime() + KST_OFFSET).toISOString().slice(0, 10);
const timestamp = (date: string) => instant(date).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
const checkedTimestamp = (date: string) => instant(date).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });

function capPercent(api: ApiUsage) {
  const ratios = [api.used !== null && api.dailyCap !== null ? (api.dailyCap === 0 ? 100 : api.used / api.dailyCap * 100) : null,
    api.monthlyUsed !== null && api.monthlyCap !== null ? (api.monthlyCap === 0 ? 100 : api.monthlyUsed / api.monthlyCap * 100) : null].filter((value): value is number => value !== null);
  return ratios.length ? Math.max(...ratios) : null;
}

function integer(value: string, label: string) {
  const parsed = Number(value);
  if (!value.trim() || !Number.isSafeInteger(parsed) || parsed < 1) throw new Error(`${label}에 1 이상의 정수를 입력하세요.`);
  if (parsed > MAX_QUOTA) throw new Error(`${label}는 ${number(MAX_QUOTA)} 이하로 입력하세요.`);
  return parsed;
}

function reasonRequired(value: string) {
  if (!value.trim()) throw new Error('바꾸는 사유를 입력하세요. 아직 저장하지 않았습니다.');
  return value.trim();
}

function useCommand(onCommand: ScreenProps['onCommand']) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  async function run(make: () => AdminCommand, success: string) {
    setError(''); setMessage(''); setBusy(true);
    try { await onCommand(make()); setMessage(success); return true; }
    catch (cause) { setError(cause instanceof Error ? cause.message : '변경하지 못했습니다. 입력을 확인하고 다시 시도하세요.'); return false; }
    finally { setBusy(false); }
  }
  return { run, busy, clear: () => { setError(''); setMessage(''); }, feedback: <>{error && <p className="error" role="alert">{error}</p>}{message && <p className="success" role="status">{message}</p>}</> };
}

function Heading({ eyebrow, title, children, action }: { eyebrow: string; title: string; children: ReactNode; action?: ReactNode }) {
  return <header className={styles.heading}><div><p className={styles.eyebrow}>{eyebrow}</p><h1>{title}</h1><p className="muted">{children}</p></div>{action}</header>;
}

function Meter({ value, max, label }: { value: number; max: number; label: string }) {
  const percent = max === 0 ? 100 : Math.min(100, Math.max(0, value / max * 100));
  return <div className={styles.meter} role="meter" aria-label={label} aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(percent)} aria-valuetext={`${number(value)} / ${number(max)}`}><span className={percent >= NEAR_CAP_PERCENT ? styles.meterWarning : ''} style={{ width: `${percent}%` }} /></div>;
}

function Metric({ label, value, detail, onClick, warning = false }: { label: string; value: ReactNode; detail: ReactNode; onClick?: () => void; warning?: boolean }) {
  const content = <><span className={styles.metricLabel}>{label}</span><strong className={warning ? styles.warning : ''}>{value}</strong><span className={styles.metricDetail}>{detail}</span>{onClick && <span className={styles.metricArrow} aria-hidden="true">↗</span>}</>;
  return onClick ? <button className={styles.metricCard} onClick={onClick}>{content}</button> : <div className={styles.metricCard}>{content}</div>;
}

function Empty({ children }: { children: ReactNode }) { return <p className={styles.empty}>{children}</p>; }
function PanelTitle({ title, aside }: { title: string; aside?: ReactNode }) { return <div className={styles.panelTitle}><h2>{title}</h2>{aside}</div>; }
function TableWrap({ children }: { children: ReactNode }) { return <div className={styles.tableWrap}>{children}</div>; }

export function HomeScreen({ data, navigate }: ScreenProps) {
  const openInquiries = data.inquiries.filter(item => item.status !== '답변 완료');
  const atLimit = data.users.filter(user => user.chat >= chatLimitFor(user, data));
  const adjusted = data.apis.filter(api => watchState(api, data.watchRules).startsWith('간격'));
  const stopped = data.apis.filter(api => watchState(api, data.watchRules) === '멈춤');
  const near = data.apis.filter(api => (capPercent(api) ?? 0) >= NEAR_CAP_PERCENT);
  const problems = data.server.checks.filter(check => check.status === '이상');
  const approvals = data.approvals.filter(item => item.status === '대기');
  const unresolved = data.outbox.filter(item => item.resolution === null);
  const todayUsage = data.daily.find(row => row.day === kstDay(data.clock));
  const pending = [
    ...openInquiries.map(item => ({ id: item.id, kind: '문의', target: item.userId, title: item.title, at: item.receivedAt, path: `/inquiries/${item.id}` })),
    ...approvals.map(item => ({ id: item.id, kind: '승인 대기 · 임시', target: item.userId, title: item.request, at: item.at, path: '/ops' })),
    ...unresolved.map(item => ({ id: item.id, kind: '발송 미확인 · 임시', target: item.topic, title: '하류 확인 후 배달 여부 기록', at: null, path: '/ops' })),
    ...atLimit.map(user => ({ id: user.id, kind: '채팅 한도', target: user.id, title: '오늘 채팅 한도에 도달했습니다', at: null, path: `/users/${user.id}` })),
  ].sort((a, b) => a.at && b.at ? a.at.localeCompare(b.at) : a.at ? -1 : b.at ? 1 : 0);
  function waited(at: string | null) {
    if (!at) return '발생 시각 미계측';
    const minutes = Math.max(0, Math.floor((instant(data.clock).getTime() - instant(at).getTime()) / 60_000));
    return minutes >= 60 ? `${Math.floor(minutes / 60)}시간 ${minutes % 60}분` : `${minutes}분`;
  }
  return <div className={styles.screen}>
    <Heading eyebrow="OPERATIONS / TODAY" title="오늘 처리할 일" action={<button className="primary" onClick={() => navigate('/notices')}>+ 공지 작성</button>}>{kstDay(data.clock)} · 화면 집계는 한국 시각, 외부 API 운영 예산은 UTC 기준입니다. 홈 구성은 팀 검토 중입니다.</Heading>
    {problems.length > 0 && <div className={`${styles.alertStrip} notice`}><span><strong>연결 상태를 확인해 주세요.</strong> {problems.map(item => item.name).join(' · ')}에서 이상이 있습니다.</span><button onClick={() => navigate('/server')}>서버 상태 보기 →</button></div>}
    <div className={`${styles.metrics} ${styles.homeMetrics}`}>
      <Metric label="새 문의" value={openInquiries.length} detail="접수 · 처리 중" onClick={() => navigate('/inquiries')} />
      <Metric label="한도에 걸린 사용자" value={atLimit.length} detail="② 채팅만 · ③ 웹은 집계만" onClick={() => navigate('/users')} warning={atLimit.length > 0} />
      <Metric label="감시 조절 · 잠정" value={`${adjusted.length + stopped.length}개`} detail={`간격 늘림 ${adjusted.length} · 멈춤 ${stopped.length}`} onClick={() => navigate('/limits')} warning={stopped.length > 0} />
      <Metric label="운영 상한 근접 API" value={`${near.length}개`} detail={`소진율 ${NEAR_CAP_PERCENT}% 이상 · 제안 기준`} onClick={() => navigate('/usage')} />
      <Metric label="연결 상태" value={problems.length ? `이상 ${problems.length}` : data.server.checks.length ? '이상 없음' : '미확인'} detail={`정상 ${data.server.checks.filter(check => check.status === '정상').length} · 미확인 ${data.server.checks.filter(check => check.status === '미확인').length}`} onClick={() => navigate('/server')} warning={problems.length > 0} />
      <Metric label="승인 · 발송 확인" value={approvals.length + unresolved.length} detail={`승인 ${approvals.length} · 발송 미확인 ${unresolved.length} · 임시`} onClick={() => navigate('/ops')} />
    </div>
    <section className="panel"><PanelTitle title="기다리고 있는 일" aside={<span className="muted">오래 기다린 순 · {pending.length}건</span>} />
      {pending.length === 0 ? <Empty>지금 처리할 일이 없습니다.</Empty> : <TableWrap><table><thead><tr><th>종류</th><th>대상</th><th>내용</th><th>기다린 시간</th><th>이동</th></tr></thead><tbody>{pending.map(item => <tr key={item.id}><td><span className="badge">{item.kind}</span></td><td className={styles.mono}>{item.target}</td><td>{item.title}</td><td>{waited(item.at)}</td><td><button aria-label={`${item.title} 열기`} onClick={() => navigate(item.path)}>열기 →</button></td></tr>)}</tbody></table></TableWrap>}
    </section>
    <section className="panel"><PanelTitle title="오늘 사용량 요약" aside={<button onClick={() => navigate('/usage')}>사용량 자세히 →</button>} /><div className={styles.summaryGrid}>
      <div><span className="muted">외부 API · 한국 시각 집계</span><strong>{todayUsage ? number(todayUsage.watch + todayUsage.chat) : '미계측'}</strong><small>{todayUsage ? `감시 ${number(todayUsage.watch)} / 채팅 중 조회 ${number(todayUsage.chat)}` : '오늘의 집계가 없습니다.'}</small></div>
      <div><span className="muted">우리 서버 호출</span><strong>{number(sum(data.users, user => user.chat + user.web))}</strong><small>② 채팅 {number(sum(data.users, user => user.chat))} / ③ 웹 {number(sum(data.users, user => user.web))}</small></div>
      <div><span className="muted">유료 사용 예상 비용</span><strong>{data.apis.some(api => api.cost !== null) ? money(sum(data.apis, api => api.cost ?? 0)) : '미계측'}</strong><small>미계측 API 제외 · 단가 출처 미정</small></div>
    </div></section>
  </div>;
}

export function UsersScreen({ data, navigate, listState, onListStateChange }: ScreenProps & { listState: UsersListState; onListStateChange: (state: UsersListState) => void }) {
  const { query, status, quick, order } = listState;
  const setQuery = (query: string) => onListStateChange({ ...listState, query });
  const setStatus = (status: string) => onListStateChange({ ...listState, status });
  const setQuick = (quick: string) => onListStateChange({ ...listState, quick });
  const setOrder = (order: string) => onListStateChange({ ...listState, order });
  const inquiries = (id: string) => data.inquiries.filter(item => item.userId === id).length;
  const users = data.users.filter(user => user.id.toLowerCase().includes(query.trim().toLowerCase()) && (status === '전체' || user.blocked === (status === '차단')) && (quick !== '채팅 한도 도달' || user.chat >= chatLimitFor(user, data)) && (quick !== '문의 있음' || inquiries(user.id) > 0))
    .sort((a, b) => order === '마지막 사용순' ? b.lastUsed.localeCompare(a.lastUsed) : (b.chat + b.web) - (a.chat + a.web));
  return <div className={styles.screen}><Heading eyebrow="OPERATIONS / USERS" title="사용자">사용자 ID로 식별합니다. 사용자별 집계는 ② 채팅 · ③ 웹이며, 외부 API는 서비스 전체로만 셉니다.</Heading>
    <section className="panel"><div className={styles.filters}><label>사용자 ID로 찾기<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="ID 일부 입력" /></label><label>상태<select value={status} onChange={event => setStatus(event.target.value)}>{['전체', '정상', '차단'].map(item => <option key={item}>{item}</option>)}</select></label><label>정렬<select value={order} onChange={event => setOrder(event.target.value)}><option>마지막 사용순</option><option>오늘 사용량순</option></select></label></div>
      <div className={styles.chips} role="group" aria-label="사용자 빠른 필터">{['전체', '채팅 한도 도달', '문의 있음'].map(item => <button key={item} aria-pressed={quick === item} className={quick === item ? styles.selected : ''} onClick={() => setQuick(item)}>{item}</button>)}<span className="muted">{users.length}명 / 전체 {data.users.length}명</span></div>
      {users.length === 0 ? <Empty>조건에 맞는 사용자가 없습니다. 검색어나 필터를 바꿔 보세요.</Empty> : <TableWrap><table><thead><tr><th>사용자 ID</th><th>상태</th><th>② 채팅 오늘 / 한도</th><th>③ 웹 호출</th><th>여행</th><th>문의</th><th>마지막 사용 · KST</th><th>상세</th></tr></thead><tbody>{users.map(user => <tr key={user.id}><td><button className={styles.textButton} onClick={() => navigate(`/users/${user.id}`)}>{user.id}</button></td><td><span className={user.blocked ? styles.warningBadge : 'badge'}>{user.blocked ? '차단' : '정상'}</span></td><td><div className={styles.usageCell}><span>{number(user.chat)} / {number(chatLimitFor(user, data))}{user.exceptionLimit !== null && <small> · 예외</small>}</span><Meter value={user.chat} max={chatLimitFor(user, data)} label={`${user.id} 채팅 사용률`} /></div></td><td>{number(user.web)}</td><td>{user.trips.length}</td><td>{inquiries(user.id)}</td><td className={styles.mono}>{timestamp(user.lastUsed)}</td><td><button aria-label={`${user.id} 상세 보기`} onClick={() => navigate(`/users/${user.id}`)}>상세 →</button></td></tr>)}</tbody></table></TableWrap>}
    </section><p className="muted">매일 한국 시각 00:00 초기화 · ③ 웹 호출의 한도 적용은 미정입니다.</p>
  </div>;
}

export function UserDetailScreen(props: ScreenProps & { userId: string }) {
  const user = props.data.users.find(item => item.id === props.userId);
  return user ? <UserDetail key={user.id} {...props} user={user} /> : <section className="panel"><h1>사용자를 찾을 수 없습니다</h1><p>사용자 ID를 확인하거나 목록에서 다시 선택하세요.</p><button onClick={() => props.navigate('/users')}>사용자 목록으로</button></section>;
}

function UserDetail({ data, user, onCommand, navigate }: ScreenProps & { user: User }) {
  const block = useCommand(onCommand);
  const limitAction = useCommand(onCommand);
  const [blockOpen, setBlockOpen] = useState(false);
  const [blockReason, setBlockReason] = useState('');
  const [exception, setException] = useState(String(user.exceptionLimit ?? data.chatLimit));
  const [period, setPeriod] = useState<'today' | 'until-cleared'>(user.exceptionPeriod ?? 'today');
  const [limitReason, setLimitReason] = useState('');
  const userInquiries = data.inquiries.filter(item => item.userId === user.id);
  const audits = data.audit.filter(item => item.target.includes(user.id));
  const limit = chatLimitFor(user, data);
  const nextDay = new Date(new Date(`${kstDay(data.clock)}T00:00:00+09:00`).getTime() + MILLISECONDS_PER_DAY);
  function saveLimit(event: FormEvent) { event.preventDefault(); void limitAction.run(() => ({ type: 'user-limit', userId: user.id, limit: integer(exception, '예외 한도'), period, reason: reasonRequired(limitReason) }), '예외 한도를 데모에 반영하고 운영 기록에 남겼습니다.'); }
  async function confirmBlock(event: FormEvent) {
    event.preventDefault();
    if (await block.run(() => ({ type: 'block-user', userId: user.id, blocked: !user.blocked, reason: reasonRequired(blockReason) }), `${user.blocked ? '차단 해제' : '차단'}를 데모에 반영했습니다.`)) {
      setBlockOpen(false); setBlockReason('');
    }
  }
  return <div className={styles.screen}><button className={styles.back} onClick={() => navigate('/users')}>← 사용자 목록</button>
    <Heading eyebrow="OPERATIONS / USER DETAIL" title="사용자 상세" action={<button className={user.blocked ? 'primary' : 'danger'} onClick={() => { block.clear(); setBlockOpen(!blockOpen); }}>{user.blocked ? '차단 해제' : '사용자 차단'}</button>}><strong>{user.id}</strong> · 키 발급 {timestamp(user.issuedAt)} · 마지막 사용 {timestamp(user.lastUsed)} · <span className="badge">{user.blocked ? '차단' : '정상'}</span></Heading>
    <p className="notice">서버는 키 원문을 보관하지 않습니다. 사용자 ID는 키 재발급 뒤에도 유지됩니다. 운영 차단 해제는 폐기한 옛 키를 되살리지 않습니다.</p>
    {blockOpen && <form noValidate className={`${styles.cautionPanel} panel`} onSubmit={confirmBlock}><h2>{user.blocked ? '차단 해제 확인' : '차단 확인'}</h2><p>{user.blocked ? '사용자가 같은 키로 다시 접근할 수 있습니다.' : '이 사용자의 요청을 거절합니다. 데이터는 삭제하지 않습니다.'} 진행 중인 여행 감시를 함께 멈출지는 미정입니다.</p><label>차단·해제 사유 (필수)<input value={blockReason} onChange={event => setBlockReason(event.target.value)} placeholder="처리 근거를 적어 주세요" /></label><div className="toolbar"><button className="danger" disabled={block.busy}>{block.busy ? '반영 중…' : user.blocked ? '차단 해제 확정' : '차단 확정'}</button><button type="button" onClick={() => setBlockOpen(false)}>닫기</button></div>{block.feedback}</form>}
    <div className={styles.twoColumns}><section className="panel"><h2>② 채팅 호출</h2><p className={styles.largeNumber}>{number(user.chat)} <span>/ {number(limit)}회</span></p><Meter value={user.chat} max={limit} label="오늘 채팅 사용률" /><p className={user.chat >= limit ? styles.warning : 'muted'}>{user.chat >= limit ? `한도 도달 · 요청 거절 · ${timestamp(nextDay.toISOString())}부터 다시 이용` : `오늘 ${number(Math.max(0, limit - user.chat))}회 더 이용할 수 있습니다.`}</p></section><section className="panel"><h2>③ 웹 호출</h2><p className={styles.largeNumber}>{number(user.web)} <span>회 · 집계만</span></p><h3>자주 부른 경로</h3>{user.paths.length ? <ul className={styles.pathList}>{[...user.paths].sort((a, b) => b.count - a.count).slice(0, 3).map(path => <li key={path.path}><code>{path.path}</code><strong>{number(path.count)}</strong></li>)}</ul> : <Empty>집계된 경로가 없습니다.</Empty>}</section></div>
    <section className="panel"><PanelTitle title="이 사용자 여행의 감시" aside={<button onClick={() => navigate('/limits')}>서비스 전체 감시 상태 →</button>} /><div className={styles.inlineStats}><span>진행 중 여행 <strong>{user.trips.filter(trip => trip.status === '진행 중').length}개</strong></span><span>감시 대상 장소 <strong>{sum(user.trips, trip => trip.places)}개</strong></span></div><p>서비스 전체 감시: 간격 늘림 {data.apis.filter(api => watchState(api, data.watchRules).startsWith('간격')).length}개 API · 멈춤 {data.apis.filter(api => watchState(api, data.watchRules) === '멈춤').length}개 API</p><p className="muted">외부 API 호출은 사용자·여행별로 나누지 않습니다. 서비스 전체 상태를 참고하세요.</p></section>
    <form noValidate className="panel" onSubmit={saveLimit}><PanelTitle title="사용자 예외 한도" aside={<span className="badge">현재 {user.exceptionLimit === null ? '기본 한도 사용' : `예외 ${number(user.exceptionLimit)}회`}</span>} /><div className={styles.filters}><label>② 채팅 하루 한도<input type="number" min="1" max={MAX_QUOTA} step="1" value={exception} onChange={event => setException(event.target.value)} /></label><label>적용 기간 · 정책 미정<select value={period} onChange={event => setPeriod(event.target.value as typeof period)}><option value="today">오늘만 · 데모</option><option value="until-cleared">해제할 때까지 · 데모</option></select></label></div><p className="muted">③ 웹 호출은 집계만 합니다. 예외 한도 기간은 화면 검토를 위한 제안입니다.</p><label>예외 한도 사유 (필수)<input value={limitReason} onChange={event => setLimitReason(event.target.value)} placeholder="변경하거나 해제하는 이유" /></label><div className="toolbar"><button className="primary" disabled={limitAction.busy}>예외 한도 저장</button><button type="button" disabled={limitAction.busy || user.exceptionLimit === null} onClick={() => void limitAction.run(() => ({ type: 'user-limit', userId: user.id, limit: null, period, reason: reasonRequired(limitReason) }), '예외를 해제하고 기본 한도로 돌렸습니다.')}>예외 해제 · 기본값 적용</button></div>{limitAction.feedback}</form>
    <section className="panel"><h2>여행 목록</h2>{user.trips.length ? <TableWrap><table><thead><tr><th>여행 ID</th><th>여행</th><th>상태</th><th>감시 대상 장소</th></tr></thead><tbody>{user.trips.map(trip => <tr key={trip.id}><td className={styles.mono}>{trip.id}</td><td>{trip.title}</td><td>{trip.status}</td><td>{trip.places}개</td></tr>)}</tbody></table></TableWrap> : <Empty>등록된 여행이 없습니다.</Empty>}</section>
    <div className={styles.twoColumns}><section className="panel"><PanelTitle title="문의 이력" aside={<button onClick={() => navigate('/inquiries')}>문의함 →</button>} />{userInquiries.length ? <ul className={styles.itemList}>{userInquiries.map(item => <li key={item.id}><button className={styles.textButton} onClick={() => navigate(`/inquiries/${item.id}`)}>{item.title}</button><span className="badge">{item.status}</span><small>{timestamp(item.receivedAt)}</small></li>)}</ul> : <Empty>문의 이력이 없습니다.</Empty>}</section><section className="panel"><PanelTitle title="이 사용자 운영 기록" aside={<button onClick={() => navigate('/audit')}>전체 기록 →</button>} />{audits.length ? <ul className={styles.itemList}>{audits.slice(0, 5).map(item => <li key={item.id}><strong>{item.action}</strong><span>{item.before} → {item.after}</span><small>{timestamp(item.at)} · {item.actor} · {item.reason}</small></li>)}</ul> : <Empty>운영 기록이 없습니다.</Empty>}</section></div>
  </div>;
}

export function LimitsScreen({ data, onCommand, navigate }: ScreenProps) {
  const [chatLimit, setChatLimit] = useState(String(data.chatLimit));
  const [rules, setRules] = useState<WatchRule[]>(data.watchRules.map(rule => ({ ...rule })));
  const [reason, setReason] = useState('');
  const action = useCommand(onCommand);
  const proposedLimit = Number(chatLimit);
  const proposed = { ...data, chatLimit: Number.isFinite(proposedLimit) ? proposedLimit : data.chatLimit };
  function updateRule(id: string, field: 'threshold' | 'multiplier', value: string) { setRules(current => current.map(rule => rule.id === id ? { ...rule, [field]: value === '' ? Number.NaN : Number(value) } : rule)); }
  function addRule() {
    if (rules.length >= MAX_WATCH_RULES) return;
    const threshold = NEW_RULE_THRESHOLDS.find(value => !rules.some(rule => rule.threshold === value))!;
    const previousMultiplier = Math.max(1, ...rules.filter(rule => rule.threshold < threshold && Number.isFinite(rule.multiplier)).map(rule => rule.multiplier));
    setRules(current => [...current, { id: `rule-${crypto.randomUUID()}`, threshold, multiplier: Math.min(MAX_WATCH_MULTIPLIER, previousMultiplier + 1) }]);
  }
  function save(event: FormEvent) {
    event.preventDefault();
    void action.run(() => {
      const limit = integer(chatLimit, '기본 채팅 한도');
      if (rules.some(rule => !Number.isFinite(rule.threshold) || rule.threshold < 1 || rule.threshold > 99 || !Number.isFinite(rule.multiplier) || rule.multiplier < 1.1 || rule.multiplier > MAX_WATCH_MULTIPLIER)) throw new Error('단계 소진율은 1~99%, 간격 배수는 1.1~20 사이로 입력하세요.');
      if (new Set(rules.map(rule => rule.threshold)).size !== rules.length) throw new Error('같은 소진율의 단계를 중복해서 저장할 수 없습니다.');
      const sorted = [...rules].sort((a, b) => a.threshold - b.threshold);
      if (sorted.some((rule, index) => index > 0 && rule.multiplier <= sorted[index - 1].multiplier)) throw new Error('소진율이 높은 단계일수록 감시 간격 배수를 더 크게 입력하세요.');
      return { type: 'save-limits', chatLimit: limit, rules: sorted, reason: reasonRequired(reason) };
    }, '기본 한도와 감시 단계를 데모에 반영했습니다. 운영 기록에서 변경 내용을 볼 수 있습니다.');
  }
  return <div className={styles.screen}><Heading eyebrow="SETTINGS / LIMITS" title="한도 · 감시 조절">사용자는 한 명당 하루 기준 · 외부 API는 서비스 전체 운영 상한 기준 · 감시 간격 조절은 잠정 제안입니다.</Heading>
    <form noValidate onSubmit={save} className={styles.screen}>
      <section className="panel"><PanelTitle title="사용자별 기본 일일 한도" aside={<button type="button" onClick={() => navigate('/users')}>사용자별 예외 →</button>} /><div className={styles.twoColumns}><label>② 채팅 하루 한도 (모든 사용자)<input type="number" min="1" max={MAX_QUOTA} step="1" value={chatLimit} onChange={event => setChatLimit(event.target.value)} /></label><div className={styles.quietBox}><strong>③ 웹 호출</strong><p>지금은 집계만 합니다. 한도 적용은 팀 논의 후 정합니다.</p></div></div><p className="muted">채팅 한도를 넘는 요청은 거절하고 다시 이용할 수 있는 시각을 안내합니다. 한국 시각 자정에 초기화됩니다.</p></section>
      <section className="panel"><PanelTitle title="감시 조절 단계" aside={<span className="badge">방식 확정 아님</span>} /><p>각 API의 운영 상한 소진율에 따라 그 API를 쓰는 감시 간격을 늘립니다. 공급자 무료 제공량과 운영 상한은 다릅니다.</p>
        <div className={styles.rules}>{rules.map((rule, index) => <div className={styles.rule} key={rule.id}><strong>{index + 1}단계</strong><label>운영 상한 소진율 (%)<input aria-label={`${index + 1}단계 소진율`} type="number" min="1" max="99" value={Number.isNaN(rule.threshold) ? '' : rule.threshold} onChange={event => updateRule(rule.id, 'threshold', event.target.value)} /></label><label>감시 간격 배수<input aria-label={`${index + 1}단계 간격 배수`} type="number" min="1.1" max={MAX_WATCH_MULTIPLIER} step="0.1" value={Number.isNaN(rule.multiplier) ? '' : rule.multiplier} onChange={event => updateRule(rule.id, 'multiplier', event.target.value)} /></label><button type="button" onClick={() => setRules(current => current.filter(item => item.id !== rule.id))} aria-label={`${index + 1}단계 빼기`}>빼기</button></div>)}</div>
        <div className={styles.stopRule}><strong>운영 상한 100% 도달</strong><span>그 API 호출 멈춤 · 다음 예산 초기화까지</span><span className="badge">고정 보호 단계</span></div><button type="button" disabled={rules.length >= MAX_WATCH_RULES} onClick={addRule}>+ 단계 추가</button><p className="muted">최대 {MAX_WATCH_RULES}단계 · 소진율 1~99% · 간격 1.1~20배 · 소진율이 높은 단계일수록 배수가 커야 합니다.</p>
        <p className="notice">사용자에게 감시 조절 자체를 알리지는 않습니다. 기능에 차질이 생기면 <button type="button" className={styles.textButton} onClick={() => navigate('/notices')}>공지로 알립니다 →</button></p>
      </section>
      <section className="panel"><PanelTitle title="지금 상태 · API별" aside={<button type="button" onClick={() => navigate('/usage')}>운영 상한 조정 →</button>} /><TableWrap><table><thead><tr><th>API</th><th>운영 상한 소진 · 일 / 월</th><th>현재 감시</th><th>이 API를 쓰는 감시</th></tr></thead><tbody>{data.apis.map(api => <tr key={api.id}><td>{api.name}</td><td>{api.used !== null && api.dailyCap !== null ? <div className={styles.usageCell}><span>일 {number(api.used)} / {number(api.dailyCap)}</span><small>월 {measured(api.monthlyUsed)} / {measured(api.monthlyCap)}</small><Meter value={capPercent(api)!} max={100} label={`${api.name} 일·월 운영 상한 중 큰 소진율`} /><small>일·월 중 큰 소진율 {Math.round(capPercent(api)!)}% · {api.budgetTimezone}</small></div> : '미계측'}</td><td><span className="badge">{watchState(api, data.watchRules)}</span></td><td>{api.watches}</td></tr>)}</tbody></table></TableWrap>{data.apis.length === 0 && <Empty>표시할 API가 없습니다.</Empty>}</section>
      <section className={styles.preview}><h2>저장 전 영향 미리보기</h2><div className={styles.inlineStats}><span>채팅 한도 도달 <strong>{data.users.filter(user => user.chat >= chatLimitFor(user, proposed)).length}명</strong></span><span>간격 늘림 <strong>{data.apis.filter(api => watchState(api, rules).startsWith('간격')).length}개 API</strong></span><span>호출 멈춤 <strong>{data.apis.filter(api => watchState(api, rules) === '멈춤').length}개 API</strong></span></div><p className="muted">오늘 데모 사용량 기준 · 기존 사용자 예외 한도는 유지됩니다.</p></section>
      <section className="panel"><label>한도·감시 설정 변경 사유 (필수)<input value={reason} onChange={event => setReason(event.target.value)} placeholder="변경 이유를 적어 주세요" /></label><div className="toolbar"><button className="primary" disabled={action.busy}>{action.busy ? '저장 중…' : '한도 · 감시 설정 저장'}</button><span className="muted">이전 값 → 새 값과 사유를 운영 기록에 남깁니다.</span></div>{action.feedback}</section>
    </form>
  </div>;
}

type Period = 'today' | 'week' | 'month' | 'current-month';
const PERIODS: { id: Period; label: string }[] = [{ id: 'today', label: '오늘' }, { id: 'week', label: '7일' }, { id: 'month', label: '30일' }, { id: 'current-month', label: '이번 달' }];

function UsageChart({ data, period }: { data: AdminSnapshot; period: Period }) {
  const [cumulative, setCumulative] = useState(false);
  const today = kstDay(data.clock);
  const days = period === 'today' ? 1 : period === 'week' ? 7 : 30;
  const start = period === 'current-month' ? `${today.slice(0, 7)}-01` : new Date(new Date(`${today}T00:00:00Z`).getTime() - (days - 1) * MILLISECONDS_PER_DAY).toISOString().slice(0, 10);
  const rows = data.daily.filter(row => row.day >= start && row.day <= today).sort((a, b) => a.day.localeCompare(b.day));
  const chartRows = rows.map((row, index) => cumulative ? { ...row, watch: sum(rows.slice(0, index + 1), item => item.watch), chat: sum(rows.slice(0, index + 1), item => item.chat) } : row);
  const cap = sum(data.apis, api => (cumulative ? api.monthlyCap : api.dailyCap) ?? 0);
  const seriesApis = data.apis.filter(api => api.watch !== null && api.chat !== null);
  const freeCoverageComplete = seriesApis.length > 0 && seriesApis.every(api => api.free !== null);
  const free = cumulative && freeCoverageComplete ? sum(seriesApis, api => api.free!) : 0;
  const monthlyBaseline = cumulative && period === 'current-month';
  const thresholdCap = cumulative ? monthlyBaseline ? cap : 0 : cap;
  const thresholdFree = monthlyBaseline ? free : 0;
  const max = Math.max(1, ...chartRows.map(row => row.watch + row.chat), thresholdCap, thresholdFree) * 1.08;
  return <section className="panel"><PanelTitle title={cumulative ? '외부 API 호출 · 선택 기간 누적' : '일별 외부 API 호출'} aside={<label className={styles.checkLabel}><input type="checkbox" checked={cumulative} onChange={event => setCumulative(event.target.checked)} />누적으로 보기</label>} />
    <div className={styles.chartLegend}><span><i className={styles.watchDot} />감시</span><span><i className={styles.chatDot} />채팅 중 조회</span><span>계측된 데모 호출 · 한국 시각</span></div>
    {rows.length === 0 ? <Empty>선택한 기간에 집계된 호출이 없습니다.</Empty> : <><div className={styles.chart} role="img" aria-label={`${start}부터 ${today}까지 외부 API 호출 ${cumulative ? '누적' : '일별'} 그래프. 상세 값은 아래 표에서 확인할 수 있습니다.`}>
      <span className={styles.chartMaximum}>{number(Math.ceil(max))}회</span>
      {thresholdCap > 0 && <div className={styles.capLine} style={{ bottom: `${thresholdCap / max * 100}%` }}><span>UTC 운영 상한 합계 · 참고 {number(thresholdCap)}</span></div>}
      {thresholdFree > 0 && <div className={styles.freeLine} style={{ bottom: `${thresholdFree / max * 100}%` }}><span>월 무료 제공량 합계 · 참고 {number(thresholdFree)}</span></div>}
      <div className={styles.bars}>{chartRows.map(row => <div className={styles.barColumn} key={row.day} title={`${row.day}: 감시 ${number(row.watch)}, 채팅 ${number(row.chat)}`}><div className={styles.barStack} style={{ height: `${(row.watch + row.chat) / max * 100}%` }}><span className={styles.chatBar} style={{ flex: row.chat }} /><span className={styles.watchBar} style={{ flex: row.watch }} /></div><small>{row.day.slice(5)}</small></div>)}</div>
    </div><details className={styles.chartDetails}><summary>그래프 수치 표로 보기</summary><TableWrap><table><thead><tr><th>날짜 · KST</th><th>감시</th><th>채팅 중 조회</th><th>합계</th></tr></thead><tbody>{chartRows.map(row => <tr key={row.day}><td>{row.day}</td><td>{number(row.watch)}</td><td>{number(row.chat)}</td><td>{number(row.watch + row.chat)}</td></tr>)}</tbody></table></TableWrap></details></>}
    <p className="muted">기준선은 현재 UTC 예산값의 합계 참고선입니다. 그래프는 한국 시각 집계이므로 이 선으로 실제 상한 도달 여부를 판단하지 않습니다. 실제 차단은 아래 표의 API별 UTC 일·월 사용량으로 확인합니다.</p>
    <p className="muted">{freeCoverageComplete ? '무료 제공량은 월 단위이므로 ‘이번 달 + 누적’에서 표시합니다.' : '무료 제공량이 미확인인 API가 포함되어 전체 무료 제공량선은 표시하지 않습니다. 아래 표에서 확인된 API의 무료 제공량을 따로 보세요.'} 실제 연결에는 한국 시각 집계용 계측이 필요합니다.</p>
  </section>;
}

function CapForm({ api, onCommand, onClose }: { api: ApiUsage; onCommand: ScreenProps['onCommand']; onClose: () => void }) {
  const formRef = useRef<HTMLFormElement>(null);
  const [daily, setDaily] = useState(String(api.dailyCap ?? ''));
  const [monthly, setMonthly] = useState(String(api.monthlyCap ?? ''));
  const [reason, setReason] = useState('');
  const action = useCommand(onCommand);
  useEffect(() => {
    formRef.current?.scrollIntoView({ block: 'nearest' });
    formRef.current?.querySelector<HTMLInputElement>('input')?.focus({ preventScroll: true });
  }, []);
  function save(event: FormEvent) {
    event.preventDefault();
    void action.run(() => {
      const dailyCap = integer(daily, '하루 운영 상한');
      const monthlyCap = integer(monthly, '월 운영 상한');
      if (dailyCap > monthlyCap) throw new Error('월 운영 상한은 하루 운영 상한 이상이어야 합니다.');
      return { type: 'api-cap', apiId: api.id, daily: dailyCap, monthly: monthlyCap, reason: reasonRequired(reason) };
    }, `${api.name} 운영 상한을 데모에 반영했습니다.`);
  }
  return <form ref={formRef} noValidate aria-label={`${api.name} 운영 상한 조정`} className={`${styles.capForm} panel`} onSubmit={save}><PanelTitle title={`${api.name} · 운영 상한 조정`} aside={<button type="button" onClick={onClose}>닫기</button>} /><p>운영 상한은 공급자 무료 제공량과 다릅니다. 유료 사용 허용 여부는 API별로 합의하며, 이 화면에서 결제나 실제 호출을 시작하지 않습니다.</p><div className={styles.filters}><label>하루 운영 상한<input type="number" min="1" max={MAX_QUOTA} step="1" value={daily} onChange={event => setDaily(event.target.value)} /></label><label>월 운영 상한<input type="number" min="1" max={MAX_QUOTA} step="1" value={monthly} onChange={event => setMonthly(event.target.value)} /></label></div><p className="muted">1~{number(MAX_QUOTA)}회 · 월 상한은 하루 상한 이상 · 예산 기준 {api.budgetTimezone}</p><label>운영 상한 변경 사유 (필수)<input maxLength={1000} value={reason} onChange={event => setReason(event.target.value)} /></label><button className="primary" disabled={action.busy}>{action.busy ? '저장 중…' : '운영 상한 저장'}</button>{action.feedback}</form>;
}

export function UsageScreen({ data, onCommand, navigate }: ScreenProps) {
  const [period, setPeriod] = useState<Period>('week');
  const [editingApi, setEditingApi] = useState<string | null>(null);
  const today = kstDay(data.clock);
  const days = period === 'today' ? 1 : period === 'week' ? 7 : 30;
  const start = period === 'current-month' ? `${today.slice(0, 7)}-01` : new Date(new Date(`${today}T00:00:00Z`).getTime() - (days - 1) * MILLISECONDS_PER_DAY).toISOString().slice(0, 10);
  const selectedDays = data.daily.filter(row => row.day >= start && row.day <= today);
  const edited = data.apis.find(api => api.id === editingApi);
  const externalLlm = data.llm.filter(llm => !llm.local);
  return <div className={styles.screen}><Heading eyebrow="USAGE / SERVICE" title="사용량">외부 API는 서비스 전체로 집계합니다. 공급자 무료 제공량 · 운영 상한 · 유료 사용을 구분합니다.</Heading>
    <div className={styles.chips} role="group" aria-label="사용량 기간">{PERIODS.map(item => <button key={item.id} aria-pressed={period === item.id} className={period === item.id ? styles.selected : ''} onClick={() => setPeriod(item.id)}>{item.label}</button>)}<span className="muted">외부 호출 그래프 기간 · 한국 시각</span></div>
    <div className={styles.metrics}><Metric label="선택 기간 외부 API 호출" value={number(sum(selectedDays, row => row.watch + row.chat))} detail={`감시 ${number(sum(selectedDays, row => row.watch))} / 채팅 조회 ${number(sum(selectedDays, row => row.chat))}`} /><Metric label="현재 운영 상한 근접" value={`${data.apis.filter(api => (capPercent(api) ?? 0) >= NEAR_CAP_PERCENT).length}개`} detail={`${NEAR_CAP_PERCENT}% 이상 · 제안 기준`} onClick={() => navigate('/limits')} /><Metric label="오늘 유료 사용 예상 비용" value={data.apis.some(api => api.cost !== null) ? money(sum(data.apis, api => api.cost ?? 0)) : '미계측'} detail="미계측 제외 · 단가 출처 미정" /><Metric label="오늘 외부 LLM 토큰" value={number(sum(externalLlm, llm => llm.input + llm.output))} detail={`입력 ${number(sum(externalLlm, llm => llm.input))} / 출력 ${number(sum(externalLlm, llm => llm.output))}`} /></div>
    <UsageChart data={data} period={period} />
    <section className="panel"><PanelTitle title="외부 API별 현황" aside={<span className="muted">현재 예산 일·월 기준 · 소진율은 일/월 중 큰 값</span>} /><TableWrap><table className={styles.apiTable}><thead><tr><th>API · 준비 상태</th><th>공급자 무료 제공량 / 월</th><th>사용 · 일 / 월</th><th>운영 상한 · 일 / 월</th><th>운영 상한 소진</th><th>감시 상태</th><th>유료 사용 · 비용</th><th>조정</th></tr></thead><tbody>{data.apis.map(api => <tr key={api.id}><td><strong>{api.name}</strong><small>어댑터: {api.adapter}</small><small>연결: {api.connection}</small><small>계측: {api.metering}</small></td><td>{api.free === null ? '미확인' : <>{number(api.free)}{api.monthlyUsed !== null && api.free > 0 && <small>월 사용 대비 {Math.round(api.monthlyUsed / api.free * 100)}% 소진</small>}</>}</td><td>{measured(api.used)}<small>월 {measured(api.monthlyUsed)}</small></td><td>{measured(api.dailyCap)}<small>월 {measured(api.monthlyCap)}</small><small>기준 시간대 {api.budgetTimezone}</small></td><td>{capPercent(api) === null ? '미계측' : <div className={styles.usageCell}><span>{Math.round(capPercent(api)!)}%</span><Meter value={capPercent(api)!} max={100} label={`${api.name} 운영 상한 소진율`} /></div>}</td><td><span className="badge">{watchState(api, data.watchRules)}</span></td><td>{measured(api.paid)}<small>{money(api.cost)}</small></td><td><button onClick={() => setEditingApi(api.id)} disabled={api.dailyCap === null || api.monthlyCap === null} aria-label={`${api.name} 운영 상한 조정`}>조정</button>{api.dailyCap === null && <small>계약 필요</small>}</td></tr>)}</tbody></table></TableWrap>{data.apis.length === 0 && <Empty>표시할 API가 없습니다.</Empty>}<p className="muted">현재 구글·카카오는 운영 상한에 닿으면 호출을 막습니다. 무료 제공량을 넘으면 자동으로 유료 전환되는 화면이 아닙니다.</p></section>
    {edited && <CapForm key={edited.id} api={edited} onCommand={onCommand} onClose={() => setEditingApi(null)} />}
    <section className="panel"><PanelTitle title="우리 서버 호출 · 오늘" aside={<span className="badge">③ 웹 호출은 집계만</span>} /><div className={styles.inlineStats}><span>② 채팅 <strong>{number(sum(data.users, user => user.chat))}회</strong></span><span>③ 웹 <strong>{number(sum(data.users, user => user.web))}회</strong></span></div><TableWrap><table><thead><tr><th>경로</th><th>호출</th><th>사용자 수</th></tr></thead><tbody>{[...data.requests].sort((a, b) => b.count - a.count).map(request => <tr key={request.path}><td><code>{request.path}</code></td><td>{number(request.count)}</td><td>{request.users}</td></tr>)}</tbody></table></TableWrap>{data.requests.length === 0 && <Empty>집계된 경로가 없습니다.</Empty>}<p className="muted">경로 통계로 ‘자주 보는 화면’을 대신할지는 미정입니다.</p></section>
    <section className="panel"><h2>LLM 모델별 · 오늘</h2><TableWrap><table><thead><tr><th>모델</th><th>분류</th><th>호출</th><th>입력 / 출력 토큰</th><th>비용</th><th>평균 지연</th></tr></thead><tbody>{data.llm.map(llm => <tr key={llm.model}><td>{llm.model}</td><td>{llm.local ? '로컬 · 서버 자원' : '외부 API'}</td><td>{number(llm.calls)}</td><td>{number(llm.input)} / {number(llm.output)}</td><td>{money(llm.cost)}</td><td>{llm.latency.toLocaleString('ko-KR')} ms</td></tr>)}</tbody></table></TableWrap>{data.llm.length === 0 && <Empty>기록된 모델 호출이 없습니다.</Empty>}<p className="muted">외부 모델은 외부 API, 로컬 모델은 서버 자원으로 구분하는 제안입니다.</p></section>
  </div>;
}

export function ServerScreen({ data, onCommand }: ScreenProps) {
  const action = useCommand(onCommand);
  return <div className={styles.screen}><Heading eyebrow="OPERATIONS / HEALTH" title="서버 상태" action={<button className="primary" disabled={action.busy} onClick={() => void action.run(() => ({ type: 'check-server' }), '데모 연결 점검 시각을 갱신했습니다. 실제 서버를 호출하지 않았습니다.')}>{action.busy ? '점검 중…' : '지금 다시 점검'}</button>}>마지막 점검 {checkedTimestamp(data.server.checkedAt)} KST · 배포처 미정</Heading>{action.feedback}
    <section><h2>연결 점검</h2><div className={styles.checkGrid}>{data.server.checks.map(check => <article className={`${styles.checkCard} ${check.status === '이상' ? styles.checkProblem : ''}`} key={check.name}><div className={styles.panelTitle}><h3>{check.name}</h3><span className={check.status === '이상' ? styles.warningBadge : 'badge'}>{check.status}</span></div><p>{check.detail}</p><small className="muted">확인 {checkedTimestamp(data.server.checkedAt)} KST</small></article>)}</div>{data.server.checks.length === 0 && <Empty>연결 점검 결과가 없습니다.</Empty>}</section>
    <section className="panel"><PanelTitle title="서버 자원 · 지금 값" aside={<span className="badge">데모 스냅샷</span>} /><div className={styles.resourceGrid}>
      <article><h3>프로세스</h3><dl><dt>CPU</dt><dd>{data.server.cpu}%</dd><dt>메모리 사용률</dt><dd>{data.server.memory}%</dd><dt>가동 시간</dt><dd>{data.server.uptime}</dd><dt>재시작</dt><dd>{data.server.restarts}회</dd></dl></article>
      <article><h3>데이터베이스</h3><dl><dt>크기</dt><dd>{data.server.dbSize}</dd><dt>연결</dt><dd>{data.server.dbConnections}개</dd><dt>느린 쿼리</dt><dd>{data.server.slowQueries}건</dd></dl></article>
      <article><h3>백그라운드 작업</h3><dl><dt>감시 마지막 실행</dt><dd>{timestamp(data.server.lastWatch)}</dd><dt>감시 실패</dt><dd>{data.server.watchFailures}건</dd><dt>발송 결과 미확인</dt><dd>{data.outbox.filter(item => item.resolution === null).length}건</dd></dl></article>
      <article><h3>디스크</h3><p className={styles.largeNumber}>{data.server.disk}<span>% 사용</span></p><Meter value={data.server.disk} max={100} label="디스크 사용률" /></article>
    </div></section>
    <section className="panel"><h2>경로별 요청 · 오늘</h2><TableWrap><table><thead><tr><th>경로</th><th>요청 수</th><th>오류율</th><th>응답 시간 중간값</th><th>느린 5% · p95</th></tr></thead><tbody>{data.requests.map(request => <tr key={request.path}><td><code>{request.path}</code></td><td>{number(request.count)}</td><td className={request.errorRate > 0 ? styles.warning : ''}>{request.errorRate}%</td><td>{number(request.p50)} ms</td><td>{number(request.p95)} ms</td></tr>)}</tbody></table></TableWrap>{data.requests.length === 0 && <Empty>집계된 요청이 없습니다.</Empty>}</section>
    <p className="notice">시간별 추이 그래프는 2차 제안입니다. 현재 백엔드의 /health는 프로세스 응답만 확인하며, 이 화면의 연결·자원 지표는 데모 데이터입니다.</p>
  </div>;
}
