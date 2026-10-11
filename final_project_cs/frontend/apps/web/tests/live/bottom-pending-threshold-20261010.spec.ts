import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { openFinished, head, pin, mapSettled } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots = process.env.BOTTOM_PENDING_SHOTS;
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
async function ready(page: Page) {
  await expect(page.getByRole('status').filter({ hasText:'계획 확인 화면이에요' })).toHaveCount(0);
}
async function capture(page: Page, name: string, tiles: () => Promise<void>) {
  if (!shots) return;
  await mkdir(shots, { recursive:true }); await page.mouse.move(0,0);
  const close=page.getByRole('status').getByRole('button',{name:'닫기',exact:true});
  if (await close.count()) await close.click();
  await page.waitForTimeout(220);
  await expect(page.getByRole('region',{name:'여행 지도',exact:true})).not.toHaveAttribute('data-moving');
  await tiles(); await page.screenshot({path:`${shots}/${name}.png`,fullPage:true});
}
for(const width of [375,1280]) {
  test(`시간은 보일 때 제목과 움직이고 가려지는 경계부터만 고정 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812}); await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots ? await useMapTiles(page) : async()=>{};
    const api=await openFinished(page,request,undefined,{intakeEvents:'off'}); await ready(page); await tiles();
    await head(page,'경복궁 관람').click();
    const body=page.locator('div[class*=sheetBody]');
    const metrics=()=>body.evaluate(e=>{
      const row=e.querySelector('[data-entry-id="0-0"]')!;
      const time=row.querySelector('[data-stop-start]')!.getBoundingClientRect(),title=row.querySelector('[class*=cardTitle]')!.getBoundingClientRect();
      const date=document.querySelector('[role=tablist]')!.getBoundingClientRect();
      return {scroll:e.scrollTop,time:time.top,center:time.top+time.height/2,titleCenter:title.top+title.height/2,clip:date.bottom,rowBottom:row.getBoundingClientRect().bottom};
    });
    await body.evaluate(e=>{e.scrollTop=0}); const original=await metrics();
    expect(Math.abs(original.center-original.titleCenter)).toBeLessThan(3);
    await capture(page,`aligned-${width}`,tiles);
    for(const delta of [20,40,60]) {
      await body.evaluate((e,at)=>{e.scrollTop=at},delta); const current=await metrics();
      expect(Math.abs(current.time-(original.time-delta))).toBeLessThan(1);
      expect(Math.abs(current.center-current.titleCenter)).toBeLessThan(3);
    }
    await capture(page,`visible-scrolling-${width}`,tiles);
    const crossing=original.time-original.clip+12;
    await body.evaluate((e,at)=>{e.scrollTop=at},crossing); const stuck=await metrics();
    expect(Math.abs(stuck.time-stuck.clip)).toBeLessThanOrEqual(4);
    await body.evaluate(e=>{e.scrollTop+=20}); expect(Math.abs((await metrics()).time-stuck.time)).toBeLessThan(1);
    await capture(page,`hidden-follow-${width}`,tiles);
    await body.evaluate(e=>{e.scrollTop=0}); expect(Math.abs((await metrics()).time-original.time)).toBeLessThan(1);
    await body.evaluate((e,at)=>{e.scrollTop=at},original.rowBottom-original.clip+25);
    expect((await metrics()).time).toBeLessThan((await metrics()).clip);
    expect(await api.received('POST','/edits')).toHaveLength(0); await noHorizontalScroll(page);
  });

  test(`수정안 안내는 하단 공백 없이 붙고 보내기와 겹치지 않는다 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812}); await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots ? await useMapTiles(page) : async()=>{};
    const api=await openFinished(page,request,undefined,{intakeEvents:'off'}); await ready(page); await tiles();
    const body=page.locator('div[class*=sheetBody]'),hint=body.getByRole('button',{name:/아래로 스크롤하면.*수정안/});
    await expect(hint).toBeVisible();
    const footer=page.locator('footer[class*=footer]');
    async function bottom() {
      await body.evaluate(e=>{e.scrollTop=e.scrollHeight}); await expect(footer).not.toHaveAttribute('data-quiet');
      await expect(body).toHaveCSS('padding-bottom','0px');
      await expect.poll(async()=>Math.abs((await body.boundingBox())!.y+(await body.boundingBox())!.height-(await hint.boundingBox())!.y-(await hint.boundingBox())!.height)).toBeLessThanOrEqual(1);
      const text=(await hint.locator('[class*=pullDirection]').boundingBox())!,fab=(await footer.boundingBox())!;
      expect(text.x+text.width<=fab.x || text.y+text.height<=fab.y || text.y>=fab.y+fab.height).toBe(true);
    }
    await bottom();
    await pin(page,'3. 광장시장').dispatchEvent('click'); await mapSettled(page); await bottom();
    await capture(page,`bottom-${width}`,tiles);
    await hint.click(); await expect(page.getByRole('group',{name:'보는 일정',exact:true})).toBeVisible();
    await expect(page.getByRole('button',{name:'2. 수정안',exact:true})).toHaveAttribute('aria-current','step');
    expect(await api.received('POST','/edits')).toHaveLength(0); await noHorizontalScroll(page);
  });

  test(`이동 시각은 둘 다 없으면 미정 하나·부분 누락은 알려진 값 유지 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812}); await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots ? await useMapTiles(page) : async()=>{};
    const api=await openFinished(page,request,v=>{
      v.review.moves[0].depart=null;v.review.moves[0].arrive=null;v.review.moves[0].minutes=null;
      v.review.moves[0].summary='장소가 정해지면 경로를 찾아요';v.review.moves[0].mode_label='';
      v.review.moves[1].arrive=null;v.review.moves[1].minutes=null;
    },{intakeEvents:'off'}); await ready(page); await tiles();
    const first=page.locator('li[data-type=move]').first(),second=page.locator('li[data-type=move]').nth(1);
    await expect(first.locator('[data-move-departure]')).toHaveText('미정');
    await expect(first.locator('[data-move-arrival]')).toHaveCount(0);
    await first.locator('button[class*=moveHead]').click();
    await expect(first.locator('[class*=timeStack]')).toHaveText('미정');
    await expect(first.getByRole('button',{name:/나서는 시각 고치기/})).toHaveAccessibleName(/지금 미정 · 도착 미정/);
    await capture(page,`pending-${width}`,tiles);
    await second.locator('button[class*=moveHead]').click();
    await expect(second.locator('[data-move-departure]')).toHaveText('12:00');
    await expect(second.locator('[data-move-arrival]')).toHaveText('미정');
    await expect(second.locator('[data-move-arrival]')).toHaveAttribute('aria-hidden','false');
    await second.getByRole('button',{name:/나서는 시각 고치기/}).click();
    await expect(page.getByRole('form',{name:'올리브영에서 나서는 시각 고치기',exact:true})).toBeVisible();
    expect(await api.received('POST','/edits')).toHaveLength(0); await noHorizontalScroll(page);
  });
}
