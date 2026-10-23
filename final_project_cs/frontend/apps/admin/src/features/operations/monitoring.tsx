'use client';

import { useState } from 'react';
import { useInfiniteQuery } from '@tanstack/react-query';
import { operationWatchRuns } from '../../lib/gateway';
import styles from './monitoring.module.css';
import { MonitoringApiLimits } from './api-limits';

type Run = { run_id:string; started_at:string; finished_at:string|null; forced:boolean; status:string; counts:Record<string,number>; error_type:string|null; duration_seconds:number|null };
type Listing = { as_of:string; interval_seconds:number; last_gate_at:string|null; next_expected_at:string|null; freshness:string; latest:Run|null; latest_scheduled:Run|null; trips:{trip_id:string;title:string}[]; runs:Run[]; next_cursor:string|null };
type Check = { category:string; status:string; source?:string; mode?:string; reason?:string; value?:unknown; confirmed_at?:string };
type Event = { check_id:number; at:string; stage:string; trip_title:string|null; target_title:string|null; report:{ verdict?:string; action?:string; checks?:Check[]; advisories?:unknown[]; disruptions?:unknown[]; reason?:string; case_id?:string; pause_id?:string; [key:string]:unknown } };
type Detail = { run:Run; events:Event[]; next_after:number|null };
const LABELS:Record<string,string> = { running:'실행 중',completed:'완료',attention:'확인 필요',failed:'실행 실패',delayed:'지연·중단 여부 확인 필요',not_recorded:'회차 기록 없음',clear:'이상 없음',disrupted:'문제 감지',fatal:'조회 실패',skipped:'점검 제외',unchecked:'확인 못 함',held:'출발 보류',sent:'안내 처리',ok:'조회 성공',not_applicable:'해당 없음',not_connected:'미연결',forecast:'날씨 예보',weather_warning:'기상 특보',disaster_msg:'재난문자',traffic_control:'교통 통제',air_quality:'대기질',earthquake:'지진',safety:'재난 안전 확인',schedule:'방문 일정 점검',mobility:'이동 경로 점검',departure:'출발 재확인',safety_action:'안전 후속 처리',schedule_action:'일정 후속 처리',opened:'새 접수·정지 생성',existing:'기존 접수 유지',ran:'접수 처리 결과',failed_action:'처리 실패',notified:'앱 알림 생성',fatal_action:'조회 실패',unchecked_action:'확인 못 한 대상',expired:'제안 만료',retried:'다시 처리',relaxed:'조건 완화 제안',pinned:'변경 고정 일정 확인',unhandled:'처리 대상 밖',reminded:'안전 재안내',released:'해제 안내',asked:'다시 시작 안내',no_place:'장소 정보 없음',no_reference_place:'기준 장소 없음',trip_already_paused:'여행 전체 정지 중',route_or_source_missing:'경로 또는 조회 소스 없음' };
const COUNT_LABELS:Record<string,string> = { checked:'일정 점검',opened:'접수 생성',existing:'기존 접수',ran:'접수 처리',escalated:'접수 확인 필요',fatal:'일정 조회 실패',unhandled:'처리 대상 밖',pinned:'변경 고정 일정',unchecked:'확인 못 한 경로',safety_trips:'안전 대상 여행',safety_checked:'안전 점검',safety_opened:'안전정지 생성',safety_already:'기존 안전정지',safety_fatal:'안전 조회 실패',safety_errored:'안전 처리 오류',safety_no_place:'기준 장소 없음',safety_upcoming:'시작 전 여행',safety_reminded:'안전 재안내',safety_released:'해제 안내',safety_asked:'다시 시작 안내' };
const label=(value:string)=>value==='simulation_full'?'시뮬레이션 전체 점검':LABELS[value]||value;
const time=(value:string|null)=>value?new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',dateStyle:'short',timeStyle:'medium'}).format(new Date(value)):'기록 없음';
const fieldTime=(value:Date)=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false}).format(value).replace(' ','T');
const initial=()=>({since:fieldTime(new Date(Date.now()-86400000)),until:'',status:'',trip_id:''});

