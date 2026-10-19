'use client';

import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { useInfiniteQuery, useQuery, useQueryClient } from '@tanstack/react-query';
import { operationTripDetail } from '../../lib/gateway';
import styles from './trip-detail.module.css';

type Tab = 'chat' | 'draft' | 'initial' | 'current';
type Props = { userId: string; tripId: string; live: boolean; navigate: (path: string) => void };
type Trip = { trip_id: string; customer_id: string; title: string; status: string; locale: string | null; party_size: number | null; latest_version: number; created_at: string };
type Turn = { turn_id: string; role: 'customer' | 'assistant'; text: string; at: string; case_id: string | null };
type ChatPage = { turns: Turn[]; next_after: string | null };
type Item = { item_id: string; seq: number; kind: string; title: string; starts_at: string; ends_at: string | null; locked: boolean; place_name: string | null; address: string | null; detail: Record<string, string | number> };
type Plan = { version: number; reason: string; created_at: string; items: Item[] };
type Draft = { intake_id: string; received_at: string; sources: { source_id: string; position: number; kind: string; filename: string | null; text: string | null; transcribed: boolean }[] };
const tabs: { id: Tab; label: string }[] = [{ id: 'chat', label: '대화 내역' }, { id: 'draft', label: '초안 원문' }, { id: 'initial', label: '처음 여행계획' }, { id: 'current', label: '현재 여행계획' }];
const statusLabel: Record<string, string> = { active: '진행 중', completed: '여행 종료', cancelled: '취소됨', paused: '일시 정지' };
const kindLabel: Record<string, string> = { activity: '활동', dining: '식사', mobility: '이동', lodging: '숙박', flight: '항공' };
const reasonLabel: Record<string, string> = { created: '처음 등록', auto_adjusted: '자동 조정', customer_request: '고객 요청', rollback: '이전 계획으로 되돌림' };
const stamp = (value: string) => new Date(value).toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', dateStyle: 'medium', timeStyle: 'short', hour12: false });
const day = (value: string) => new Intl.DateTimeFormat('sv-SE', { timeZone: 'Asia/Seoul', dateStyle: 'short' }).format(new Date(value));
const time = (value: string) => new Date(value).toLocaleTimeString('ko-KR', { timeZone: 'Asia/Seoul', hour: '2-digit', minute: '2-digit', hour12: false });
const queryKey = (props: Pick<Props, 'userId' | 'tripId'>) => ['admin', 'trip-detail', props.userId, props.tripId];

function ReadError({ error, retry }: { error: Error; retry: () => void }) {
  return <div role="alert" className="error"><p>{error.message}</p><button type="button" onClick={retry}>다시 읽기</button></div>;
}

function LoadingState({ label }: { label: string }) {
  const [stage, setStage] = useState(0);
  useEffect(() => {
    const brief = setTimeout(() => setStage(1), 100);
    const slow = setTimeout(() => setStage(2), 1000);
    return () => { clearTimeout(brief); clearTimeout(slow); };
  }, []);
  return <div role="status" aria-live="polite">{stage > 0 && <p>{label}</p>}{stage > 1 && <div className={styles.skeleton} aria-hidden="true"><span /><span /><span /></div>}</div>;
}

