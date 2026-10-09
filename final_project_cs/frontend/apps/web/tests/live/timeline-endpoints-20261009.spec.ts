import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { openFinished, pin, mapSettled, toast } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';
const shots=process.env.TIMELINE_SHOTS;
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
async function capture(page:Page,name:string) {
  if(!shots) return;
  await mkdir(shots,{recursive:true}); await page.mouse.move(0,0); await page.evaluate(()=>getSelection()?.removeAllRanges());
  await expect(toast(page,'계획 확인 화면이에요')).toHaveCount(0);
  await page.screenshot({path:`${shots}/${name}.png`,fullPage:true});
}
for(const width of [375,1280]) {
  test(`출발 시각·큰 시작 시각·세로 지도 단추 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812}); await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots ? await useMapTiles(page) : async()=>{};
    await openFinished(page,request,undefined,{intakeEvents:'off',intakeRoutes:'on'}); await tiles();
    const row=page.locator('li[data-type=move]').first();
    await expect(row.locator('[data-move-end]')).toHaveCount(0);
    await expect(row.locator('[data-move-departure]')).toHaveText('10:30');
    await expect(row.locator('[data-move-arrival]')).toHaveAttribute('aria-hidden','true');
    await expect(row).not.toContainText('머무름');
    await expect(page.locator('li[data-type=item]').first().locator(':scope > [class*=time]')).toHaveCSS('font-size','16px');
    expect((await page.locator('li[data-type=item]').first().locator(':scope > [class*=time]').boundingBox())!.height).toBeGreaterThanOrEqual(44);
    const controls=page.getByRole('group',{name:'지도 단추'}),fold=controls.getByRole('button',{name:'지도 단추 펼치기'});
    await expect(controls).toHaveAttribute('data-direction','column');
    const dimensions=await fold.evaluate(el=>{const b=el.getBoundingClientRect(),s=el.querySelector('[role=img]')!.getBoundingClientRect(),arrow=el.querySelector('svg')!.getBoundingClientRect();return {width:b.width,height:b.height,scaleBottom:s.bottom,arrowTop:arrow.top,background:getComputedStyle(el).backgroundColor};});
    expect(dimensions.width).toBeLessThanOrEqual(44); expect(dimensions.height).toBe(40); expect(dimensions.scaleBottom).toBeLessThanOrEqual(dimensions.arrowTop);
    expect(dimensions.background).toMatch(/0\.92|92%/);
    await capture(page,`01-times-map-${width}`); await noHorizontalScroll(page);
  });
  test(`추가 취소 후 바깥 화면 고정·마지막 카드 전체 표시 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812}); await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots ? await useMapTiles(page) : async()=>{};
    await openFinished(page,request,undefined,{intakeEvents:'off',intakeRoutes:'on'}); await tiles();
    await pin(page,'1. 경복궁 관람').dispatchEvent('click'); await mapSettled(page);
    const name=await page.locator('[data-insert-near] > button').getAttribute('aria-label');
    await page.locator('[data-insert-near] > button').click();
    for(let i=0;i<4;i++) await page.getByRole('button',{name:'목록 높이 바꾸기'}).press('ArrowUp');
    await page.getByRole('button',{name:'일정 추가 취소',exact:true}).click();
    await expect(page.getByRole('button',{name:name!,exact:true})).toBeFocused();
    const geometry=()=>page.locator('[class*=checking]').first().evaluate(el=>{
      const root=el.getBoundingClientRect(),body=el.querySelector('[class*=sheetBody]')!.getBoundingClientRect();return {scroll:el.scrollTop,gap:root.bottom-body.bottom};
    });
    await expect.poll(geometry).toEqual({scroll:0,gap:0});
    await capture(page,`02-return-${width}`);
    await page.locator('[class*=sheetBody]').evaluate(el=>{el.scrollTop=el.scrollHeight;});
    await expect.poll(()=>page.locator('article').last().evaluate(el=>{const b=el.getBoundingClientRect(),body=el.closest('[class*=sheetBody]')!.getBoundingClientRect();return b.top>=body.top&&b.bottom<=body.bottom;})).toBe(true);
    await capture(page,`03-bottom-${width}`);
  });
  test(`스크롤·드래그 중 제출 숨김과 유휴 복원 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812});
    const tiles=shots ? await useMapTiles(page) : async()=>{};
    await openFinished(page,request,undefined,{intakeEvents:'off'}); await tiles();
    const footer=page.locator('footer[class*=footer]'),body=page.locator('[class*=sheetBody]');
    await expect(footer).not.toHaveAttribute('data-quiet');
    await body.dispatchEvent('wheel',{deltaY:40});
    await expect(footer).toHaveAttribute('data-quiet'); await expect(footer).toHaveAttribute('inert');
    await expect(footer).toHaveCSS('opacity','0'); await expect(footer).toHaveCSS('transition-duration','0.15s');
    await expect(footer).not.toHaveAttribute('data-quiet'); await expect(footer).toHaveCSS('transition-duration','0.2s, 0.2s');
    const b=(await body.boundingBox())!;
    await page.mouse.move(b.x+3,b.y+70); await page.mouse.down();
    await expect(footer).toHaveAttribute('data-quiet'); await page.waitForTimeout(900); await expect(footer).toHaveAttribute('data-quiet');
    await capture(page,`04-interacting-${width}`);
    await page.mouse.up(); await expect(footer).not.toHaveAttribute('data-quiet');
    await page.emulateMedia({reducedMotion:'reduce'}); await body.dispatchEvent('wheel',{deltaY:20});
    await expect(footer).toHaveCSS('transform','none'); expect(await footer.evaluate(el=>parseFloat(getComputedStyle(el).transitionDuration))).toBeLessThanOrEqual(0.00015);
    await expect(footer).not.toHaveAttribute('data-quiet');
    await footer.getByRole('button').focus(); await page.keyboard.press('Tab');
    await expect(footer).not.toHaveAttribute('inert');
  });
}
test('도착 시각이 없는 구간은 시각을 지어내지 않는다',async({page,request})=>{
  await openFinished(page,request,view=>{for(const move of view.review.moves){move.arrive=null;move.minutes=null;}},{intakeEvents:'off'});
  await expect(page.locator('[data-move-arrival]').first()).toHaveText('~—');
});
