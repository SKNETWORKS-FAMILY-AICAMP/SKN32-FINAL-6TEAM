import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { card, head, openFinished, toast } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots=process.env.FOCUSED_TIME_SHOTS;
test.beforeEach(async({request})=>{await mockServer(request).reset();});
async function capture(page:Page,name:string) {
  if(!shots)return;
  await mkdir(shots,{recursive:true});await page.mouse.move(0,0);
  await expect(toast(page,'계획 확인 화면이에요')).toHaveCount(0);
  await page.screenshot({path:`${shots}/${name}.png`,fullPage:true});
}
async function openCard(page:Page,title:string) {
  if(await head(page,title).getAttribute('aria-expanded')!=='true')await head(page,title).click();
}
for(const width of [375,1280]) {
  test(`접힌 카드 종류 아이콘·상세 잠금·키보드 초점 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812});await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots?await useMapTiles(page):async()=>{};
    const kinds=['lodging','dining','train','flight','bus','activity',null];
    const expected=['lodging','dining','train','flight','bus','activity','unknown'];
    await openFinished(page,request,view=>{
      const original=view.review.items[0];
      view.review.items=kinds.map((kind,index)=>({...original,id:`0-${index}`,index,title:['서울 숙소','광장시장 식사','서울역 열차','공항 비행기','시내 버스','경복궁 관람','미정 일정'][index],kind,status:index===1?'review':'keep',locked:index===0,starts_at:`${String(9+index).padStart(2,'0')}:00`,ends_at:`${String(10+index).padStart(2,'0')}:00`,place:original.place?{...original.place,kind}:null}));
      view.review.moves=[];
    },{intakeEvents:'off'});await tiles();
    for(let i=0;i<4;i++)await page.getByRole('button',{name:'목록 높이 바꾸기'}).press('ArrowUp');
    await expect(page.locator('[data-stop-kind]')).toHaveCount(7);
    for(let i=0;i<expected.length;i++)await expect(page.locator('li[data-type=item]').nth(i).locator('[data-stop-kind]')).toHaveAttribute('data-stop-kind',expected[i]);
    await expect(page.getByRole('button',{name:/고정 풀기|꼭 넣을 일정으로 고정|확인이 필요한 일정은 고정할/})).toHaveCount(0);
    await card(page,'서울 숙소').hover();
    await expect(page.getByRole('button',{name:'서울 숙소 고정 풀기'})).toHaveCount(0);
    await capture(page,`01-kinds-${width}`);
    const before=(await head(page,'서울 숙소').boundingBox())!;
    await head(page,'서울 숙소').click();
    const unlock=page.getByRole('button',{name:'서울 숙소 고정 풀기'});
    await expect(unlock).toBeVisible();await expect(unlock).toHaveAttribute('aria-pressed','true');
    await expect(card(page,'서울 숙소').locator('[data-stop-kind]')).toHaveCount(0);
    const box=(await unlock.boundingBox())!;expect(box.width).toBe(44);expect(box.height).toBe(44);
    expect((await head(page,'서울 숙소').boundingBox())!.x).toBe(before.x);
    await head(page,'서울 숙소').press('Shift+Tab');await expect(unlock).toBeFocused();await expect(unlock.getByRole('tooltip',{includeHidden:true})).toHaveCount(0);
    await capture(page,`02-lock-${width}`);
    await head(page,'서울 숙소').click();await expect(card(page,'서울 숙소').locator('[data-stop-kind=lodging]')).toBeVisible();
    await expect(unlock).toHaveCount(0);await noHorizontalScroll(page);
  });
  test(`선택한 일정·이동만 시각 두 줄·애니메이션 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812});await page.emulateMedia({reducedMotion:'no-preference'});
    const tiles=shots?await useMapTiles(page):async()=>{};
    await openFinished(page,request,undefined,{intakeEvents:'off',intakeRoutes:'on'});await tiles();
    const first=page.locator('li[data-type=item]').first(),move=page.locator('li[data-type=move]').first();
    await expect(page.locator('[data-move-end]')).toHaveCount(0);
    await expect(first.locator('[data-stop-end]')).toHaveCSS('opacity','0');
    await expect(first.locator('[data-stop-start]')).toHaveCSS('font-weight','400');
    await expect(move.locator('[data-move-departure]')).toHaveText('10:30');
    await expect(move.locator('[data-move-arrival]')).toHaveCSS('opacity','0');
    await head(page,'경복궁 관람').click();
    await expect(first.locator('[data-stop-start]')).toHaveText('09:00');
    await expect(first.locator('[data-stop-start]')).toHaveCSS('font-weight','600');
    await expect(first.locator('[data-stop-end]')).toHaveText('~10:30');
    await expect(first.locator('[data-stop-end]')).toHaveCSS('font-weight','400');
    await expect(first.locator('[data-stop-end]')).toHaveCSS('font-size','12px');
    await expect(first.locator('[data-stop-end]')).toHaveCSS('opacity','1');
    await expect(first.locator('[data-stop-end]')).toHaveCSS('transition-duration','0.2s');
    await capture(page,`03-stop-range-${width}`);
    await move.locator('[class*=moveHead]').click();
    await expect(page.locator('[data-time-focused]')).toHaveCount(1);
    await expect(first.locator('[data-stop-end]')).toHaveCSS('opacity','0');
    await expect(first.locator('[data-stop-end]')).toHaveCSS('transition-duration','0.15s, 0.15s');
    await expect(move.locator('[data-move-arrival]')).toHaveText('~10:39');
    await expect(move.locator('[data-move-arrival]')).toHaveCSS('opacity','1');
    await expect(move.locator('[data-move-departure]')).toHaveCSS('font-weight','600');
    const geometry=await move.evaluate(el=>{
      const depart=el.querySelector('[data-move-departure]')!.getBoundingClientRect(),arrive=el.querySelector('[data-move-arrival]')!.getBoundingClientRect(),header=el.querySelector('[class*=moveHead]')!.getBoundingClientRect();
      return {centre:depart.top+depart.height/2-header.top-header.height/2,gap:arrive.top-depart.bottom};
    });expect(Math.abs(geometry.centre)).toBeLessThan(1);expect(geometry.gap).toBe(2);
    await capture(page,`04-move-range-${width}`);
    await page.emulateMedia({reducedMotion:'reduce'});
    await expect(move.locator('[data-move-arrival]')).toHaveCSS('transform','none');
    expect(parseFloat(await move.locator('[data-move-arrival]').evaluate(el=>getComputedStyle(el).transitionDuration))).toBeLessThan(0.001);
    await move.locator('[class*=moveHead]').click();
    await expect(move.locator('[data-move-arrival]')).toHaveAttribute('aria-hidden','true');await noHorizontalScroll(page);
  });
}