export function WatchMonitoring(){
  const [draft,setDraft]=useState(initial);
  const [filter,setFilter]=useState(initial);
  const [error,setError]=useState('');
  const [selected,setSelected]=useState('');
  const query=useInfiniteQuery({queryKey:['watch-runs',filter],initialPageParam:'',queryFn:({pageParam})=>{
    const params=new URLSearchParams({since:new Date(`${filter.since}+09:00`).toISOString()});
    if(filter.until)params.set('until',new Date(`${filter.until}+09:00`).toISOString());
    if(filter.status)params.set('status',filter.status);
    if(filter.trip_id)params.set('trip_id',filter.trip_id);
    if(pageParam)params.set('cursor',pageParam);
    return operationWatchRuns<Listing>(`?${params}`);
  },getNextPageParam:last=>last.next_cursor||undefined,refetchInterval:10000});
  const first=query.data?.pages[0];
  const rows=query.data?.pages.flatMap(p=>p.runs)||[];
  return <section className={`panel ${styles.page}`}><h1>감시 현황·로그</h1>
    <p>3분 주기 감시가 확인한 여행·일정과 결과를 봅니다. 이 화면은 10초마다 저장된 기록만 읽으며 외부 재난 정보를 새로 호출하지 않습니다.</p>
    <p>재난 안전 확인은 여행별 재난문자·지진을, 방문 일정 점검은 앞으로 90분 안에 시작할 항목의 6종 정보를 확인합니다. 이동 항목은 경로 사건과 필요한 출발 재확인을 기록합니다.</p>
    {first&&<div className={styles.current} aria-label="현재 감시 상태"><strong>{label(first.freshness)}</strong><p>설정 주기 {first.interval_seconds/60}분 · 최근 주기 시작 {time(first.latest_scheduled?.started_at||null)} · 최근 주기 종료 {time(first.latest_scheduled?.finished_at||null)}</p>
      <p>다음 예정 {time(first.next_expected_at)} · 조회 시각 {time(first.as_of)}</p><small>예정 시각은 실행 보장이 아닙니다. 최근 시작이 주기의 두 배보다 오래되면 지연 여부 확인이 필요합니다. 수동 실행은 별도로 표시합니다.</small>
      {first.latest&&<><Counts run={first.latest}/><button onClick={()=>setSelected(first.latest!.run_id)}>최근 회차 상세 보기</button></>}
      {!first.latest_scheduled&&<p>아직 주기 실행 기록이 없습니다. 기록 기능 적용 후 실제 감시가 실행되면 나타납니다. 기존 감시의 마지막 실행 시도: {time(first.last_gate_at)}</p>}
    </div>}
    <MonitoringApiLimits />
    <form className={styles.filters} noValidate onSubmit={event=>{event.preventDefault();const a=Date.parse(`${draft.since}+09:00`),b=draft.until?Date.parse(`${draft.until}+09:00`):Date.now();if(!Number.isFinite(a)||!Number.isFinite(b)||a>=b){setError('조회 시작과 끝 시각을 확인해 주세요. 시작은 끝보다 빨라야 합니다.');return;}setError('');setFilter({...draft});}}>
      <label>조회 시작 (한국 시각)<input type="datetime-local" value={draft.since} onChange={e=>{setDraft({...draft,since:e.target.value});setError('');}}/></label>
      <label>조회 끝 (비우면 현재)<input type="datetime-local" value={draft.until} onChange={e=>{setDraft({...draft,until:e.target.value});setError('');}}/></label>
      <label>회차 상태<select value={draft.status} onChange={e=>setDraft({...draft,status:e.target.value})}><option value="">전체</option>{['running','completed','attention','failed'].map(v=><option key={v} value={v}>{label(v)}</option>)}</select></label>
      <label>여행<select value={draft.trip_id} onChange={e=>setDraft({...draft,trip_id:e.target.value})}><option value="">전체 여행</option>{first?.trips.map(t=><option key={t.trip_id} value={t.trip_id}>{t.title} · {t.trip_id.slice(0,8)}</option>)}</select></label>
      <button type="submit">기간·조건 조회</button><button type="button" onClick={()=>void query.refetch()}>기록 새로 읽기</button>
      {error&&<p role="alert" className="error">{error}</p>}
    </form>
    {query.isError&&<div role="alert"><p className="error">{query.error.message}</p><button onClick={()=>void query.refetch()}>기록 다시 읽기</button></div>}
    <h2>회차 이력</h2><p>회차 완료는 감시 처리가 끝났다는 뜻입니다. 고객 알림의 실제 배달 성공과는 별개입니다.</p>
    <div className={styles.table} tabIndex={0} aria-label="감시 회차 표"><table><thead><tr><th>시작 · 한국 시각</th><th>실행 방식</th><th>결과</th><th>소요</th><th>상세</th></tr></thead><tbody>
      {rows.map(run=><tr key={run.run_id}><td>{time(run.started_at)}</td><td>{run.forced?'수동':'주기'}</td><td>{label(run.status)}</td><td>{run.duration_seconds===null?'진행 중':`${run.duration_seconds.toFixed(1)}초`}</td><td><button aria-label={`${time(run.started_at)} 회차 보기`} aria-pressed={selected===run.run_id} onClick={()=>setSelected(run.run_id)}>회차 보기</button></td></tr>)}
      {!rows.length&&<tr><td colSpan={5}>{query.isPending?'회차 기록을 읽는 중…':query.isError?'기록을 읽지 못했습니다. 다시 읽기를 눌러 주세요.':'이 조건에 해당하는 회차 기록이 없습니다. 기간·상태·여행 조건을 바꿔 조회해 주세요.'}</td></tr>}
    </tbody></table></div>
    {query.hasNextPage&&<button onClick={()=>void query.fetchNextPage()}>{query.isFetchingNextPage?'이전 회차 읽는 중…':'이전 회차 더 보기'}</button>}
    {selected&&<RunDetail key={selected} runId={selected}/>}
  </section>;
}

