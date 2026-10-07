'use client';

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react';
import { INITIAL_INQUIRIES_LIST, chatLimitFor, formatNumber, type AdminCommand, type Inquiry, type InquiryStatus, type InquiriesListState, type Notice, type ScreenProps } from '../../lib/model';
import { DEMO_OPERATOR } from '../../lib/demo/fixtures';
import styles from './screens.module.css';

const INQUIRY_STATUSES: InquiryStatus[] = ['접수', '처리 중', '답변 완료'];
const KST_OFFSET_MS = 9 * 60 * 60 * 1000;
const DAY_MS = 24 * 60 * 60 * 1000;

function kstTimestamp(value: string) {
  const normalized = value.replace(' ', 'T');
  return new Date(/(?:Z|[+-]\d{2}:\d{2})$/i.test(normalized) ? normalized : `${normalized}+09:00`).getTime();
}

function displayTime(value: string) {
  const date = new Date(kstTimestamp(value));
  return Number.isNaN(date.getTime()) ? '시각 미확인' : new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(date);
}

function dateInput(value: string) {
  const timestamp = kstTimestamp(value);
  return Number.isNaN(timestamp) ? '' : new Date(timestamp + KST_OFFSET_MS).toISOString().slice(0, 16);
}

function useCommandFeedback(onCommand: ScreenProps['onCommand']) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  async function run(command: AdminCommand, message: string) {
    setError(''); setSuccess(''); setPending(true);
    try {
      await onCommand(command);
      setSuccess(message);
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '변경을 저장하지 못했습니다. 다시 시도해 주세요.');
      return false;
    } finally { setPending(false); }
  }
  function invalid(message: string) { setSuccess(''); setError(message); }
  return { pending, error, success, run, invalid };
}

function Feedback({ error, success }: { error: string; success: string }) {
  return <>{error && <p className="error" role="alert">{error}</p>}{success && <p className="success" role="status">{success}</p>}</>;
}

function Empty({ children }: { children: string }) {
  return <div className={styles.empty}><span aria-hidden="true">○</span><p>{children}</p></div>;
}

function WorkflowDialog({ children, titleId, locked, onClose }: { children: ReactNode; titleId: string; locked: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    const trigger = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    dialog?.showModal();
    return () => {
      dialog?.close();
      if (trigger?.isConnected) trigger.focus();
    };
  }, []);
  return <dialog ref={ref} className={styles.dialog} aria-labelledby={titleId} onCancel={event => { event.preventDefault(); if (!locked) onClose(); }}>{children}</dialog>;
}

