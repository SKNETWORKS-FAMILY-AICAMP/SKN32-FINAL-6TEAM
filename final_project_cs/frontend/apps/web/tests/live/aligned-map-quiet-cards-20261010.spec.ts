import {expect,test,type Page} from '@playwright/test';
import {mkdir} from 'node:fs/promises';
import {mockServer,noHorizontalScroll} from './helpers';
import {card,head,openFinished} from './plan-check-kit';
import {useMapTiles} from './capture-map-tiles';

const shots=process.env.ALIGNED_MAP_SHOTS;
test.beforeEach(async({request})=>{await mockServer(request).reset();});
async function prepare(page:Page) {
  const close=page.getByRole('button',{name:'닫기',exact:true});if(await close.isVisible())await close.click();
  await page.mouse.move(0,0);
}
async function capture(page:Page,name:string) {
  if(!shots)return;await mkdir(shots,{recursive:true});await page.mouse.move(0,0);
  await page.screenshot({path:`${shots}/${name}.png`,fullPage:true});
}
async function textPosition(page:Page) {
  return page.getByRole('group',{name:'지도 단추'}).locator('button[aria-expanded]').evaluate(el=>{
    const b=el.getBoundingClientRect(),s=el.querySelector('[role=img]')!.getBoundingClientRect();
    return {x:s.x+s.width/2-b.x,y:s.y+s.height/2-b.y};
  });
}
async function arrowGeometry(page:Page) {
  return page.getByRole('group',{name:'지도 단추'}).locator('button[aria-expanded]').evaluate(el=>{
    const button=el.getBoundingClientRect(),arrow=el.querySelector('[class*=foldArrow]')!,box=arrow.getBoundingClientRect();
    const matrix=arrow.querySelector('svg')!.getScreenCTM()!;
    const back=new DOMPoint(9,12).matrixTransform(matrix),tip=new DOMPoint(15,12).matrixTransform(matrix);
    return {x:box.x+box.width/2-button.x,y:box.y+box.height/2-button.y,dx:tip.x-back.x,dy:tip.y-back.y};
  });
}
for(const width of [375,1280]) {
  test(`메뉴 정렬·고정 거리 글자·화살표만 전환 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812});await page.emulateMedia({reducedMotion:'no-preference'});
    const tiles=shots?await useMapTiles(page):async()=>{};
    await openFinished(page,request,undefined,{intakeEvents:'off',intakeRoutes:'on'});await tiles();await prepare(page);
    const controls=page.getByRole('group',{name:'지도 단추'}),fold=controls.locator('button[aria-expanded]'),arrow=fold.locator('[class*=foldArrow]');
    const menu=page.getByRole('button',{name:'메뉴',exact:true});
    const a=(await fold.boundingBox())!,b=(await menu.boundingBox())!;
    expect(a.width).toBe(b.width);expect(a.height).toBe(40);expect(Math.abs(a.x-b.x)).toBeLessThan(.6);
    await expect(arrow).toHaveCSS('transition-property','transform');await expect(arrow).toHaveCSS('transition-duration','0.2s');
    await expect.poll(async()=>(await arrowGeometry(page)).dy).toBeGreaterThan(3);
    const origin=await arrowGeometry(page);
    expect(Math.abs(origin.x-a.width/2)).toBeLessThan(.6);expect(origin.y).toBeGreaterThan(a.height/2);
    async function samePosition() {
      const current=await arrowGeometry(page);
      expect(Math.abs(current.x-origin.x)).toBeLessThan(.6);expect(Math.abs(current.y-origin.y)).toBeLessThan(.6);
    }
    const before=await textPosition(page);await capture(page,`01-column-${width}`);
    await fold.click();await expect(fold).toHaveAttribute('aria-expanded','true');
    await expect.poll(async()=>(await arrowGeometry(page)).dy).toBeLessThan(-3);await samePosition();
    expect(await textPosition(page)).toEqual(before);
    await fold.click();await expect(fold).toHaveAttribute('aria-expanded','false');
    for(let i=0;i<4;i++)await page.getByRole('button',{name:'목록 높이 바꾸기'}).press('ArrowUp');
    await expect(controls).toHaveAttribute('data-direction','row');await expect(controls).toHaveCSS('opacity','1');
    await expect.poll(async()=>(await arrowGeometry(page)).dx).toBeLessThan(-3);await samePosition();
    expect(await textPosition(page)).toEqual(before);
    const value=fold.getByRole('img');expect((await value.boundingBox())!.y+(await value.boundingBox())!.height).toBeLessThan((await arrow.boundingBox())!.y);
    await capture(page,`02-row-${width}`);
    await fold.click();await expect(fold).toHaveAttribute('aria-expanded','true');
    await expect(controls).toHaveAttribute('data-layout','row');
    await expect.poll(async()=>(await arrowGeometry(page)).dx).toBeGreaterThan(3);await samePosition();
    expect(await textPosition(page)).toEqual(before);await capture(page,`03-row-open-${width}`);
    await fold.click();
    for(let i=0;i<4;i++)await page.getByRole('button',{name:'목록 높이 바꾸기'}).press('ArrowDown');
    await expect(controls).toHaveAttribute('data-direction','column');
    await expect.poll(async()=>(await arrowGeometry(page)).dy).toBeGreaterThan(3);await samePosition();
    await page.emulateMedia({reducedMotion:'reduce'});expect(await arrow.evaluate(el=>parseFloat(getComputedStyle(el).transitionDuration))).toBeLessThanOrEqual(.0001);
    await noHorizontalScroll(page);
  });
  test(`일반 카드 무테·선택과 상태 테두리·잠금 재클릭 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812});await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots?await useMapTiles(page):async()=>{};
    await openFinished(page,request,undefined,{intakeEvents:'off'});await tiles();await prepare(page);
    for(let i=0;i<4;i++)await page.getByRole('button',{name:'목록 높이 바꾸기'}).press('ArrowUp');
    await page.evaluate(()=>{if(document.activeElement instanceof HTMLElement)document.activeElement.blur();});
    await expect(card(page,'경복궁 관람')).toHaveCSS('border-top-color','rgba(0, 0, 0, 0)');
    await expect(card(page,'올리브영')).not.toHaveCSS('border-top-color','rgba(0, 0, 0, 0)');
    await expect(card(page,'광장시장')).not.toHaveCSS('border-top-color','rgba(0, 0, 0, 0)');
    await expect(page.locator('[data-departure-mark] svg').first()).toHaveClass(/lucide-minus/);
    await capture(page,`03-cards-${width}`);
    await head(page,'경복궁 관람').focus();await expect(card(page,'경복궁 관람')).not.toHaveCSS('border-top-color','rgba(0, 0, 0, 0)');
    await head(page,'경복궁 관람').click();
    const lock=page.getByRole('button',{name:'경복궁 관람 꼭 넣을 일정으로 고정'});
    await lock.click();const unlock=page.getByRole('button',{name:'경복궁 관람 고정 풀기'});
    await expect(unlock).toHaveAttribute('aria-pressed','true');await unlock.hover();await unlock.focus();
    await expect(unlock.getByRole('tooltip',{includeHidden:true})).toHaveCount(0);await expect(unlock).not.toHaveAttribute('title',/.+/);
    await prepare(page);await capture(page,`04-lock-${width}`);
    await unlock.click();await expect(lock).toHaveAttribute('aria-pressed','false');
    await noHorizontalScroll(page);
  });
  test(`밀린 지도 마커는 실제 좌표 방향으로 모서리와 선을 연결 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812});await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots?await useMapTiles(page):async()=>{};
    await openFinished(page,request,view=>{
      const originals=view.review.items;
      view.review.items=Array.from({length:14},(_,i)=>({...originals[i===1?1:0],id:`0-${i}`,index:i,title:`서울 일정 ${i+1}`,starts_at:`${String(i+6).padStart(2,'0')}:00`,ends_at:`${String(i+7).padStart(2,'0')}:00`}));view.review.moves=[];
    },{intakeEvents:'off'});await tiles();await prepare(page);
    const facing=await page.locator('[data-pin-body]').evaluateAll(bodies=>bodies.filter(body=>(body as HTMLElement).style.visibility!=='hidden').map(body=>{
      const pin=body.parentElement!,left=parseFloat((body as HTMLElement).style.left),top=parseFloat((body as HTMLElement).style.top),middle=parseFloat(pin.style.width)/2;
      const east=left+17>=middle,north=top+17<=middle;
      return {expected:north?east?'ne':'nw':east?'se':'sw',actual:(body as HTMLElement).dataset.facing,pushed:Number(pin.dataset.push)};
    }));
    expect(facing.length).toBeGreaterThan(0);expect(facing.some(pin=>pin.pushed>0)).toBe(true);
    facing.forEach(pin=>expect(pin.actual).toBe(pin.expected));
    await capture(page,`05-markers-${width}`);await noHorizontalScroll(page);
  });
}
