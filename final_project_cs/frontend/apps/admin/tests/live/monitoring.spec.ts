import {test,expect} from '@playwright/test';
import {createDemoSnapshot} from '../../src/lib/demo/fixtures';
const run={run_id:'run-1',started_at:'2026-10-09T10:00:00+09:00',finished_at:'2026-10-09T10:00:08+09:00',forced:false,status:'attention',counts:{checked:1,opened:0,fatal:1,safety_checked:1},error_type:null,duration_seconds:8};
const listing={as_of:'2026-10-09T10:01:00+09:00',interval_seconds:180,last_gate_at:run.started_at,next_expected_at:'2026-10-09T10:03:00+09:00',freshness:'attention',latest:run,latest_scheduled:run,trips:[{trip_id:'trip-1',title:'서울 진행 중 여행'}],runs:[run],next_cursor:'older'};
const events=[{check_id:1,at:run.started_at,stage:'schedule',trip_title:'서울 진행 중 여행',target_title:'서울 시험 공원',report:{verdict:'fatal',checks:[{category:'forecast',status:'ok',source:'시험 예보',mode:'simulation',value:{precipitation_probability:80}},{category:'traffic_control',status:'failed',reason:'1차·대체 소스 조회 실패'},{category:'earthquake',status:'ok',source:'시험 지진',value:{magnitude:0}}],advisories:[{category:'forecast',value:80}],failed_categories:['traffic_control']}},{check_id:2,at:run.finished_at,stage:'schedule_action',trip_title:'서울 진행 중 여행',target_title:'서울 시험 공원',report:{action:'fatal',case_id:'case-test'}}];

test('현재 상태·과거 회차·항목별 결과와 필터를 확인한다',async({page})=>{
  const queries:string[]=[];
  await page.route('**/admin/api/**',async route=>{
    const url=new URL(route.request().url());
    if(url.pathname.endsWith('/session'))return route.fulfill({json:{authenticated:true,configured:true,operator:'test',scopes:['ops:introspect'],csrf:'mock'}});
    if(url.pathname.endsWith('/snapshot'))return route.fulfill({json:{...createDemoSnapshot(),live:true}});
    if(url.pathname.endsWith('/api-limits'))return route.fulfill({json:{as_of:listing.as_of,limits:[]}});
    if(url.pathname.endsWith('/watch-runs')){queries.push(url.search);return route.fulfill({json:url.searchParams.has('cursor')?{...listing,runs:[{...run,run_id:'older-run',status:'completed',forced:true,started_at:'2026-10-09T09:57:00+09:00'}],next_cursor:null}:listing});}
    return route.fulfill({json:{run,events,next_after:null}});
  });
  await page.goto('/monitoring');
  await expect(page.getByRole('heading',{name:'감시 현황·로그'})).toBeVisible();
  await expect(page.getByLabel('현재 감시 상태')).toContainText('설정 주기 3분');
  await page.getByRole('button',{name:'최근 회차 상세 보기'}).click();
  await expect(page.getByRole('heading',{name:/방문 일정 점검.*서울 시험 공원/})).toBeVisible();
  await expect(page.getByText('교통 통제 · 조회 실패',{exact:true})).toBeVisible();
  await expect(page.getByText('[시뮬레이션]',{exact:true})).toBeVisible();
  await expect(page.getByText('강수확률 80%',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'이전 회차 더 보기'}).click();
  await expect(page.getByRole('cell',{name:'수동',exact:true})).toBeVisible();
  if(process.env.MONITORING_SCREENSHOT){await page.setViewportSize({width:1280,height:900});await page.screenshot({path:process.env.MONITORING_SCREENSHOT,fullPage:true});}
  await page.getByLabel('회차 상태').selectOption('failed');
  await page.getByRole('combobox',{name:/^여행/}).selectOption('trip-1');
  await page.getByRole('button',{name:'기간·조건 조회'}).click();
  await expect.poll(()=>queries.some(q=>q.includes('status=failed')&&q.includes('trip_id=trip-1'))).toBe(true);
});

test('375px에서 오류·빈 이력과 날짜 검증을 실제 화면으로 확인한다',async({page})=>{
  await page.setViewportSize({width:375,height:844});
  let failed=true;
  await page.route('**/admin/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{authenticated:true,configured:true,operator:'test',scopes:['ops:introspect'],csrf:'mock'}});
    if(path.endsWith('/snapshot'))return route.fulfill({json:{...createDemoSnapshot(),live:true}});
    if(path.endsWith('/api-limits'))return route.fulfill({json:{as_of:listing.as_of,limits:[]}});
    return failed?route.fulfill({status:503,json:{detail:'감시 이력 DB가 준비되지 않았습니다.'}}):route.fulfill({json:{...listing,latest:null,latest_scheduled:null,freshness:'not_recorded',runs:[],next_cursor:null}});
  });
  await page.goto('/monitoring');
  await expect(page.getByRole('alert').filter({hasText:'감시 이력 DB'})).toBeVisible();
  failed=false;await page.getByRole('button',{name:'기록 다시 읽기'}).click();
  await expect(page.getByText('회차 기록 없음',{exact:true})).toBeVisible();
  await expect(page.getByRole('cell',{name:/이 조건에 해당하는 회차/})).toBeVisible();
  await page.getByLabel('조회 시작 (한국 시각)').fill('2026-10-10T10:00');
  await page.getByLabel('조회 끝 (비우면 현재)').fill('2026-10-09T10:00');
  await page.getByRole('button',{name:'기간·조건 조회'}).click();
  await expect(page.getByRole('alert').filter({hasText:'조회 시작과 끝 시각'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  if(process.env.MONITORING_NARROW_SCREENSHOT)await page.screenshot({path:process.env.MONITORING_NARROW_SCREENSHOT,fullPage:true});
});