export function InquiriesScreen({ data, onCommand, navigate, inquiryId, listState, onListStateChange }: ScreenProps & { inquiryId?: string; listState: InquiriesListState; onListStateChange: (state: InquiriesListState) => void }) {
  const { status, query, owner } = listState;
  const setStatus = (status: InquiriesListState['status']) => onListStateChange({ ...listState, status });
  const setQuery = (query: string) => onListStateChange({ ...listState, query });
  const setOwner = (owner: string) => onListStateChange({ ...listState, owner });
  const [manageTemplates, setManageTemplates] = useState(false);
  const operators = [...new Set([DEMO_OPERATOR, ...data.inquiries.map(item => item.assignee), ...data.audit.map(item => item.actor)])].filter(Boolean).sort();
  const filtered = data.inquiries.filter(item => (status === '전체' || item.status === status) && (owner === 'all' || (owner === 'unassigned' ? !item.assignee : item.assignee === owner)) && `${item.title} ${item.body} ${item.userId}`.toLowerCase().includes(query.toLowerCase().trim()));
  const requestedInquiry = inquiryId ? data.inquiries.find(item => item.id === inquiryId) : undefined;
  const selected = inquiryId ? filtered.find(item => item.id === inquiryId) : filtered[0];

  return <div className={styles.stack}>
    <header className={styles.heading}><div><p className={styles.eyebrow}>INBOX</p><h1>문의함</h1><p className="muted">사용자에게 필요한 답변을, 한곳에서.</p></div><span className="badge">미답변 {data.inquiries.filter(item => item.status !== '답변 완료').length}건</span></header>
    <div className={styles.inbox}>
      <section className={`panel ${styles.inboxList}`} aria-label="문의 목록">
        <div className={styles.tabs} aria-label="문의 상태 필터">{(['전체', ...INQUIRY_STATUSES] as const).map(value => <button key={value} type="button" aria-pressed={status === value} className={status === value ? styles.activeTab : ''} onClick={() => setStatus(value)}>{value}<span>{value === '전체' ? data.inquiries.length : data.inquiries.filter(item => item.status === value).length}</span></button>)}</div>
        <div className={styles.listFilters}><label>문의 찾기<input value={query} onChange={event => setQuery(event.target.value)} placeholder="제목, 내용 또는 사용자 ID" /></label><label>담당자 필터<select value={owner} onChange={event => setOwner(event.target.value)}><option value="all">담당 전체</option><option value="unassigned">미지정</option><option value={DEMO_OPERATOR}>내 담당</option>{operators.filter(operator => operator !== DEMO_OPERATOR).map(operator => <option key={operator}>{operator}</option>)}</select></label></div>
        <div className={styles.inquiryItems}>{filtered.length ? filtered.map(item => <button key={item.id} type="button" className={`${styles.inquiryItem} ${selected?.id === item.id ? styles.selectedItem : ''}`} aria-pressed={selected?.id === item.id} onClick={() => navigate(`/inquiries/${item.id}`)}><div className={styles.row}><span className={`badge ${item.status === '접수' ? styles.warmBadge : ''}`}>{item.status}</span><time className={styles.small}>{displayTime(item.receivedAt)}</time></div><strong>{item.title}</strong><span className={styles.excerpt}>{item.body}</span><span className={styles.small}>{item.userId} · {item.assignee || '담당 미지정'}</span></button>) : <Empty>조건에 맞는 문의가 없습니다.</Empty>}</div>
      </section>
      {selected ? <InquiryDetail key={selected.id} inquiry={selected} data={data} onCommand={onCommand} navigate={navigate} operators={operators} onManageTemplates={() => setManageTemplates(true)} /> : <section className="panel"><Empty>{requestedInquiry ? '선택한 문의가 현재 필터에 포함되지 않습니다.' : inquiryId ? '요청한 문의를 찾을 수 없습니다.' : '문의가 접수되면 여기에서 내용을 확인할 수 있습니다.'}</Empty>{requestedInquiry ? <button type="button" onClick={() => onListStateChange(INITIAL_INQUIRIES_LIST)}>문의 필터 초기화</button> : inquiryId && <button type="button" onClick={() => navigate('/inquiries')}>문의 목록으로 돌아가기</button>}</section>}
    </div>
    {manageTemplates && <TemplateManager data={data} onCommand={onCommand} onClose={() => setManageTemplates(false)} />}
  </div>;
}

