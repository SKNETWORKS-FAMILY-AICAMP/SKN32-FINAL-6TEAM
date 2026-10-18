'use client';

import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { operationUsers } from '../../lib/gateway';
import { chatLimitFor, chatLimitReached, chatLimitText, chatUnlimited, formatNumber, type AdminSnapshot, type PageInfo, type ScreenProps, type UsersListState, type User } from '../../lib/model';
import styles from './users.module.css';

export const USER_PAGE_SIZE = 50;
export type UserSort = 'id' | 'status' | 'chat' | 'web' | 'trips' | 'inquiries' | 'lastUsed';
export type UserFilters = { q: string; match: 'contains' | 'exact'; status: string; quick: string; sort: UserSort; direction: 'asc' | 'desc'; page: number };
const COLUMNS: { key: UserSort; label: string }[] = [
  { key: 'id', label: '사용자 ID' }, { key: 'status', label: '상태' }, { key: 'chat', label: '② 채팅 오늘 / 한도' },
  { key: 'web', label: '③ 웹 호출' }, { key: 'trips', label: '여행' }, { key: 'inquiries', label: '문의' }, { key: 'lastUsed', label: '마지막 사용 · KST' },
];

export function UsersScreen({ data, navigate, listState, onListStateChange }: ScreenProps & { listState?: UsersListState; onListStateChange?: (state: UsersListState) => void }) {
  const [filters, setFilters] = useState<UserFilters>(() => ({ q: listState?.query ?? '', match: listState?.match ?? 'contains', status: listState?.status === '차단' ? 'blocked' : listState?.status === '정상' ? 'active' : listState?.status === '전체' ? 'all' : listState?.status ?? 'all', quick: listState?.quick === '채팅 한도 도달' ? 'limit' : listState?.quick === '문의 있음' ? 'inquiry' : listState?.quick === '전체' ? 'all' : listState?.quick ?? 'all', sort: listState?.sort ?? 'lastUsed', direction: listState?.direction ?? 'desc', page: listState?.page ?? 1 }));
  const search = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLElement>(null);
  const params = new URLSearchParams(Object.entries(filters).map(([key, value]) => [key, String(value)]));
  const live = useQuery({ queryKey: ['users', params.toString(), data.clock], queryFn: () => operationUsers(params), enabled: !!data.live });
  const result = data.live ? live.data : demoUsers(data, filters);
  function save(next: UserFilters) { setFilters(next); onListStateChange?.({ query: next.q, status: next.status, quick: next.quick, order: '마지막 사용순', match: next.match, sort: next.sort, direction: next.direction, page: next.page }); }
  function update(change: Partial<UserFilters>) { save({ ...filters, ...change, page: 1 }); }
  function sort(key: UserSort) { update({ sort: key, direction: filters.sort === key ? filters.direction === 'asc' ? 'desc' : 'asc' : key === 'id' || key === 'status' ? 'asc' : 'desc' }); }
  function changePage(page: number) { save({ ...filters, page }); list.current?.scrollIntoView({ block: 'start' }); }
  const pager = <Pagination info={result ?? { total: 0, page: 1, pageSize: USER_PAGE_SIZE, pages: 1 }} disabled={!!data.live && (live.isPending || live.isError)} noun="명" onPage={changePage} />;
  return <div className={styles.screen} onKeyDown={event => {
    if (event.key === '/' && !(event.target instanceof HTMLInputElement) && !(event.target instanceof HTMLSelectElement)) { event.preventDefault(); search.current?.focus(); }
  }}>
    <header><p className={styles.eyebrow}>OPERATIONS / USERS</p><h1>사용자</h1><p className="muted">열 제목을 눌러 정렬합니다. 한 페이지에 50명씩 표시합니다.</p></header>
    <section ref={list} className="panel" aria-label="사용자 목록">
      <div className={styles.toolbar}>
        <label className={styles.search}>사용자 ID로 찾기<input ref={search} type="search" value={filters.q} maxLength={200} placeholder="사용자 ID 전체 또는 일부" onChange={event => update({ q: event.target.value })} /></label>
        <label className={styles.exact}><input type="checkbox" checked={filters.match === 'exact'} onChange={event => update({ match: event.target.checked ? 'exact' : 'contains' })} />입력한 사용자만 보기</label>
        <details className={styles.filterPanel}><summary>필터</summary><div className={styles.filterFields}>
          <label>상태<select value={filters.status} onChange={event => update({ status: event.target.value })}><option value="all">전체</option><option value="active">정상</option><option value="blocked">차단</option></select></label>
          <label>조회 조건<select value={filters.quick} onChange={event => update({ quick: event.target.value })}><option value="all">전체</option><option value="limit">채팅 한도 도달</option><option value="inquiry">문의 있음</option></select></label>
        </div></details>
        <button type="button" onClick={() => update({ q: '', match: 'contains', status: 'all', quick: 'all' })}>필터 초기화</button>
      </div>
      <p className="muted" role="status">{result ? `조건에 맞는 사용자 ${formatNumber(result.total)}명 · ${COLUMNS.find(c => c.key === filters.sort)?.label} ${filters.direction === 'asc' ? '오름차순' : '내림차순'}` : '사용자를 불러오는 중…'}{filters.status !== 'all' && ` · ${filters.status === 'blocked' ? '차단' : '정상'}만`}{filters.quick !== 'all' && ` · ${filters.quick === 'limit' ? '채팅 한도 도달' : '문의 있음'}`}</p>
      {pager}
      <div className={styles.tableWrap} aria-busy={!!data.live && live.isPending}>
        <table><thead><tr>{COLUMNS.map(column => <th key={column.key} scope="col" aria-sort={filters.sort === column.key ? filters.direction === 'asc' ? 'ascending' : 'descending' : 'none'}><button className={styles.sort} onClick={() => sort(column.key)}>{column.label}<span aria-hidden="true">{filters.sort === column.key ? filters.direction === 'asc' ? '↑' : '↓' : '↕'}</span></button></th>)}<th scope="col">상세</th></tr></thead>
          <tbody>{data.live && live.isError ? <tr><td colSpan={8}><p className="error" role="alert">사용자를 불러오지 못했습니다. {live.error.message}</p><button onClick={() => void live.refetch()}>다시 불러오기</button></td></tr> : !result ? <tr><td colSpan={8}>사용자를 불러오는 중…</td></tr> : !result.users.length ? <tr><td colSpan={8} className={styles.empty}>조건에 맞는 사용자가 없습니다. 검색어나 필터를 바꿔 보세요.</td></tr> : result.users.map(user => <tr key={user.id}>
            <td><button className={styles.userLink} onClick={() => navigate(`/users/${encodeURIComponent(user.id)}`)}>{user.id}</button></td>
            <td><span className="badge">{user.blocked ? '차단' : '정상'}</span></td>
            <td>{formatNumber(user.chat)} / {chatLimitText(chatLimitFor(user, data))}{user.exceptionLimit !== null && <small> · 예외</small>}{!chatUnlimited(chatLimitFor(user, data)) && <meter className={styles.usageMeter} min={0} max={Math.max(1, chatLimitFor(user, data))} value={user.chat} aria-label={`${user.id} 채팅 사용량`} aria-valuetext={`${user.chat} / ${chatLimitFor(user, data)}`} />}</td>
            <td>{formatNumber(user.web)}</td><td>{user.trips.length}</td><td>{inquiryCount(user, data)}</td><td>{userTime(user.lastUsed)}</td>
            <td><button aria-label={`${user.id} 상세 보기`} onClick={() => navigate(`/users/${encodeURIComponent(user.id)}`)}>상세 →</button></td>
          </tr>)}</tbody></table>
      </div>
      {pager}
    </section>
  </div>;
}