export function TripDetailScreen(props: Props) {
  const { userId, tripId, live, navigate } = props;
  const [tab, setTab] = useState<Tab>('chat');
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const client = useQueryClient();
  const query = useQuery({ queryKey: [...queryKey(props), 'summary'], queryFn: ({ signal }) => operationTripDetail<{ trip: Trip; as_of: string }>(userId, tripId, '', signal), enabled: live, staleTime: 0 });
  function moveTab(event: KeyboardEvent, index: number) {
    const target = event.key === 'ArrowRight' ? (index + 1) % tabs.length : event.key === 'ArrowLeft' ? (index + tabs.length - 1) % tabs.length : event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : null;
    if (target === null) return;
    event.preventDefault(); setTab(tabs[target].id); buttons.current[target]?.focus();
  }
  const trip = query.data?.trip;
  return <div className={styles.page}>
    <nav aria-label="여행 위치" className={styles.breadcrumb}><button onClick={() => navigate('/users')}>사용자 목록</button><span aria-hidden="true">›</span><button onClick={() => navigate(`/users/${encodeURIComponent(userId)}`)}>사용자 상세</button><span aria-hidden="true">›</span><span>여행 상세</span></nav>
    <header className={styles.heading}><div><h1>{trip?.title || '여행 상세'}</h1>{trip && <><p><span className="badge">{statusLabel[trip.status] || trip.status}</span> · {trip.party_size === null ? '인원 미기록' : `${trip.party_size}명`} · 현재 {trip.latest_version}판</p><p className="muted">등록 {stamp(trip.created_at)} · 한국 시각</p></>}</div>{trip && <button disabled={query.isFetching} onClick={() => void client.invalidateQueries({ queryKey: queryKey(props) })}>기록 새로 읽기</button>}</header>
    {!live ? <section className="panel"><h2>저장된 여행 기록</h2><p>데모 여행에는 저장된 대화·계획이 없습니다. 실제 운영 자료에서 여행을 선택하면 확인할 수 있습니다.</p></section> : query.isPending ? <section className="panel"><LoadingState label="여행 정보를 읽는 중…" /></section> : query.isError ? <ReadError error={query.error} retry={() => void query.refetch()} /> : <>
      <dl className={styles.identities}><div><dt>사용자 ID</dt><dd>{userId}</dd></div><div><dt>여행 ID</dt><dd>{tripId}</dd></div></dl>
      <div role="tablist" aria-label="여행 기록" className={styles.tabs}>{tabs.map((item, index) => <button key={item.id} id={`trip-tab-${item.id}`} ref={node => { buttons.current[index] = node; }} role="tab" aria-selected={tab === item.id} aria-controls={`trip-panel-${item.id}`} tabIndex={tab === item.id ? 0 : -1} onKeyDown={event => moveTab(event, index)} onClick={() => setTab(item.id)}>{item.label}</button>)}</div>
      <section role="tabpanel" id={`trip-panel-${tab}`} aria-labelledby={`trip-tab-${tab}`} tabIndex={0} className={`panel ${styles.body}`}>
        {tab === 'chat' ? <ChatHistory {...props} /> : tab === 'draft' ? <DraftHistory {...props} /> : <PlanHistory key={tab} {...props} view={tab} />}
      </section>
    </>}
  </div>;
}

function DraftHistory(props: Props) {
  const query = useQuery({ queryKey: [...queryKey(props), 'draft'], queryFn: ({ signal }) => operationTripDetail<{ draft: Draft | null; as_of: string }>(props.userId, props.tripId, '/draft', signal), staleTime: 0 });
  const draft = query.data?.draft;
  return <><div className={styles.sectionHeading}><h2>고객이 입력한 여행 초안 원문</h2><button disabled={query.isFetching} onClick={() => void query.refetch()}>원문 다시 읽기</button></div>
    <p className="muted">이 여행을 처음 등록할 때 입력한 글과 첨부에서 읽은 글입니다. 저장된 문구와 줄바꿈을 표시하며, 개인정보는 가립니다. 등록 후 정리된 일정은 처음 여행계획에서 확인할 수 있습니다.</p>
    {query.isPending ? <LoadingState label="초안 원문을 읽는 중…" /> : query.isError ? <ReadError error={query.error} retry={() => void query.refetch()} /> : !draft || !draft.sources.length ? <p className={styles.empty}>이 여행에 보관된 입력 원문이 없습니다. 입력 없이 만든 여행이나 원문이 보관되지 않은 여행은 처음 여행계획에서 등록된 일정을 확인해 주세요.</p> : <>
      <p className="muted">접수 {stamp(draft.received_at)} · 원문 {draft.sources.length}개 · 한국 시각</p>
      {draft.sources.map((source, index) => <section className={styles.source} key={source.source_id}><h3>{index + 1}. {source.filename || '입력한 글'}</h3><p className="muted">{source.transcribed ? '사진·스캔에서 받아쓴 글' : ['chat', 'text'].includes(source.kind) ? '입력한 텍스트' : '첨부 파일에서 추출한 글'}</p>{source.text ? <pre className={styles.original}>{source.text}</pre> : <p className={styles.empty}>이 원본에서 읽은 글이 보관되어 있지 않습니다.</p>}</section>)}
      <p className="muted">조회 {stamp(query.data!.as_of)} · 이후 변경은 다시 읽기로 확인할 수 있습니다.</p>
    </>}
  </>;
}