function InquiryDetail({ inquiry, data, onCommand, navigate, operators, onManageTemplates }: ScreenProps & { inquiry: Inquiry; operators: string[]; onManageTemplates: () => void }) {
  const [status, setStatus] = useState(inquiry.status);
  const [assignee, setAssignee] = useState(inquiry.assignee);
  const [reason, setReason] = useState('');
  const [reply, setReply] = useState('');
  const [template, setTemplate] = useState('');
  const feedback = useCommandFeedback(onCommand);
  const user = data.users.find(item => item.id === inquiry.userId);
  async function saveStatus(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reason.trim()) return feedback.invalid('문의 상태·담당 변경 사유를 입력해 주세요.');
    if (status === inquiry.status && assignee === inquiry.assignee) return feedback.invalid('변경할 상태 또는 담당자를 선택해 주세요.');
    if (await feedback.run({ type: 'inquiry-status', inquiryId: inquiry.id, status, assignee, reason }, '문의 상태와 담당자를 데모에 저장했습니다.')) setReason('');
  }
  async function sendReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reply.trim()) return feedback.invalid('답변 내용을 입력해 주세요.');
    if (await feedback.run({ type: 'reply', inquiryId: inquiry.id, body: reply }, '답변을 데모에 저장했습니다. 상태가 답변 완료로 바뀌었습니다.')) { setReply(''); setTemplate(''); setStatus('답변 완료'); setAssignee(DEMO_OPERATOR); }
  }
  return <section className={`panel ${styles.detail}`} aria-label="문의 상세">
    <div className={styles.row}><span className="badge">{inquiry.status}</span><span className={styles.small}>{inquiry.id}</span></div>
    <h2>{inquiry.title}</h2><div className={styles.meta}><button type="button" className={styles.textButton} onClick={() => navigate(`/users/${inquiry.userId}`)}>{inquiry.userId} ↗</button><span>{displayTime(inquiry.receivedAt)} 접수</span><span>{inquiry.language}</span></div>
    <div className={styles.message}>{inquiry.body}</div>
    <div className={styles.userContext}><strong>이 사용자 오늘</strong>{user ? <><span>② 채팅 <b>{formatNumber(user.chat)} / {formatNumber(chatLimitFor(user, data))}</b></span><span>③ 웹 <b>{formatNumber(user.web)}</b></span><span>여행 <b>{user.trips.length}건</b></span></> : <span>사용량 정보 없음</span>}<button type="button" className={styles.textButton} onClick={() => navigate(`/users/${inquiry.userId}`)}>사용자 상세 →</button></div>
    <form onSubmit={saveStatus} noValidate className={styles.formSection}><div className={styles.twoColumns}><label>문의 담당자<select value={assignee} onChange={event => setAssignee(event.target.value)}><option value="">미지정</option>{operators.map(operator => <option key={operator}>{operator}</option>)}</select></label><label>문의 상태<select value={status} onChange={event => setStatus(event.target.value as InquiryStatus)}>{INQUIRY_STATUSES.map(value => <option key={value}>{value}</option>)}</select></label></div><div className={styles.inlineForm}><label>상태·담당 변경 사유 (필수)<input value={reason} onChange={event => setReason(event.target.value)} placeholder="상태나 담당자를 바꾸는 이유" /></label><button disabled={feedback.pending} type="submit">상태·담당 저장</button></div></form>
    {inquiry.replies.map((item, index) => <div key={`${item.at}-${index}`} className={styles.reply}><div className={styles.row}><strong>{item.operator}의 답변</strong><time>{displayTime(item.at)}</time></div><p>{item.body}</p></div>)}
    <form className={styles.formSection} onSubmit={sendReply} noValidate><div className={styles.row}><h3>답변 작성</h3><button type="button" className={styles.textButton} onClick={onManageTemplates}>템플릿 관리</button></div><label>답변 템플릿<select value={template} onChange={event => { const id = event.target.value; setTemplate(id); const found = data.templates.find(item => item.id === id); if (found) setReply(found.body); }}><option value="">템플릿 고르기</option>{data.templates.map(item => <option key={item.id} value={item.id}>{item.title}</option>)}</select></label><label>답변 본문<textarea rows={6} value={reply} onChange={event => setReply(event.target.value)} placeholder="사용자가 이해하기 쉽게 답변을 작성하세요." /></label><div className={styles.formFooter}><p className="muted">답변 본문을 운영 기록에 남기고,<br />상태를 답변 완료로 바꿉니다.</p><button disabled={feedback.pending} className="primary" type="submit">{feedback.pending ? '저장 중…' : '답변 보내기'}</button></div></form>
    <Feedback {...feedback} /><section className={styles.history}><h3>처리 이력</h3>{inquiry.history.map((item, index) => <div key={`${item.at}-${index}`}><time>{displayTime(item.at)}</time><span>{item.text}</span></div>)}</section>
  </section>;
}

