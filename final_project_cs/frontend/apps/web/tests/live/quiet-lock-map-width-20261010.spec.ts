import {expect,test,type Page} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
import {mockServer,noHorizontalScroll} from './helpers';
import {card,head,openFinished} from './plan-check-kit';
import {useMapTiles} from './capture-map-tiles';

const shots=process.env.QUIET_LOCK_SHOTS;
test.beforeEach(async({request})=>{await mockServer(request).reset();});
async function capture(page:Page,name:string) {
 if(!shots)return;await mkdir(shots,{recursive:true});await page.mouse.move(0,0);
 if(name.startsWith('04-'))await page.evaluate(()=>{if(document.activeElement instanceof HTMLElement)document.activeElement.blur();});
 await page.screenshot({path:`${shots}/${name}.png`,fullPage:true});
}
for(const width of [375,1280]) {
 test(`거리 버튼은 두 방향 모두 메뉴 폭·기존 높이 ${width}px`,async({page,request})=>{
  await page.setViewportSize({width,height:812});await page.emulateMedia({reducedMotion:'reduce'});
  const tiles=shots?await useMapTiles(page):async()=>{};
  await openFinished(page,request,undefined,{intakeEvents:'off',intakeRoutes:'on'});await tiles();
  const noticeClose=page.getByRole('button',{name:'닫기',exact:true});if(await noticeClose.isVisible())await noticeClose.click();
  const controls=page.getByRole('group',{name:'지도 단추'}),fold=controls.getByRole('button',{name:'지도 단추 펼치기'});
  const menu=page.getByRole('button',{name:'메뉴',exact:true});
  const menuBox=(await menu.boundingBox())!;
  await expect(controls).toHaveAttribute('data-direction','column');
  const column=await fold.evaluate(el=>{const b=el.getBoundingClientRect(),scale=el.querySelector('[role=img]')!.getBoundingClientRect(),arrow=el.querySelector('svg')!.getBoundingClientRect();return{width:b.width,height:b.height,scaleBottom:scale.bottom,arrowTop:arrow.top};});
  expect(column.width).toBe(menuBox.width);expect(column.height).toBe(40);expect(column.scaleBottom).toBeLessThanOrEqual(column.arrowTop);
  await capture(page,`01-column-${width}`);
  for(let i=0;i<4;i++)await page.getByRole('button',{name:'목록 높이 바꾸기'}).press('ArrowUp');
  await expect(controls).toHaveAttribute('data-direction','row');await expect(controls).toHaveCSS('opacity','1');
  expect((await fold.boundingBox())!.width).toBe(menuBox.width);expect((await fold.boundingBox())!.height).toBe(40);
  const fits=await fold.evaluate(el=>{const b=el.getBoundingClientRect(),range=document.createRange();range.selectNodeContents(el.querySelector('[role=img]')!);const s=range.getBoundingClientRect();return s.left>=b.left && s.right<=b.right;});expect(fits).toBe(true);
  await capture(page,`02-row-${width}`);await fold.click();await expect(controls).toHaveAttribute('data-layout','row');await noHorizontalScroll(page);
 });
 test(`잠금은 아이콘만 채우고 도움말 없이 다시 누르면 해제 ${width}px`,async({page,request})=>{
  await page.setViewportSize({width,height:812});await page.emulateMedia({reducedMotion:'reduce'});
  const tiles=shots?await useMapTiles(page):async()=>{};
  await openFinished(page,request,view=>{view.review.items[0].locked=true;},{intakeEvents:'off'});await tiles();
  const noticeClose=page.getByRole('button',{name:'닫기',exact:true});if(await noticeClose.isVisible())await noticeClose.click();
  await head(page,'경복궁 관람').click();
  const lock=page.getByRole('button',{name:'경복궁 관람 고정 풀기'}),tooltip=lock.getByRole('tooltip',{includeHidden:true});
  await page.mouse.move(0,0);await expect(tooltip).toHaveCount(0);
  await expect(lock).toHaveCSS('background-color','rgba(0, 0, 0, 0)');
  await expect(lock.locator('svg rect')).toHaveCSS('fill-opacity','0.2');
  await expect(card(page,'경복궁 관람')).toHaveCSS('box-shadow','none');
  await lock.hover();await expect(tooltip).toHaveCount(0);await expect(lock).toHaveCSS('background-color','rgba(0, 0, 0, 0)');
  await head(page,'경복궁 관람').press('Shift+Tab');await expect(lock).toBeFocused();
  await expect(lock).toHaveCSS('outline-style','none');await expect(lock.locator(':scope > svg')).toHaveCSS('stroke-width','2.6px');await expect(tooltip).toHaveCount(0);
  await capture(page,`03-lock-tooltip-${width}`);
  await head(page,'경복궁 관람').focus();await page.mouse.move(0,0);await expect(tooltip).toHaveCount(0);
  await capture(page,`04-lock-${width}`);await lock.click();await expect(page.getByRole('button',{name:'경복궁 관람 꼭 넣을 일정으로 고정'})).toBeVisible();await noHorizontalScroll(page);
 });
 test(`전체 자동 추천은 목록과 함께 사라지고 최상단에서 복귀 ${width}px`,async({page,request})=>{
  await page.setViewportSize({width,height:812});await page.emulateMedia({reducedMotion:'reduce'});
  const tiles=shots?await useMapTiles(page):async()=>{};
  await openFinished(page,request,view=>{const originals=view.review.items;view.review.items=Array.from({length:10},(_,i)=>({...originals[i===1?1:0],id:`0-${i}`,index:i,title:`서울 일정 ${i+1}`,starts_at:`${String(i+8).padStart(2,'0')}:00`,ends_at:`${String(i+9).padStart(2,'0')}:00`}));view.review.moves=[];},{intakeEvents:'off'});await tiles();
  const noticeClose=page.getByRole('button',{name:'닫기',exact:true});if(await noticeClose.isVisible())await noticeClose.click();
  const body=page.locator('[class*=sheetBody]'),all=body.getByRole('button',{name:/^전체 자동 추천/});
  await expect(all).toBeInViewport();await expect(all).toHaveCSS('position','static');await expect(page.getByRole('button',{name:/^전체 자동 추천/})).toHaveCount(1);
  const before=(await all.boundingBox())!.y;await capture(page,`05-top-${width}`);
  await body.evaluate(el=>{el.scrollTop=250;});
  await expect.poll(async()=>((await all.boundingBox())!.y)).toBeLessThan(before-100);
  expect((await all.boundingBox())!.y+(await all.boundingBox())!.height).toBeLessThan((await body.boundingBox())!.y);
  await capture(page,`06-scrolled-${width}`);
  await body.evaluate(el=>{el.scrollTop=0;});await expect(all).toBeInViewport();await noHorizontalScroll(page);
 });
}
