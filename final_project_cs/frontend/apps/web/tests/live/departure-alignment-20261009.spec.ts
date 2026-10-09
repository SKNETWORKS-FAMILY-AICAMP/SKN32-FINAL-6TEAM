import { expect, test, type Locator, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { openFinished, toast } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots=process.env.DEPARTURE_SHOTS;
test.beforeEach(async({request})=>{await mockServer(request).reset();});
async function aligned(row:Locator) {
  const points=await row.evaluate(el=>{
    const centre=(selector:string)=>{const b=el.querySelector(selector)!.getBoundingClientRect();return b.top+b.height/2;};
    const mark=el.querySelector<HTMLElement>('[data-departure-mark]')!;
    return {time:centre('[data-move-departure]'),icon:centre('[data-departure-mark]'),head:centre('[class*=moveHead]'),shape:getComputedStyle(mark).borderRadius,svg:mark.querySelector('svg')?.getAttribute('class')};
  });
  expect(Math.abs(points.time-points.head)).toBeLessThan(1);
  expect(Math.abs(points.icon-points.head)).toBeLessThan(1);
  expect(points.shape).toBe('0px'); expect(points.svg).toContain('arrow-right-from-line');
}
async function capture(page:Page,name:string) {
  if(!shots)return;
  await mkdir(shots,{recursive:true});await page.mouse.move(0,0);
  await expect(toast(page,'계획 확인 화면이에요')).toHaveCount(0);
  await page.screenshot({path:`${shots}/${name}.png`,fullPage:true});
}
for(const width of [375,1280]) {
  test(`출발 시각·화살표·경로 한 줄 정렬 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812});await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots?await useMapTiles(page):async()=>{};
    await openFinished(page,request,undefined,{intakeEvents:'off',intakeRoutes:'on'});await tiles();
    const row=page.locator('li[data-type=move]').first();
    await expect(row.locator('[data-move-departure]')).toHaveText('10:30');
    await expect(row.locator('button[class*=time] [data-move-departure]')).toHaveText('10:30');
    await expect(row.locator('[data-move-end]')).toHaveCount(0);
    await expect(row.locator('[data-move-arrival]')).toHaveAttribute('aria-hidden','true');
    await aligned(row);await capture(page,`01-departure-${width}`);
    await row.locator('[class*=moveHead]').click();await aligned(row);
    await expect(row.locator('[data-move-arrival]')).toHaveText('~10:39');
    await expect(row.locator('[data-move-arrival]')).toHaveAttribute('aria-hidden','false');
    await noHorizontalScroll(page);
  });
  test(`시각 누락·떠 있는 일차·스크롤 정렬 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812});await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots?await useMapTiles(page):async()=>{};
    await openFinished(page,request,view=>{
      view.review.items[0].title='호텔';view.review.items[0].ends_at=null;
      const move=view.review.moves[0];move.depart=null;move.arrive=null;move.minutes=null;move.summary='장소가 정해지면 경로를 찾아요';
      view.review.items.push({...view.review.items[2],id:'second-day',index:3,title:'둘째 날 식당',day:2,date:'2026-10-02'});
    },{intakeEvents:'off',intakeRoutes:'on'});await tiles();
    await expect(page.getByRole('tab',{name:/2일차/})).toHaveCount(1);
    const row=page.locator('li[data-type=move]').first();
    await expect(row.locator('[data-move-departure]')).toHaveText('—');await aligned(row);
    const body=page.locator('[class*=sheetBody]');await body.evaluate(el=>{el.scrollTop+=40;});
    await aligned(row);await capture(page,`02-no-time-${width}`);
    expect(await row.locator('button[class*=time]').evaluate(el=>getComputedStyle(el).position)).toBe('absolute');
    await noHorizontalScroll(page);
  });
}
test('출발 화살표를 끌면 출발 시각 변경을 저장한다',async({page,request})=>{
  await page.setViewportSize({width:375,height:812});
  const api=await openFinished(page,request,undefined,{intakeEvents:'off'});
  const mark=page.locator('[data-departure-mark]').first(),box=(await mark.boundingBox())!;
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.down();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2+20,{steps:5});
  await expect(page.getByRole('group',{name:'하루 일정 미니맵'})).toBeVisible();
  await page.mouse.move(box.x+box.width/2,box.y+box.height/2+35,{steps:5});await page.mouse.up();
  await expect.poll(async()=>(await api.received('POST','/edits')).length).toBe(1);
  const edits=(await api.received('POST','/edits'))[0].body!.edits;
  expect(edits).toContainEqual(expect.objectContaining({field:'items[0].ends_at'}));
  expect(edits).not.toContainEqual(expect.objectContaining({field:'items[0].starts_at'}));
});