function TemplateManager({ data, onCommand, onClose }: Pick<ScreenProps, 'data' | 'onCommand'> & { onClose: () => void }) {
  const [id, setId] = useState('');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const feedback = useCommandFeedback(onCommand);
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim() || !body.trim()) return feedback.invalid('템플릿 제목과 본문을 모두 입력해 주세요.');
    if (await feedback.run({ type: 'save-template', ...(id ? { id } : {}), title, body }, '답변 템플릿을 데모에 저장했습니다.')) { setId(''); setTitle(''); setBody(''); }
  }
  return <WorkflowDialog titleId="template-title" locked={feedback.pending} onClose={onClose}><div className={styles.row}><h2 id="template-title">답변 템플릿 관리</h2><button type="button" aria-label="템플릿 관리 닫기" onClick={onClose} disabled={feedback.pending}>닫기</button></div><p className="muted">반복되는 안내를 저장하고, 답변 전에 내용을 다듬어 주세요.</p><form onSubmit={save} className={styles.stack} noValidate><label>편집할 템플릿<select value={id} onChange={event => { const found = data.templates.find(item => item.id === event.target.value); setId(found?.id ?? ''); setTitle(found?.title ?? ''); setBody(found?.body ?? ''); }}><option value="">새 템플릿</option>{data.templates.map(item => <option value={item.id} key={item.id}>{item.title}</option>)}</select></label><label>템플릿 제목<input value={title} onChange={event => setTitle(event.target.value)} /></label><label>템플릿 본문<textarea rows={7} value={body} onChange={event => setBody(event.target.value)} /></label><Feedback {...feedback} /><div className={styles.actions}><button type="submit" className="primary" disabled={feedback.pending}>템플릿 저장</button></div></form></WorkflowDialog>;
}

function noticeStatus(notice: Notice, clock: string) {
  const now = kstTimestamp(clock);
  if (kstTimestamp(notice.startsAt) > now) return '예약';
  return kstTimestamp(notice.endsAt) <= now ? '종료' : '게시 중';
}