export function Pagination({ info, onPage, noun, disabled = false }: { info: PageInfo; onPage: (page: number) => void; noun: string; disabled?: boolean }) {
  return <nav className={styles.pagination} aria-label={noun === '명' ? '사용자 페이지' : '대화 구간'}>
    <span role="status">{info.total ? `${formatNumber((info.page - 1) * info.pageSize + 1)}–${formatNumber(Math.min(info.page * info.pageSize, info.total))}${noun} / 총 ${formatNumber(info.total)}${noun}` : `0${noun}`}</span>
    <div><button disabled={disabled || info.page <= 1} onClick={() => onPage(1)}>처음</button><button disabled={disabled || info.page <= 1} onClick={() => onPage(info.page - 1)}>이전</button>
      <label>{noun === '명' ? '페이지' : '구간'}<input key={`${info.page}:${info.pages}`} type="number" min={1} max={info.pages} defaultValue={info.page} disabled={disabled} aria-label={noun === '명' ? '이동할 페이지' : '이동할 대화 구간'} onKeyDown={event => {
        if (event.key === 'Enter') { const page = Number(event.currentTarget.value); if (Number.isInteger(page) && page >= 1 && page <= info.pages) onPage(page); }
      }} onBlur={event => { const page = Number(event.target.value); if (Number.isInteger(page) && page >= 1 && page <= info.pages) onPage(page); else event.target.value = String(info.page); }} /> / {formatNumber(info.pages)}</label>
      <button disabled={disabled || info.page >= info.pages} onClick={() => onPage(info.page + 1)}>다음</button><button disabled={disabled || info.page >= info.pages} onClick={() => onPage(info.pages)}>{noun === '명' ? '마지막' : '최신'}</button></div>
  </nav>;
}

