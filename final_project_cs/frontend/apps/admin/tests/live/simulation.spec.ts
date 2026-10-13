import { test, expect } from '@playwright/test';
import { createDemoSnapshot } from '../../src/lib/demo/fixtures';

const categories = [ ['forecast','날씨 예보'], ['weather_warning','기상 특보'], ['disaster_msg','재난문자'], ['traffic_control','교통 통제'], ['air_quality','대기질'], ['earthquake','지진'] ].map(([key,label]) => ({key,label}));

test('재난 N종 선택·적용·중지와 실행별 알림을 실제 관리자 화면에서 확인한다', async ({ page }) => {
  const commands: Record<string, unknown>[] = [];
  let configuration: Record<string, unknown> = { revision:0, active:false, categories:[] };
  await page.route('**/admin/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/session')) return route.fulfill({json:{authenticated:true,configured:true,operator:'test-operator',scopes:['ops:introspect','limits:write'],csrf:'mock-csrf'}});
    if (path.endsWith('/snapshot')) return route.fulfill({json:{...createDemoSnapshot(),live:true}});
    if (path.endsWith('/simulations')) return route.fulfill({json:{trips:[{trip_id:'trip-test',title:'서울 진행 중 여행'}],categories}});
    if (path.endsWith('/simulations/trip-test')) {
      if (route.request().method() === 'PATCH') {
        expect(route.request().headers()['x-csrf-token']).toBe('mock-csrf');
        const body=route.request().postDataJSON(); commands.push(body);
        configuration={revision:Number(configuration.revision)+1,active:body.categories.length>0,categories:body.categories,item_id:body.item_id,expires_at:'2099-01-01T00:15:00+09:00',run_id:'trial-1'};
      }
      return route.fulfill({json:{trip_id:'trip-test',title:'서울 진행 중 여행',version:3,configuration,
        items:[{item_id:'current-item',title:'서울 시험 공원',starts_at:'2026-10-09T10:00:00+09:00',ongoing:true,weather_sensitive:true}],
        notices:configuration.active ? [{key:'notice-1',text:'[시뮬레이션] 재난 위험으로 오늘 남은 일정을 정지했어요.',at:'2026-10-09T10:00:00+09:00'}] : []}});
    }
    return route.fulfill({status:404,json:{detail:'mock 요청 경로 확인 필요'}});
  });
  await page.goto('/simulations');
  await expect(page.getByRole('heading',{name:'재난 6종 시뮬레이션'})).toBeVisible();
  await page.getByLabel('대상 여행').selectOption('trip-test');
  await expect(page.getByRole('switch')).toHaveCount(6);
  await expect(page.getByLabel('대상 일정')).toHaveValue('current-item');
  await page.getByRole('switch',{name:/날씨 예보/}).check();
  await page.getByRole('switch',{name:/교통 통제/}).check();
  await page.getByRole('switch',{name:/지진/}).check();
  await expect(page.getByRole('group')).toContainText('선택 3/6');
  await page.getByRole('button',{name:'선택한 3종 적용'}).click();
  await expect(page.getByRole('alert').filter({hasText:'적용·중지 사유'})).toBeVisible();
  expect(commands).toHaveLength(0);
  await page.getByLabel('적용·중지 사유').fill('현재 일정 복합 재난 시험');
  await page.getByRole('button',{name:'선택한 3종 적용'}).click();
  await expect(page.getByText(/입력 3종 활성/)).toBeVisible();
  expect(commands[0]).toEqual({expected_revision:0,expected_version:3,item_id:'current-item',categories:['forecast','traffic_control','earthquake'],duration_minutes:15,reason:'현재 일정 복합 재난 시험'});
  await expect(page.getByText('[시뮬레이션] 재난 위험으로 오늘 남은 일정을 정지했어요.',{exact:true})).toBeVisible();
  if (process.env.SIMULATION_SCREENSHOT) {
    await page.setViewportSize({width:1280,height:900});
    await page.screenshot({path:process.env.SIMULATION_SCREENSHOT,fullPage:true});
  }
  await page.getByLabel('적용·중지 사유').fill('복합 재난 시험 종료');
  await page.getByRole('button',{name:'시뮬레이션 중지'}).click();
  await expect(page.getByText('시뮬레이션 입력 꺼짐',{exact:false})).toBeVisible();
  expect(commands[1]).toMatchObject({expected_revision:1,expected_version:3,item_id:null,categories:[],reason:'복합 재난 시험 종료'});
});

test('좁은 화면에서 6개 스위치를 키보드로 조작한다', async ({ page }) => {
  await page.setViewportSize({width:375,height:844});
  await page.route('**/admin/api/**', async route => {
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{authenticated:true,configured:true,operator:'test',scopes:[],csrf:'mock'}});
    if(path.endsWith('/snapshot'))return route.fulfill({json:{...createDemoSnapshot(),live:true}});
    if(path.endsWith('/simulations'))return route.fulfill({json:{trips:[{trip_id:'t',title:'서울 여행'}],categories}});
    return route.fulfill({json:{trip_id:'t',title:'서울 여행',version:1,configuration:{revision:0,active:false,categories:[]},items:[],notices:[]}});
  });
  await page.goto('/simulations');
  await page.getByLabel('대상 여행').selectOption('t');
  const first=page.getByRole('switch',{name:/날씨 예보/});
  await first.focus(); await page.keyboard.press('Space');
  await expect(first).toBeChecked();
  if (process.env.SIMULATION_NARROW_SCREENSHOT) await page.screenshot({path:process.env.SIMULATION_NARROW_SCREENSHOT,fullPage:true});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await page.getByLabel('적용·중지 사유').fill('위치 없는 일정 시험');
  await page.getByRole('button',{name:'선택한 1종 적용'}).click();
  await expect(page.getByRole('alert').filter({hasText:'대상 일정을 선택'})).toBeVisible();
});
