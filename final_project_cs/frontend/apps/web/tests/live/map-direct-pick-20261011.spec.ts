import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { openFinished, mapSettled } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots = process.env.MAP_PICK_SHOTS;
const map = (page:Page) => page.getByRole('region',{name:'여행 지도',exact:true});
const picker = (page:Page) => page.getByRole('region',{name:'지도에서 위치 지정',exact:true});
const form = (page:Page) => page.getByRole('form',{name:'일정 추가',exact:true});
async function dismissIntro(page:Page) {
  const note=page.getByRole('status').filter({hasText:'계획 확인 화면이에요'});
  if(await note.count()) await note.getByRole('button',{name:'닫기',exact:true}).click();
}
async function capture(page:Page,name:string) {
  if (!shots) return;
  await mkdir(shots,{recursive:true}); await page.mouse.move(0,0);
  await page.screenshot({path:`${shots}/${name}.png`,fullPage:true});
}
test.beforeEach(async({request})=>{await mockServer(request).reset();});
for (const width of [375,1280]) {
  test(`검색에 없는 장소를 지도에서 지정하고 좌표 원값을 저장 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812}); await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots?await useMapTiles(page):async()=>{};
    const api=await openFinished(page,request,undefined,{intakeEvents:'off'}); await tiles(); await dismissIntro(page);
    await page.locator('[data-insert-near] > button').click();
    await form(page).getByLabel('일정 이름',{exact:true}).fill('종로 잠깐 쉬기');
    const date=await form(page).getByLabel('날짜',{exact:true}).inputValue();
    const start=await form(page).getByLabel('시작',{exact:true}).inputValue();
    await page.route('**/v1/web/trip-intakes/**/place-search?*',route=>route.fulfill({json:{revision:1,item:'0-0',query:'종로 쉼터',results:[],notes:[]}}));
    // 결과 유무와 관계없이 직접 위치를 지정할 수 있다.
    await page.getByRole('searchbox').fill('종로 쉼터');
    await expect(page.getByRole('status').filter({hasText:'검색 결과가 없어요.'})).toBeVisible();
    await capture(page,`search-empty-${width}`);
    await page.getByRole('button',{name:'지도에서 위치 지정',exact:true}).click();
    await expect(picker(page)).toBeVisible(); await mapSettled(page);
    await expect(picker(page).getByRole('button',{name:'이 위치 사용'})).toBeDisabled();
    const bounds=(await map(page).boundingBox())!;
    const x=Math.round(bounds.x+bounds.width*.4), y=Math.round(bounds.y+bounds.height*.45);
    await page.mouse.move(x,y); await page.mouse.down(); await page.mouse.move(x+50,y+20,{steps:8}); await page.mouse.up();
    await expect(page.locator('[data-coordinate-pin]')).toHaveCount(0); await mapSettled(page);
    await page.getByRole('button',{name:'지도 단추 펼치기',exact:true}).click();
    await expect(page.locator('[data-coordinate-pin]')).toHaveCount(0);
    await page.getByRole('button',{name:'지도 단추 접기',exact:true}).click();
    await page.mouse.click(x,y); await expect(page.locator('[data-coordinate-pin]')).toBeVisible();
    const dot=(await page.locator('[data-coordinate-pin]').boundingBox())!;
    expect(dot.x+dot.width/2).toBeCloseTo(x,0); expect(dot.y+dot.height/2).toBeCloseTo(y,0);
    const coords=(await picker(page).getByRole('status').innerText()).split(',').map(Number);
    await picker(page).getByLabel('장소 이름',{exact:true}).fill('종로 지도 쉼터');
    await tiles(); await capture(page,`pick-${width}`);
    await picker(page).getByRole('button',{name:'이 위치 사용'}).click();
    await expect(form(page).getByLabel('일정 이름',{exact:true})).toHaveValue('종로 잠깐 쉬기');
    await expect(form(page).getByLabel('날짜',{exact:true})).toHaveValue(date);
    await expect(form(page).getByLabel('시작',{exact:true})).toHaveValue(start);
    await expect(page.getByText('지도에서 지정 ·',{exact:false})).toBeVisible();
    expect(await api.received('POST','/edits')).toHaveLength(0);
    await capture(page,`confirmed-${width}`);
    await form(page).getByRole('button',{name:'일정에 추가',exact:true}).click();
    await expect.poll(async()=>(await api.received('POST','/edits')).length).toBe(1);
    const payload=(await api.received('POST','/edits'))[0].body as {edits:{field:string;value:unknown}[]};
    const place=payload.edits.find(e=>e.field.endsWith('.place'))!.value as {source:string;name:string;latitude:number;longitude:number;content_id?:string};
    expect(place.source).toBe('map'); expect(place.name).toBe('종로 지도 쉼터');
    expect(place.latitude).toBeCloseTo(coords[0],5); expect(place.longitude).toBeCloseTo(coords[1],5); expect(place.content_id).toBeUndefined();
    await noHorizontalScroll(page);
  });
  test(`위치 지정 취소·중심 선택과 확장 도구 ${width}px`,async({page,request})=>{
    await page.setViewportSize({width,height:812}); await page.emulateMedia({reducedMotion:'reduce'});
    const tiles=shots?await useMapTiles(page):async()=>{};
    const api=await openFinished(page,request,undefined,{intakeEvents:'off'}); await tiles(); await dismissIntro(page);
    await page.locator('[data-insert-near] > button').click();
    await form(page).getByLabel('일정 이름',{exact:true}).fill('입력 보존');
    await page.getByRole('searchbox').fill('찾는 이름');
    await page.getByRole('button',{name:'지도에서 위치 지정',exact:true}).click();
    await mapSettled(page); await page.getByRole('button',{name:'지도 중심 선택'}).click();
    await expect(page.locator('[data-coordinate-pin]')).toBeVisible();
    await page.getByRole('button',{name:'지도 단추 펼치기',exact:true}).click();
    for(let i=0;i<5;i++) await page.getByRole('button',{name:'축소',exact:true}).click();
    await expect(map(page)).not.toHaveAttribute('data-moving');
    const box=(await map(page).boundingBox())!;
    await page.mouse.click(Math.round(box.x+box.width*.1),Math.round(box.y+box.height*.35));
    await expect(picker(page).getByRole('status')).toContainText('서울 안에서 선택');
    await expect(picker(page).getByRole('button',{name:'이 위치 사용'})).toBeDisabled();
    await picker(page).getByRole('button',{name:'취소',exact:true}).click();
    await expect(page.getByRole('searchbox')).toHaveValue('찾는 이름');
    await expect(page.getByRole('button',{name:'지도에서 위치 지정',exact:true})).toBeFocused();
    expect(await api.received('POST','/edits')).toHaveLength(0);
    await page.getByRole('button',{name:'지도에서 위치 지정',exact:true}).click();
    await page.getByRole('button',{name:'지도 중심 선택'}).focus(); await page.keyboard.press('Escape');
    await expect(picker(page)).toHaveCount(0);
    await expect(page.getByRole('button',{name:'지도에서 위치 지정',exact:true})).toBeFocused();
    expect(await api.received('POST','/edits')).toHaveLength(0);
    await page.getByRole('button',{name:'검색어 지우기',exact:true}).click();
    await expect(form(page).getByLabel('일정 이름',{exact:true})).toHaveValue('입력 보존');
    for(let i=0;i<4;i++) await page.getByRole('button',{name:'목록 높이 바꾸기'}).press('ArrowUp');
    const group=page.getByRole('group',{name:'지도 단추',exact:true});
    const unfold=group.getByRole('button',{name:'지도 단추 펼치기',exact:true});
    if(await unfold.count()) await unfold.click();
    await expect(group.locator('[data-map-obstacle]')).toHaveCount(1);
    await expect(group.locator('[data-map-obstacle]')).toHaveAttribute('aria-label','지도 단추 접기');
    const boxes=await group.evaluate(e=>({group:e.getBoundingClientRect().width,fold:e.querySelector('[data-map-obstacle]')!.getBoundingClientRect().width}));
    expect(boxes.group).toBeGreaterThan(boxes.fold*2);
    await tiles();
    if(await unfold.count()) await unfold.click();
    await group.hover(); await page.screenshot({path:shots?`${shots}/tools-${width}.png`:undefined}); await noHorizontalScroll(page);
  });
}