export function NoticesScreen({ data, onCommand }: ScreenProps) {
  const [maintenanceMessage, setMaintenanceMessage] = useState(data.maintenance.message);
  const [maintenanceEnglish, setMaintenanceEnglish] = useState(data.maintenance.messageEn);
  const [maintenanceEnd, setMaintenanceEnd] = useState(dateInput(data.maintenance.endsAt));
  const [reason, setReason] = useState('');
  const [kind, setKind] = useState('안내');
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [titleEn, setTitleEn] = useState('');
  const [bodyEn, setBodyEn] = useState('');
  const [startsAt, setStartsAt] = useState(dateInput(data.clock));
  const [endsAt, setEndsAt] = useState('');
  const [language, setLanguage] = useState<'ko' | 'en'>('en');
  const [preview, setPreview] = useState(false);
  const [noticeFilter, setNoticeFilter] = useState('전체');
  const maintenanceFeedback = useCommandFeedback(onCommand);
  const publishFeedback = useCommandFeedback(onCommand);
  async function toggleMaintenance(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reason.trim()) return maintenanceFeedback.invalid('점검 모드를 바꾸는 사유를 입력해 주세요.');
    if (!data.maintenance.enabled && (!maintenanceMessage.trim() || !maintenanceEnd)) return maintenanceFeedback.invalid('점검 안내 문구와 예상 종료 시각을 입력해 주세요.');
    if (!data.maintenance.enabled && kstTimestamp(maintenanceEnd) <= kstTimestamp(data.clock)) return maintenanceFeedback.invalid('예상 종료는 현재 데모 시각보다 뒤로 지정해 주세요.');
    if (await maintenanceFeedback.run({ type: 'maintenance', enabled: !data.maintenance.enabled, message: maintenanceMessage, messageEn: maintenanceEnglish, endsAt: maintenanceEnd, reason }, `점검 모드를 데모에서 ${data.maintenance.enabled ? '껐습니다' : '켰습니다'}.`)) setReason('');
  }
  async function publish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!title.trim() || !body.trim()) return publishFeedback.invalid('한국어 공지 제목과 내용을 입력해 주세요.');
    if (!!titleEn.trim() !== !!bodyEn.trim()) return publishFeedback.invalid('English 제목과 내용은 함께 입력해 주세요.');
    if (!startsAt || !endsAt || kstTimestamp(endsAt) <= kstTimestamp(startsAt)) return publishFeedback.invalid('게시 시작과 끝을 입력하고, 끝을 시작보다 뒤로 지정해 주세요.');
    if (await publishFeedback.run({ type: 'publish-notice', notice: { kind, title, body, titleEn, bodyEn, startsAt, endsAt } }, '공지 본문과 게시 기간을 데모에 저장했습니다.')) { setTitle(''); setBody(''); setTitleEn(''); setBodyEn(''); setPreview(false); }
  }
  const notices = data.notices.filter(item => noticeFilter === '전체' || noticeStatus(item, data.clock) === noticeFilter);
  return <div className={styles.stack}>
    <header className={styles.heading}><div><p className={styles.eyebrow}>COMMUNICATION</p><h1>공지 · 점검</h1><p className="muted">서비스의 변화를 사용자에게 알려 주세요.</p></div><span className="badge">한국 시각 기준</span></header>
    <div className={styles.noticeColumns}><div className={styles.stack}>
      <section className={`panel ${styles.card}`}><div className={styles.row}><h2>점검 모드</h2><span className={`badge ${data.maintenance.enabled ? styles.warmBadge : ''}`}>{data.maintenance.enabled ? '켜짐' : '꺼짐'}</span></div><p className="muted">사용자 웹을 막을지, 배너만 보일지는 팀 협의 중입니다.<br />여기서는 점검 안내와 전환을 시연합니다.</p><form noValidate className={styles.stack} onSubmit={toggleMaintenance}><label>점검 안내 · 한국어<textarea rows={2} value={maintenanceMessage} onChange={event => setMaintenanceMessage(event.target.value)} /></label><label>점검 안내 · English<textarea rows={2} value={maintenanceEnglish} onChange={event => setMaintenanceEnglish(event.target.value)} /></label><label>예상 종료 (한국 시각)<input type="datetime-local" value={maintenanceEnd} onChange={event => setMaintenanceEnd(event.target.value)} /></label><label>점검 전환 사유 (필수)<input value={reason} onChange={event => setReason(event.target.value)} placeholder="켜거나 끄는 이유" /></label><Feedback {...maintenanceFeedback} /><div className={styles.actions}><button className={data.maintenance.enabled ? '' : 'danger'} disabled={maintenanceFeedback.pending} type="submit">점검 모드 {data.maintenance.enabled ? '끄기' : '켜기'}</button></div></form></section>
      <section className={`panel ${styles.card}`}><div className={styles.row}><h2>공지 목록</h2><span className="muted">{notices.length}건</span></div><div className={styles.tabs} aria-label="공지 상태 필터">{['전체', '게시 중', '예약', '종료'].map(value => <button type="button" aria-pressed={noticeFilter === value} className={noticeFilter === value ? styles.activeTab : ''} key={value} onClick={() => setNoticeFilter(value)}>{value}</button>)}</div>{notices.length ? <div className={styles.noticeList}>{notices.map(item => <details key={item.id} className={styles.noticeItem}><summary><span className="badge">{noticeStatus(item, data.clock)}</span><strong>{item.title || item.titleEn}</strong></summary><p className={styles.small}>{displayTime(item.startsAt)} ~ {displayTime(item.endsAt)} · {item.author}</p><p className={styles.preserve}>{item.body || '한국어 내용 없음'}</p><p className={styles.preserve} lang="en">{item.titleEn}<br />{item.bodyEn || 'English 내용 없음'}</p></details>)}</div> : <Empty>해당 상태의 공지가 없습니다.</Empty>}</section>
    </div><div className={styles.stack}><section className={`panel ${styles.card}`}><div><p className={styles.eyebrow}>NEW NOTICE</p><h2>공지 작성</h2></div><form className={styles.stack} noValidate onSubmit={publish}><label>공지 종류<select value={kind} onChange={event => setKind(event.target.value)}><option>안내</option><option>기능 차질·장애</option><option>점검 예고</option></select></label><div className={styles.twoColumns}><label>제목 · 한국어<input value={title} onChange={event => setTitle(event.target.value)} placeholder="무엇이 달라지나요?" /></label><label>제목 · English<input value={titleEn} onChange={event => setTitleEn(event.target.value)} placeholder="Notice title" /></label><label>내용 · 한국어<textarea rows={5} value={body} onChange={event => setBody(event.target.value)} placeholder="영향을 받는 기능과 예상 시간을 알려 주세요." /></label><label>내용 · English<textarea rows={5} value={bodyEn} onChange={event => setBodyEn(event.target.value)} placeholder="Describe the service update." /></label></div><div className={styles.twoColumns}><label>게시 시작 (한국 시각)<input type="datetime-local" value={startsAt} onChange={event => setStartsAt(event.target.value)} /></label><label>게시 끝 (한국 시각)<input type="datetime-local" value={endsAt} onChange={event => setEndsAt(event.target.value)} /></label></div><p className="muted">본문을 운영 기록에 남깁니다. 데모에서는 한국어 제목·내용을 입력합니다. 한/영 필수 정책은 팀 협의 중입니다.</p><Feedback {...publishFeedback} /><div className={styles.actions}><button type="button" onClick={() => setPreview(value => !value)} aria-expanded={preview}>미리보기</button><button className="primary" type="submit" disabled={publishFeedback.pending}>공지 게시</button></div></form></section>
      <section className={`panel ${styles.preview}`} aria-label="사용자 웹 미리보기"><div className={styles.previewHeader}><strong>triPilot</strong><div className={styles.tabs}>{(['en', 'ko'] as const).map(value => <button key={value} type="button" aria-pressed={language === value} onClick={() => { setLanguage(value); setPreview(true); }}>{value === 'en' ? 'English' : '한국어'}</button>)}</div></div>{preview ? <div className={styles.previewNotice} lang={language}><span className="badge">{kind}</span><h3>{(language === 'en' ? titleEn : title) || '이 언어의 제목을 입력해 주세요'}</h3><p className={styles.preserve}>{(language === 'en' ? bodyEn : body) || '이 언어의 내용이 없습니다.'}</p></div> : <Empty>작성한 공지를 언어별로 미리 볼 수 있습니다.</Empty>}<p className={styles.previewNote}>사용자 웹 미리보기 · 기본 언어 English · 실제 사용자 웹에는 게시되지 않습니다.</p></section>
    </div></div>
  </div>;
}

