import { test, expect } from '@playwright/test';
import { createDemoSnapshot } from '../../src/lib/demo/fixtures';

const values:Record<string,number>={kma:1000,open_meteo:10000,kma_warning:10000,disaster_msg:1000,utic:1000,its:800,airkorea:500,open_meteo_air:2000,kma_earthquake:1000};
const limits=Object.entries(values).map(([id,value])=>({id,name:id,daily:{env:`ACOP_RATE_${id.toUpperCase()}_PER_DAY`,value,origin:'configured',zero_meaning:'no_interval_limit'},monthly:{env:id==='its'?'ACOP_RATE_ITS_PER_MONTH':null,value:id==='its'?0:null,origin:id==='its'?'configured':'absent',zero_meaning:id==='its'?'unset':null}}));
const data={as_of:'2026-10-09T23:03:00+09:00',limits};
const listing={as_of:data.as_of,interval_seconds:180,last_gate_at:null,next_expected_at:null,freshness:'not_recorded',latest:null,latest_scheduled:null,trips:[],runs:[],next_cursor:null};

test('6개 감시 항목 옆에 각 API의 한도를 따로 표시한다',async({page})=>{
  let reads=0;
  await page.route('**/admin/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{authenticated:true,configured:true,operator:'test',scopes:['ops:introspect'],csrf:'mock'}});
    if(path.endsWith('/snapshot'))return route.fulfill({json:{...createDemoSnapshot(),live:true}});
    if(path.endsWith('/api-limits')){reads++;return route.fulfill({json:data});}
    return route.fulfill({json:listing});
  });
  await page.goto('/monitoring');
  const panel=page.getByRole('region',{name:'감시 항목·API 한도',exact:true});
  await expect(panel.locator('tbody > tr')).toHaveCount(6);
  const forecast=panel.getByRole('row').filter({has:page.getByRole('cell',{name:'날씨 예보',exact:true})});
  await expect(forecast).toContainText('강수확률·풍속 등의 주의사항');
  await expect(forecast).toContainText('하루 1,000회');await expect(forecast).toContainText('하루 10,000회');
  const traffic=panel.getByRole('row').filter({has:page.getByRole('cell',{name:'도로 상황',exact:true})});
  await expect(traffic).toContainText('하루 1,000회');await expect(traffic).toContainText('하루 800회 · 월 0 · 미설정 · 세기만');
  await traffic.getByText('ENV 이름·출처 보기',{exact:true}).last().click();
  await expect(traffic.getByText('ACOP_RATE_ITS_PER_DAY',{exact:true})).toBeVisible();
  await traffic.getByText('ENV 이름·출처 보기',{exact:true}).last().click();
  const air=panel.getByRole('row').filter({has:page.getByRole('cell',{name:'대기질',exact:true})});
  await expect(air).toContainText('하루 500회');await expect(air).toContainText('하루 2,000회');
  await expect(panel.getByRole('row').filter({has:page.getByRole('cell',{name:'기상 특보',exact:true})})).toContainText('하루 10,000회');
  await expect(panel.getByRole('row').filter({has:page.getByRole('cell',{name:'재난문자',exact:true})})).toContainText('하루 1,000회');
  await expect(panel.getByRole('row').filter({has:page.getByRole('cell',{name:'지진',exact:true})})).toContainText('하루 1,000회');
  await panel.getByRole('button',{name:'감시 API 한도 다시 읽기'}).click();await expect.poll(()=>reads).toBeGreaterThan(1);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  if(process.env.WATCH_LIMITS_SCREENSHOT)await panel.screenshot({path:process.env.WATCH_LIMITS_SCREENSHOT});
});

test('375px에서 한도 조회 실패·누락을 0으로 만들지 않고 재시도한다',async({page})=>{
  await page.setViewportSize({width:375,height:844});
  let failed=true;
  await page.route('**/admin/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/session'))return route.fulfill({json:{authenticated:true,configured:true,operator:'test',scopes:['ops:introspect'],csrf:'mock'}});
    if(path.endsWith('/snapshot'))return route.fulfill({json:{...createDemoSnapshot(),live:true}});
    if(path.endsWith('/api-limits'))return failed?route.fulfill({status:503,json:{detail:'조회 실패'}}):route.fulfill({json:{...data,limits:limits.filter(value=>value.id!=='utic')}});
    return route.fulfill({json:listing});
  });
  await page.goto('/monitoring');
  const panel=page.getByRole('region',{name:'감시 항목·API 한도',exact:true});
  await expect(panel.getByRole('alert')).toContainText('감시 API 한도를 읽지 못했습니다.');
  await expect(panel.locator('tbody > tr')).toHaveCount(6);
  failed=false;await panel.getByRole('button',{name:'감시 API 한도 다시 읽기'}).click();
  const traffic=panel.getByRole('row').filter({has:page.getByRole('cell',{name:'도로 상황',exact:true})});
  await expect(traffic).toContainText('UTIC한도 미확인');await expect(traffic).toContainText('하루 800회');
  await expect(panel.getByRole('alert')).toHaveCount(0);
  await panel.getByRole('button',{name:'감시 API 한도 다시 읽기'}).focus();await page.keyboard.press('Tab');
  const frame=panel.getByRole('region',{name:/6개 감시 항목과 API 한도 표/});await expect(frame).toBeFocused();
  await page.keyboard.press('ArrowRight');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  const tableSize=await panel.locator('table').evaluate(element=>({width:element.getBoundingClientRect().width,viewport:innerWidth}));
  expect(tableSize.width).toBeLessThanOrEqual(tableSize.viewport);
  await frame.evaluate(element=>(element as HTMLElement).blur());
  if(process.env.WATCH_LIMITS_NARROW_SCREENSHOT)await panel.screenshot({path:process.env.WATCH_LIMITS_NARROW_SCREENSHOT});
});