export function demoUsers(data: AdminSnapshot, filters: UserFilters) {
  const q = filters.q.trim().toLowerCase();
  const users = data.users.filter(user => (filters.match === 'exact' ? user.id.toLowerCase() === q : user.id.toLowerCase().includes(q)) &&
    (filters.status === 'all' || user.blocked === (filters.status === 'blocked')) &&
    (filters.quick !== 'limit' || chatLimitReached(user, data)) && (filters.quick !== 'inquiry' || inquiryCount(user, data) > 0));
  users.sort((a, b) => {
    const av = sortValue(a, filters.sort, data), bv = sortValue(b, filters.sort, data);
    if (av === null || bv === null) return av === bv ? a.id.localeCompare(b.id) : av === null ? 1 : -1;
    const delta = typeof av === 'string' && typeof bv === 'string' ? av.localeCompare(bv) : Number(av) - Number(bv);
    return (filters.direction === 'asc' ? delta : -delta) || a.id.localeCompare(b.id);
  });
  const pages = Math.max(1, Math.ceil(users.length / USER_PAGE_SIZE)), page = Math.min(filters.page, pages);
  return { users: users.slice((page - 1) * USER_PAGE_SIZE, page * USER_PAGE_SIZE), total: users.length, page, pages, pageSize: USER_PAGE_SIZE };
}

function sortValue(user: User, key: UserSort, data: AdminSnapshot): string | number | null {
  if (key === 'status') return Number(user.blocked);
  if (key === 'trips') return user.trips.length;
  if (key === 'inquiries') return inquiryCount(user, data);
  if (key === 'lastUsed') { const at = parseTime(user.lastUsed); return Number.isFinite(at.getTime()) ? at.getTime() : null; }
  return user[key];
}
function inquiryCount(user: User, data: AdminSnapshot) { return user.inquiryCount ?? data.inquiries.filter(item => item.userId === user.id).length; }
function parseTime(at: string) { return new Date(/(?:[zZ]|[+-]\d{2}:\d{2})$/.test(at) ? at : `${at.replace(' ', 'T')}+09:00`); }
export function userTime(at: string) { const date = parseTime(at); return Number.isFinite(date.getTime()) ? date.toLocaleString('ko-KR', { timeZone: 'Asia/Seoul', dateStyle: 'short', timeStyle: 'short' }) : '사용 기록 없음'; }