export function AuditScreen({ data }: ScreenProps) {
  const [period, setPeriod] = useState('7');
  const [actor, setActor] = useState('all');
  const [action, setAction] = useState('all');
  const [query, setQuery] = useState('');
  const dayStart = Math.floor((kstTimestamp(data.clock) + KST_OFFSET_MS) / DAY_MS) * DAY_MS - KST_OFFSET_MS;
  const cutoff = period === 'all' ? -Infinity : dayStart - (Number(period) - 1) * DAY_MS;
  const entries = data.audit.filter(item => kstTimestamp(item.at) >= cutoff && (actor === 'all' || item.actor === actor) && (action === 'all' || item.action === action) && item.target.toLowerCase().includes(query.toLowerCase().trim())).sort((a, b) => kstTimestamp(b.at) - kstTimestamp(a.at));
  return <div className={styles.stack}><header className={styles.heading}><div><p className={styles.eyebrow}>AUDIT TRAIL</p><h1>운영 기록</h1><p className="muted">누가, 언제, 무엇을, 왜 바꿨는지.</p></div><span className="badge">조회 전용</span></header><section className={`panel ${styles.card}`}><div className={styles.filters}><label>기록 기간<select value={period} onChange={event => setPeriod(event.target.value)}><option value="1">오늘</option><option value="7">7일</option><option value="30">30일</option><option value="all">전체</option></select></label><label>기록 운영자<select value={actor} onChange={event => setActor(event.target.value)}><option value="all">전체 운영자</option>{[...new Set(data.audit.map(item => item.actor))].map(value => <option key={value}>{value}</option>)}</select></label><label>작업 종류<select value={action} onChange={event => setAction(event.target.value)}><option value="all">전체 작업</option>{[...new Set(data.audit.map(item => item.action))].map(value => <option key={value}>{value}</option>)}</select></label><label>대상 찾기<input value={query} onChange={event => setQuery(event.target.value)} placeholder="사용자 ID, 공지 제목 등" /></label></div><div className={styles.row}><p className="muted">한국 시각 · 최신순 · 기록은 수정할 수 없습니다.</p><span className="badge">{entries.length}건</span></div>{entries.length ? <div className={styles.tableWrap}><table className={styles.auditTable}><thead><tr><th>시각 / 운영자</th><th>작업 / 대상</th><th>이전 → 이후</th><th>사유 또는 본문</th></tr></thead><tbody>{entries.map(item => <tr key={item.id}><td><time>{displayTime(item.at)}</time><span className={styles.cellSecondary}>{item.actor}</span></td><td><strong>{item.action}</strong><span className={styles.cellSecondary}>{item.target}</span></td><td><span className={styles.before}>{item.before || '—'}</span><span className={styles.arrow} aria-label="변경 후">→</span><span>{item.after || '—'}</span></td><td className={styles.preserve}>{item.reason || '—'}</td></tr>)}</tbody></table></div> : <Empty>선택한 조건의 운영 기록이 없습니다.</Empty>}</section></div>;
}

