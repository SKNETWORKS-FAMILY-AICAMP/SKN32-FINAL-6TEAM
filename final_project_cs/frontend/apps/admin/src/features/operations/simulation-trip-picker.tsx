'use client';

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { operationSimulations } from '../../lib/gateway';
import styles from './simulation.module.css';

export type Categories = { key: string; label: string }[];
export type Audience = 'monitored' | 'guest';
type Trip = { trip_id: string; title: string; starts_at?: string | null; ends_at?: string | null; can_simulate?: boolean; paused?: boolean };
type Catalogue = { trips: Trip[]; categories: Categories; total: number; page: number; total_pages: number };
const day = (value: string) => new Intl.DateTimeFormat('ko-KR', { timeZone: 'Asia/Seoul', month: 'numeric', day: 'numeric' }).format(new Date(value));

function tripLabel(trip: Trip) {
  const period = trip.starts_at && trip.ends_at ? ` · ${day(trip.starts_at)}~${day(trip.ends_at)}` : '';
  const status = trip.paused ? ' · 재난 정지 중' : trip.can_simulate === false ? ' · 조회만 가능' : '';
  return `${trip.title}${period} · ${trip.trip_id.slice(0, 8)}${status}`;
}

export function SimulationTripPicker({ audience, selectedId, onSelect, onClear }: {
  audience: Audience; selectedId: string; onSelect: (id: string, categories: Categories) => void; onClear: () => void;
}) {
  const guest = audience === 'guest';
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const [dateError, setDateError] = useState('');
  const invalidRange = Boolean(dateFrom && dateTo && dateFrom > dateTo);
  const catalogue = useQuery({
    queryKey: ['simulation-catalogue', audience, dateFrom, dateTo, page], enabled: !invalidRange,
    queryFn: () => {
      const query = new URLSearchParams({ audience, page: String(page), page_size: '10' });
      if (dateFrom) query.set('date_from', dateFrom);
      if (dateTo) query.set('date_to', dateTo);
      return operationSimulations<Catalogue>(undefined, query);
    },
  });
  const changeDate = (value: string, from: boolean) => {
    if (from) setDateFrom(value); else setDateTo(value);
    setDateError(''); setPage(1); onClear();
  };
  const validateDates = () => setDateError(invalidRange ? '조회 시작일을 종료일 이전으로 골라 주세요.' : '');
  const changePage = (value: number) => { setPage(value); onClear(); };
  const refresh = async () => {
    const result = await catalogue.refetch();
    if (selectedId && !result.data?.trips.some(trip => trip.trip_id === selectedId)) onClear();
    // 마지막 페이지의 여행이 삭제되면 첫 페이지로 돌아가 새 목록을 읽는다.
    if (result.data && !result.data.trips.length && page > 1) changePage(1);
  };
  return <fieldset className={styles.tripPicker}>
    <legend>{guest ? '게스트 여행' : '감시 대상 여행'}</legend>
    {guest && <>
      <p id="guest-trip-help">로그인 없이 만든 여행도 따로 조회합니다. 날짜는 여행 기간 기준이며, 끝난 여행은 조회만 가능합니다.</p>
      <div className={styles.dateFilters}>
        <label>게스트 조회 시작일 (선택)<input type="date" value={dateFrom} onChange={e => changeDate(e.target.value, true)} onFocus={() => setDateError('')} onBlur={validateDates} aria-invalid={!!dateError} aria-describedby={dateError ? 'guest-date-error' : 'guest-trip-help'} /></label>
        <label>게스트 조회 종료일 (선택)<input type="date" value={dateTo} onChange={e => changeDate(e.target.value, false)} onFocus={() => setDateError('')} onBlur={validateDates} aria-invalid={!!dateError} aria-describedby={dateError ? 'guest-date-error' : 'guest-trip-help'} /></label>
      </div>
      <button type="button" onClick={() => { setDateFrom(''); setDateTo(''); setDateError(''); setPage(1); onClear(); }}>날짜 조건 지우기</button>
      {dateError && <p id="guest-date-error" role="alert" className="error">{dateError}</p>}
    </>}
    {invalidRange ? <p role="status">시작일과 종료일을 확인하면 여행 목록을 다시 읽습니다.</p> : catalogue.isPending ? <p role="status">시험할 여행을 읽는 중…</p> : catalogue.isError ? <div role="alert"><p className="error">{catalogue.error.message}</p><button type="button" onClick={() => void catalogue.refetch()}>여행 다시 읽기</button></div> : <>
      <label>{guest ? '게스트 여행 선택' : '대상 여행'}<select value={selectedId} onChange={e => onSelect(e.target.value, catalogue.data.categories)}>
        <option value="">여행 선택</option>{catalogue.data.trips.map(trip => <option key={trip.trip_id} value={trip.trip_id}>{tripLabel(trip)}</option>)}
      </select></label>
      {!catalogue.data.trips.length && <p>{guest ? '조회 조건에 맞는 게스트 여행이 없습니다. 날짜 조건을 지워 다시 확인해 주세요.' : '시험할 감시 대상 여행이 없습니다. 게스트 여행은 아래에서 따로 골라 주세요.'}</p>}
      <nav className={styles.pagination} aria-label={guest ? '게스트 여행 페이지' : '감시 대상 여행 페이지'}>
        <button type="button" disabled={page <= 1 || catalogue.isFetching} onClick={() => changePage(page - 1)}>이전 페이지</button>
        <span role="status">{catalogue.data.total ?? catalogue.data.trips.length}개 · {page}/{Math.max(1, catalogue.data.total_pages ?? 1)}페이지</span>
        <button type="button" disabled={page >= (catalogue.data.total_pages ?? 1) || catalogue.isFetching} onClick={() => changePage(page + 1)}>다음 페이지</button>
      </nav>
      <button type="button" onClick={() => void refresh()}>{guest ? '게스트 여행 목록 새로 읽기' : '여행 목록 새로 읽기'}</button>
    </>}
  </fieldset>;
}