function Counts({run}:{run:Run}){return <dl className={styles.counts}>{Object.entries(run.counts).map(([key,value])=><div key={key}><dt>{COUNT_LABELS[key]||key}</dt><dd>{value}건</dd></div>)}</dl>;}

function RunDetail({runId}:{runId:string}){
  const query=useInfiniteQuery({queryKey:['watch-run-detail',runId],initialPageParam:0,queryFn:({pageParam})=>operationWatchRuns<Detail>(`/${encodeURIComponent(runId)}?after=${pageParam}`),getNextPageParam:last=>last.next_after??undefined,refetchInterval:10000});
  const run=query.data?.pages[0].run;
  const events=query.data?.pages.flatMap(p=>p.events)||[];
  return <section className={styles.detail} aria-label="선택한 감시 회차"><h2>선택한 회차 상세</h2>
    {query.isPending?<p role="status">점검 기록을 읽는 중…</p>:query.isError?<div role="alert"><p className="error">{query.error.message}</p><button onClick={()=>void query.refetch()}>회차 다시 읽기</button></div>:run&&<>
      <p>{time(run.started_at)} 시작 · {time(run.finished_at)} 종료 · {label(run.status)}{run.forced?' · 수동 실행':''}</p><Counts run={run}/>
      {run.error_type&&<p className="error">실행 오류 종류: {run.error_type}. 이 회차의 앞선 기록을 확인해 주세요.</p>}
      <p>조회 결과에는 캐시가 포함될 수 있습니다. 아래 점검 수는 외부 API 신규 호출 횟수가 아닙니다. 시험 입력은 별도로 표시합니다.</p>
      {!events.length&&<p>{run.status==='running'?'아직 저장된 항목 결과가 없습니다. 실행 중인 결과를 기다립니다.':'이 회차에 저장된 항목 결과가 없습니다. 점검 대상이 없었는지 회차 집계를 확인해 주세요.'}</p>}
      {events.map(event=><article key={event.check_id} className={styles.event}><h3>{label(event.stage)} · {event.trip_title||'여행 정보 미기록'}{event.target_title?` / ${event.target_title}`:''}</h3>
        <p>{time(event.at)} · {event.report.verdict?label(event.report.verdict):label(event.report.action==='failed'?'failed_action':event.report.action==='fatal'?'fatal_action':event.report.action==='unchecked'?'unchecked_action':event.report.action||'결과 기록')}{event.report.reason?` · ${label(event.report.reason)}`:''}</p>
        {!!event.report.advisories?.length&&<p>주의사항 {event.report.advisories.length}건 — 예보 주의는 확정 재난과 구분합니다.</p>}
        {!!event.report.disruptions?.length&&<p>문제 원인 {event.report.disruptions.length}건</p>}
        {!!event.report.checks?.length&&<ul className={styles.checks}>{event.report.checks.map((check,i)=><li key={`${check.category}-${i}`}><strong>{label(check.category)} · {check.status==='failed'?'조회 실패':label(check.status)}</strong>{check.mode==='simulation'&&<b> [시뮬레이션]</b>}<span>{check.source||check.reason||'출처 미기록'}</span><CheckValues value={check.value}/></li>)}</ul>}
        {event.report.case_id&&<p>접수 번호: {event.report.case_id}</p>}
        <details><summary>저장된 상세 결과 펼치기</summary><pre>{JSON.stringify(event.report,null,2)}</pre></details>
      </article>)}
      {query.hasNextPage&&<button onClick={()=>void query.fetchNextPage()}>{query.isFetchingNextPage?'항목 기록 읽는 중…':'이 회차의 다음 항목 기록 보기'}</button>}
    </>}
  </section>;
}

function CheckValues({value}:{value:unknown}){
  const fields:Record<string,[string,string]>={precipitation_probability:['강수확률','%'],wind_speed_kmh:['풍속','km/h'],temperature:['기온','℃'],magnitude:['규모',''],distance_km:['거리','km'],pm10:['미세먼지','㎍/㎥'],pm25:['초미세먼지','㎍/㎥']};
  if(!value||typeof value!=='object'||Array.isArray(value))return null;
  return <>{Object.entries(value).filter(([key,v])=>fields[key]&&typeof v==='number').map(([key,v])=><p key={key}>{fields[key][0]} {String(v)}{fields[key][1]}</p>)}</>;
}