type ReasonCommand = Extract<AdminCommand, { reason: string }>;
interface Confirmation { title: string; target: string; description: string; button: string; command: ReasonCommand }

export function OpsScreen({ data, onCommand, navigate }: ScreenProps) {
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);
  const [showHandled, setShowHandled] = useState(false);
  const pendingApprovals = data.approvals.filter(item => item.status === '대기');
  const outbox = data.outbox.filter(item => showHandled || !item.resolution);
  return <div className={styles.stack}><header className={styles.heading}><div><p className={styles.eyebrow}>OPERATIONS</p><h1>예약 승인 · 위임 · 발송 확인</h1><p className="muted">사람의 확인이 필요한 작업을 처리합니다.</p></div><span className="badge">임시 포함</span></header><div className="notice">이번 범위에 둘지는 팀에서 정합니다. 모든 처리는 데모 상태에만 반영됩니다.</div>
    <section className={`panel ${styles.card}`}><div className={styles.row}><h2>예약 승인 대기</h2><span className="badge">{pendingApprovals.length}건</span></div><p className="muted">근거를 확인한 뒤 승인하거나 거절하세요. 두 동작 모두 사유를 남깁니다.</p>{pendingApprovals.length ? <div className={styles.tableWrap}><table><thead><tr><th>요청 / 사용자</th><th>여행 / 요청 시각</th><th>근거</th><th>처리</th></tr></thead><tbody>{pendingApprovals.map(item => <tr key={item.id}><td><strong>{item.request}</strong><button type="button" className={styles.cellLink} onClick={() => navigate(`/users/${item.userId}`)}>{item.userId} ↗</button></td><td>{item.trip}<time className={styles.cellSecondary}>{displayTime(item.at)}</time></td><td><details><summary>근거 보기</summary><p className={styles.evidence}>{item.evidence}</p></details></td><td><div className={styles.actions}>{[false, true].map(approve => <button key={String(approve)} type="button" className={approve ? 'primary' : ''} onClick={() => setConfirmation({ title: `예약 ${approve ? '승인' : '거절'}`, target: `${item.userId} · ${item.trip}`, description: `${item.request} 요청을 ${approve ? '승인' : '거절'}합니다. 근거: ${item.evidence}`, button: `${approve ? '승인' : '거절'} 확정`, command: { type: 'approval', approvalId: item.id, approve, reason: '' } })}>{approve ? '승인' : '거절'}</button>)}</div></td></tr>)}</tbody></table></div> : <Empty>승인을 기다리는 예약 요청이 없습니다.</Empty>}</section>
    <section className={`panel ${styles.card}`}><div className={styles.row}><h2>위임</h2><span className="muted">자동 실행 허용 범위</span></div><p className="muted">서버 설정이 허용한 범위 안에서만 위임합니다. 변경한 운영자와 사유를 기록합니다.</p>{data.delegations.length ? <div className={styles.tableWrap}><table><thead><tr><th>사용자</th><th>상태</th><th>맡긴 범위</th><th>처리</th></tr></thead><tbody>{data.delegations.map(item => <tr key={item.id}><td><button type="button" className={styles.textButton} onClick={() => navigate(`/users/${item.userId}`)}>{item.userId} ↗</button></td><td><span className="badge">{item.active ? '위임 중' : '없음'}</span></td><td>{item.scope}</td><td><button type="button" onClick={() => setConfirmation({ title: item.active ? '위임 거두기' : '위임 주기', target: item.userId, description: `${item.scope} 범위의 자동 실행을 ${item.active ? '중지' : '허용'}합니다.`, button: item.active ? '위임 회수 확정' : '위임 부여 확정', command: { type: 'delegation', delegationId: item.id, active: !item.active, reason: '' } })}>{item.active ? '거두기' : '주기'}</button></td></tr>)}</tbody></table></div> : <Empty>위임을 확인할 사용자가 없습니다.</Empty>}</section>
    <section className={`panel ${styles.card}`}><div className={styles.row}><h2>알림 발송 결과 미확인</h2><label className={styles.checkbox}><input type="checkbox" checked={showHandled} onChange={event => setShowHandled(event.target.checked)} /> 확인 완료 포함</label></div><p className="muted">보냈는지 알 수 없는 알림(unknown)에 확인한 결과만 기록합니다.<br />다시 보내거나 원래 발송 상태를 성공으로 바꾸지 않습니다.</p>{outbox.length ? <div className={styles.tableWrap}><table><thead><tr><th>주제 / 발송 상태</th><th>시도</th><th>마지막 오류</th><th>확인 결과</th></tr></thead><tbody>{outbox.map(item => <tr key={item.id}><td><strong>{item.topic}</strong><span className={styles.cellSecondary}>{item.status}</span></td><td>{item.attempts}회</td><td>{item.error}</td><td>{item.resolution ? <><span className="badge">{item.resolution === 'confirmed_delivered' ? '전달 확인' : '미전달 확인'}</span><span className={styles.cellSecondary}>{item.resolvedBy} · {item.note}</span></> : <div className={styles.actions}>{(['confirmed_not_delivered', 'confirmed_delivered'] as const).map(resolution => <button type="button" key={resolution} className={resolution === 'confirmed_delivered' ? 'primary' : ''} onClick={() => setConfirmation({ title: resolution === 'confirmed_delivered' ? '전달 확인' : '미전달 확인', target: item.topic, description: '외부 채널에서 확인한 결과와 근거를 남기세요. 기록 후에도 원래 발송 상태는 unknown으로 유지되며 재발송하지 않습니다.', button: '확인 결과 기록', command: { type: 'resolve-outbox', outboxId: item.id, resolution, reason: '' } })}>{resolution === 'confirmed_delivered' ? '전달 확인' : '미전달 확인'}</button>)}</div>}</td></tr>)}</tbody></table></div> : <Empty>확인이 필요한 알림이 없습니다.</Empty>}</section>
    {confirmation && <ReasonConfirmation confirmation={confirmation} onCommand={onCommand} onClose={() => setConfirmation(null)} />}
  </div>;
}

