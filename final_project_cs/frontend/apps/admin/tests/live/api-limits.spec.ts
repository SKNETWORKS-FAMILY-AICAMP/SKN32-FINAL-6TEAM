import { test, expect } from '@playwright/test';
import { createDemoSnapshot } from '../../src/lib/demo/fixtures';

const field = (env: string | null, value: number | null, zero_meaning = 'unset', origin = 'configured') => ({ env, value, zero_meaning, origin });
const its = { id: 'its', name: '국가교통정보 ITS', budget_timezone: 'Asia/Seoul', daily: field('ACOP_RATE_ITS_PER_DAY', 1000), monthly: field('ACOP_RATE_ITS_PER_MONTH', 0), recorded: { day: {used:123,cap:800,updated_at:'2026-10-09T22:00:00+09:00'}, month:null }, operator_cap:{day:500,month:15000} };
const odsay = { id:'odsay', name:'대중교통 ODsay', budget_timezone:'Asia/Seoul', daily:field('ACOP_RATE_ODSAY_PER_DAY',30,'no_interval_limit','default'),monthly:field(null,null,'unset','absent'),recorded:{day:null,month:null},operator_cap:null };
const data = { as_of:'2026-10-09T22:01:00+09:00', timezone:'Asia/Seoul',usage_error:null,limits:[its,odsay] };

test('ENV 한도·기본값·현재 사용·마지막 상한을 구분하고 검색·다시 읽기한다', async ({page}) => {
  let reads=0;
  await page.route('**/admin/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{authenticated:true,configured:true,operator:'test',scopes:['ops:introspect'],csrf:'mock'}});
    if(path.endsWith('/snapshot'))return route.fulfill({json:{...createDemoSnapshot(),live:true}});
    if(path.endsWith('/api-limits')){reads++;return route.fulfill({json:data});}
    return route.abort();
  });
  await page.goto('/usage');
  const panel=page.getByRole('region',{name:'API 환경설정 한도'});
  await expect(panel.getByRole('cell',{name:/ACOP_RATE_ITS_PER_DAY/})).toContainText('1,000회');
  await expect(panel.getByText('0 · 미설정 · 세기만',{exact:true})).toBeVisible();
  await expect(panel.getByRole('cell',{name:/ACOP_RATE_ODSAY_PER_DAY/})).toContainText('기본값');
  await expect(panel.getByRole('cell',{name:/일: 123회/})).toContainText('800회');
  await expect(panel.getByRole('cell',{name:/일 500회/})).toBeVisible();
  expect(await panel.getByRole('cell',{name:/ACOP_RATE_ITS_PER_DAY/}).evaluate(element=>getComputedStyle(element).fontSize)).toBe('14px');
  expect(await panel.getByRole('cell',{name:/ACOP_RATE_ITS_PER_DAY/}).locator('code').evaluate(element=>getComputedStyle(element).fontSize)).toBe('12px');
  await panel.getByLabel('API·환경변수 찾기').focus();await page.keyboard.press('Tab');
  await expect(panel.getByRole('region',{name:/API 한도 표/})).toBeFocused();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  if(process.env.API_LIMITS_SCREENSHOT)await page.screenshot({path:process.env.API_LIMITS_SCREENSHOT,fullPage:true});
  if(process.env.API_LIMITS_PANEL_SCREENSHOT)await panel.screenshot({path:process.env.API_LIMITS_PANEL_SCREENSHOT});
  await panel.getByLabel('API·환경변수 찾기').fill('ACOP_RATE_ITS');
  await expect(panel.getByText('1/2개 표시',{exact:false})).toBeVisible();
  await expect(panel.getByRole('cell',{name:/대중교통 ODsay/})).toHaveCount(0);
  await panel.getByLabel('API·환경변수 찾기').fill('검색결과없음');
  await expect(panel.getByRole('cell',{name:/검색 조건에 해당하는 API/})).toBeVisible();
  await panel.getByRole('button',{name:'검색어 지우기'}).click();
  await expect(panel.getByRole('cell',{name:/대중교통 ODsay/})).toBeVisible();
  await panel.getByRole('button',{name:'한도 다시 읽기'}).click();
  await expect.poll(()=>reads).toBeGreaterThan(1);
});

test('375px에서 조회 오류·재시도·DB 오류를 숨기지 않는다', async ({page}) => {
  await page.setViewportSize({width:375,height:844});
  let failed=true;
  await page.route('**/admin/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{authenticated:true,configured:true,operator:'test',scopes:['ops:introspect'],csrf:'mock'}});
    if(path.endsWith('/snapshot'))return route.fulfill({json:{...createDemoSnapshot(),live:true}});
    return failed?route.fulfill({status:503,json:{detail:'운영 앱에 연결하지 못했습니다.'}}):route.fulfill({json:{...data,usage_error:'DB 사용 기록을 읽지 못했습니다.',limits:[odsay]}});
  });
  await page.goto('/usage');
  const panel=page.getByRole('region',{name:'API 환경설정 한도'});
  await expect(panel.getByRole('alert')).toContainText('한도 설정을 읽지 못했습니다.');
  failed=false;await panel.getByRole('button',{name:'한도 다시 읽기'}).click();
  await expect(panel.getByRole('alert')).toContainText('환경설정 한도만 표시');
  await expect(panel.getByRole('cell',{name:/ACOP_RATE_ODSAY_PER_DAY/})).toContainText('30회');
  await expect(panel.getByRole('cell',{name:'미확인',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  if(process.env.API_LIMITS_NARROW_SCREENSHOT)await page.screenshot({path:process.env.API_LIMITS_NARROW_SCREENSHOT,fullPage:true});
});