function ChatHistory(props: Props) {
  const query = useInfiniteQuery({ queryKey: [...queryKey(props), 'chat'], initialPageParam: '0', queryFn: ({ pageParam, signal }) => operationTripDetail<ChatPage>(props.userId, props.tripId, `/chat?after=${pageParam}&limit=100`, signal), getNextPageParam: page => page.next_after ?? undefined, staleTime: 0 });
  const turns = query.data?.pages.flatMap(page => page.turns) || [];
  return <><div className={styles.sectionHeading}><h2>대화 내역</h2><span className="muted">한국 시각</span></div>
    <p className="muted">이 여행에서 저장된 고객·구구루트 대화입니다. 오래된 순서로 표시하며, 보관 기간이 지난 기록이나 외부 AI에서만 나눈 대화는 포함하지 않습니다.</p>
    {query.isPending ? <LoadingState label="대화를 읽는 중…" /> : query.isError && !turns.length ? <ReadError error={query.error} retry={() => void query.refetch()} /> : <>
      {!turns.length ? <p className={styles.empty}>이 여행에 저장된 대화 내역이 없습니다.</p> : <><p className="muted" role="status">대화 {turns.length.toLocaleString('ko-KR')}개 표시{query.hasNextPage ? ' · 뒤에 기록이 더 있습니다.' : ' · 저장된 기록을 모두 불러왔습니다.'}</p><ol className={styles.conversation}>{turns.map(turn => <li key={turn.turn_id} className={turn.role === 'customer' ? styles.customer : styles.assistant}><div className={styles.turnMeta}><strong>{turn.role === 'customer' ? '고객' : '구구루트'}</strong><time dateTime={turn.at}>{stamp(turn.at)}</time></div><p className={styles.message}>{turn.text}</p>{turn.case_id && <button className={styles.caseLink} onClick={() => props.navigate(`/cases/${turn.case_id}`)}>연결된 접수·처리 근거 보기 →</button>}</li>)}</ol></>}
      {query.isFetchNextPageError && <ReadError error={query.error} retry={() => void query.fetchNextPage()} />}
      {query.isRefetchError && <ReadError error={query.error} retry={() => void query.refetch()} />}
      {query.hasNextPage && <button className={styles.more} disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? '대화를 더 읽는 중…' : '다음 대화 더 보기'}</button>}
    </>}
  </>;
}

function PlanHistory(props: Props & { view: 'initial' | 'current' }) {
  const { view } = props;
  const query = useQuery({ queryKey: [...queryKey(props), 'plan', view], queryFn: ({ signal }) => operationTripDetail<{ plan: Plan | null; as_of: string }>(props.userId, props.tripId, `/plans/${view}`, signal), staleTime: 0 });
  const plan = query.data?.plan;
  const groups = new Map<string, Item[]>();
  for (const item of plan?.items || []) { const key = day(item.starts_at); groups.set(key, [...(groups.get(key) || []), item]); }
  return <><div className={styles.sectionHeading}><h2>{view === 'initial' ? '처음 여행계획' : '현재 여행계획'}</h2><button disabled={query.isFetching} onClick={() => void query.refetch()}>계획 다시 읽기</button></div>
    <p className="muted">{view === 'initial' ? '처음 등록했을 때 저장된 1판입니다. 이후 변경 전의 계획을 확인할 수 있습니다.' : '최근 저장된 계획입니다. 첫 계획과 판 번호가 같으면 등록 후 변경되지 않은 계획입니다.'}</p>
    {query.isPending ? <LoadingState label="여행계획을 읽는 중…" /> : query.isError ? <ReadError error={query.error} retry={() => void query.refetch()} /> : !plan ? <p className={styles.empty}>{view === 'initial' ? '처음 여행계획(1판)이 보관되어 있지 않습니다.' : '현재 여행계획이 보관되어 있지 않습니다.'}</p> : <>
      <p className={styles.planMeta}><strong>{plan.version}판 · {reasonLabel[plan.reason] || plan.reason}</strong><span>저장 {stamp(plan.created_at)}</span><span>일정 {plan.items.length}개 · 한국 시각</span></p>
      {!plan.items.length ? <p className={styles.empty}>이 판에 저장된 일정 항목이 없습니다.</p> : [...groups].map(([date, items]) => <section key={date} className={styles.day}><h3>{date}</h3><ol className={styles.itinerary}>{items.map(item => <li key={item.item_id}><div className={styles.scheduleTime}><time dateTime={item.starts_at}>{time(item.starts_at)}</time>{item.ends_at && <span>– {day(item.ends_at) !== date ? `${day(item.ends_at)} ` : ''}{time(item.ends_at)}</span>}</div><div className={styles.itemBody}><div className={styles.itemTitle}><span className="badge">{kindLabel[item.kind] || item.kind}</span><h4>{item.title}</h4>{item.locked && <span className="badge">고정 일정</span>}</div>{item.place_name && <p>{item.place_name}</p>}{item.address && <p className="muted">{item.address}</p>}{Object.entries(item.detail).map(([key, value]) => <p className="muted" key={key}>{({ mode: '이동 수단', travel_minutes: '이동 시간(분)', price_krw: '비용(원)', route_text: '이동 경로' } as Record<string, string>)[key]}: {value}</p>)}</div></li>)}</ol></section>)}
      <p className="muted">조회 {stamp(query.data!.as_of)} · 이후 변경은 다시 읽기로 확인할 수 있습니다.</p>
    </>}
  </>;
}