function ReasonConfirmation({ confirmation, onCommand, onClose }: { confirmation: Confirmation; onCommand: ScreenProps['onCommand']; onClose: () => void }) {
  const [reason, setReason] = useState('');
  const feedback = useCommandFeedback(onCommand);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reason.trim()) return feedback.invalid('사유 또는 확인한 근거를 입력해 주세요.');
    if (await feedback.run({ ...confirmation.command, reason }, '확인 결과를 데모에 기록했습니다.')) onClose();
  }
  return <WorkflowDialog titleId="confirmation-title" locked={feedback.pending} onClose={onClose}><span className={styles.eyebrow}>확인 후 기록</span><h2 id="confirmation-title">{confirmation.title}</h2><strong>{confirmation.target}</strong><p className={styles.preserve}>{confirmation.description}</p><form onSubmit={submit} noValidate className={styles.stack}><label>사유 · 확인 근거 (필수)<textarea rows={4} value={reason} onChange={event => setReason(event.target.value)} placeholder="확인한 사실과 판단의 이유를 적어 주세요." /></label><p className="muted">현재 로그인한 운영자 ID로 운영 기록에 남습니다.</p><Feedback {...feedback} /><div className={styles.actions}><button type="button" onClick={onClose} disabled={feedback.pending}>취소</button><button type="submit" className="primary" disabled={feedback.pending}>{feedback.pending ? '기록 중…' : confirmation.button}</button></div></form></WorkflowDialog>;
}