test('잠금은 시작·출발 드래그와 내용 변경을 막고 이웃 일정은 고정 경계까지만 움직인다',async({page,request})=>{
  await page.setViewportSize({width:375,height:812});
  const api=await openFinished(page,request,undefined,{intakeEvents:'off'});
  await openCard(page,'경복궁 관람');await page.getByRole('button',{name:'경복궁 관람 꼭 넣을 일정으로 고정'}).click();
  await expect(page.getByRole('button',{name:'경복궁 관람 고정 풀기'})).toBeVisible();
  const start=page.getByRole('button',{name:/^경복궁 관람 시간 고치기/}),depart=page.getByRole('button',{name:/^경복궁 관람에서 나서는 시각 고치기/});
  for(const time of [start,depart]) {
    await expect(time).toHaveAttribute('aria-disabled','true');await expect(time).not.toHaveAttribute('data-grab');
    const b=(await time.boundingBox())!;await page.mouse.move(b.x+b.width/2,b.y+b.height/2);await page.mouse.down();await page.mouse.move(b.x+b.width/2,b.y+b.height/2+35,{steps:5});await page.mouse.up();
    await expect(page.locator('[data-overlay=time]')).toHaveCount(0);
  }
  await expect(page.locator('li[data-type=item]').first().locator('[class*=dot]')).not.toHaveAttribute('data-grab');
  await expect(page.locator('[data-departure-mark]').first()).not.toHaveAttribute('data-grab');
  for(const name of ['경복궁 관람 수정','경복궁 관람 삭제','경복궁 관람 자동 추천']) {
    const button=page.getByRole('button',{name,exact:true});await expect(button).toHaveAttribute('aria-disabled','true');await button.click({force:true});
  }
  await expect.poll(async()=>(await api.received('POST','/edits')).length).toBe(1);
  await page.getByRole('button',{name:/^올리브영 시간 고치기/}).click();
  const form=page.getByRole('form',{name:'올리브영 시간 고치기'});
  await expect(form.getByText('가능한 시각 10:39 ~ ',{exact:false})).toBeVisible();
  await form.getByLabel('시작',{exact:true}).fill('10:45');await form.getByRole('button',{name:'적용',exact:true}).click();
  await expect.poll(async()=>(await api.received('POST','/edits')).length).toBe(2);
  const edits=(await api.received('POST','/edits'))[1].body!.edits as {field:string}[];
  expect(edits.some((edit:{field:string})=>edit.field.startsWith('items[0].'))).toBe(false);
  await expect(start).toContainText('09:00');
});

test('시간 변경 후 잠그면 되돌리기를 먼저 막고 요청을 보내지 않는다',async({page,request})=>{
  const api=await openFinished(page,request,undefined,{intakeEvents:'off'});
  await page.getByRole('button',{name:/^경복궁 관람 시간 고치기/}).click();
  const form=page.getByRole('form',{name:'경복궁 관람 시간 고치기'});
  await form.getByLabel('시작',{exact:true}).fill('09:10');await form.getByRole('button',{name:'적용',exact:true}).click();
  await expect.poll(async()=>(await api.received('POST','/edits')).length).toBe(1);
  await openCard(page,'경복궁 관람');await page.getByRole('button',{name:'경복궁 관람 꼭 넣을 일정으로 고정'}).click();
  await expect(page.getByRole('button',{name:'경복궁 관람 고정 풀기'})).toBeVisible();
  const undo=page.getByRole('button',{name:'경복궁 관람 시간 되돌리기'});
  await expect(undo).toHaveAttribute('aria-disabled','true');await undo.click({force:true});
  await expect(toast(page,'고정한 일정이라 바꿀 수 없어요')).toBeVisible();expect((await api.received('POST','/edits')).length).toBe(2);
});

test('재확인 상태인 잠근 일정도 상세에서 잠금 해제할 수 있다',async({page,request})=>{
  const api=await openFinished(page,request,view=>{view.review.items[1].locked=true;},{intakeEvents:'off'});
  await head(page,'올리브영').click();const unlock=page.getByRole('button',{name:'올리브영 고정 풀기'});
  await expect(unlock).not.toHaveAttribute('aria-disabled');await unlock.click();
  await expect.poll(async()=>(await api.received('POST','/edits')).length).toBe(1);
  expect((await api.received('POST','/edits'))[0].body!.edits).toContainEqual(expect.objectContaining({field:'items[1].locked',value:false}));
});
