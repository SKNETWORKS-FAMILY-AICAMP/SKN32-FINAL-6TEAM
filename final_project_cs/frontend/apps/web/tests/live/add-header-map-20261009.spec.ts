import { expect, test, type Page } from "@playwright/test";
import { mkdir, access } from "node:fs/promises";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { mockServer, noHorizontalScroll } from "./helpers";
import { INTAKE, mapSettled, openFinished, pin, toast } from "./plan-check-kit";
import { useMapTiles } from "./capture-map-tiles";

const shots = process.env.ADD_HEADER_SHOTS;
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
async function capture(page: Page, name: string) {
  if (!shots) return;
  await mkdir(shots, { recursive: true }); await page.mouse.move(0, 0); await page.waitForTimeout(220);
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}
async function drag(page: Page, x: number, y: number, dx: number, dy = 0) {
  await page.mouse.move(x,y); await page.mouse.down(); await page.mouse.move(x+dx,y+dy,{ steps:12 }); await page.mouse.up();
}
async function collisions(page: Page) {
  return page.getByRole('region',{name:'여행 지도'}).evaluate(map=>{
    const boxes=[...map.querySelectorAll<HTMLElement>('[data-pin-body],[data-edge-chip],[data-map-controls]')]
      .filter(node=>getComputedStyle(node).visibility!=='hidden' && getComputedStyle(node).display!=='none').map(node=>node.getBoundingClientRect());
    return boxes.flatMap((a,i)=>boxes.slice(i+1).filter(b=>Math.min(a.right,b.right)-Math.max(a.left,b.left)>1 && Math.min(a.bottom,b.bottom)-Math.max(a.top,b.top)>1)).length;
  });
}
for (const width of [375,1280]) {
  test(`상단 검색·선택·뒤로가기와 지도 단추 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({width,height:812}); await page.emulateMedia({ reducedMotion:"reduce" });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    const api = await openFinished(page, request, undefined, { intakeEvents:"off", intakeRoutes:"on" }); await tiles();
    await expect(toast(page,"계획 확인 화면이에요")).toHaveCount(0);
    await pin(page,"1. 경복궁 관람").dispatchEvent('click'); await mapSettled(page);
    const tools = page.getByRole("group",{name:"지도 단추"});
    const fold = tools.getByRole("button",{name:"지도 단추 펼치기"});
    await expect(fold.getByRole("img",{name:/거리 눈금/})).toBeVisible();
    await expect(fold).toContainText(/\d+(m|km)/);
    await expect(tools.locator('[class*=scaleBar]')).toHaveCount(0);
    await capture(page,`04-vertical-${width}`);
    const seam=page.locator('[data-insert-near] > button'); const seamName=await seam.getAttribute('aria-label');
    await seam.click();
    const search=page.getByRole('searchbox',{name:'장소 검색',exact:true});
    await expect(search).toBeFocused();
    expect(await search.evaluate(node=>Boolean(node.closest('[data-hide-brand]')))).toBe(true);
    await expect(page.getByRole('region',{name:'일정 추가 화면'}).getByRole('searchbox')).toHaveCount(0);
    await expect(page.getByRole('button',{name:'다시 제출',exact:true})).toHaveCount(0);
    for(let i=0;i<4;i++) await page.getByRole('button',{name:'목록 높이 바꾸기'}).press('ArrowUp');
    await search.fill('올리브영');
    const result=page.getByRole('list',{name:'장소 검색 결과'}).getByRole('button',{name:/올리브영 명동 플래그십/});
    await expect(result).toBeVisible(); await capture(page,`01-search-${width}`);
    await result.click();
    const form=page.getByRole('form',{name:'일정 추가',exact:true});
    await expect(form.getByLabel('일정 이름',{exact:true})).toHaveValue('올리브영 명동 플래그십');
    await expect(form.getByLabel('시작',{exact:true})).not.toHaveValue('');
    await capture(page,`02-selected-${width}`);
    await fold.click();
    await expect(tools).toHaveAttribute('data-layout','row');
    await expect.poll(()=>collisions(page)).toBe(0);
    await capture(page,`03-horizontal-${width}`);
    await page.getByRole('button',{name:'일정 추가 취소',exact:true}).click();
    await expect(search).toHaveCount(0);
    await expect(page.getByRole('button',{name:seamName!,exact:true})).toBeFocused();
    expect(await api.received('POST','/edits')).toHaveLength(0);
    await capture(page,`05-return-${width}`);
    await noHorizontalScroll(page);
  });
}

test('빈 배경의 오른쪽 스와이프만 추가를 취소하고 일차 전환 모션을 사용한다',async({page,request})=>{
  await page.setViewportSize({width:375,height:812});
  const api=await openFinished(page,request,undefined,{intakeEvents:'off'});
  await expect(toast(page,'계획 확인 화면이에요')).toHaveCount(0);
  await page.locator('[data-insert-near] > button').click();
  const screen=page.getByRole('region',{name:'일정 추가 화면'}), search=page.getByRole('searchbox',{name:'장소 검색'});
  const box=(await screen.boundingBox())!;
  // 세로로 읽는 동작은 취소하지 않는다.
  await drag(page,box.x+4,box.y+100,8,90); await expect(search).toBeVisible();
  // 입력칸에서 시작한 가로 드래그도 취소하지 않는다.
  const input=(await search.boundingBox())!;
  await drag(page,input.x+8,input.y+input.height/2,120); await expect(search).toBeVisible();
  await drag(page,box.x+4,box.y+100,160);
  await expect(search).toHaveCount(0);
  await expect(page.locator('[data-slide="prev"]')).toHaveCSS('animation-name',/slidePrev/);
  expect(await api.received('POST','/edits')).toHaveLength(0);
});

test('저장 중에는 뒤로가기·스와이프가 요청과 입력을 취소하지 않는다',async({page,request})=>{
  await page.setViewportSize({width:375,height:812});
  await openFinished(page,request,undefined,{intakeEvents:'off'});
  await page.locator('[data-insert-near] > button').click();
  await page.getByRole('searchbox',{name:'장소 검색'}).fill('올리브영');
  await page.getByRole('list',{name:'장소 검색 결과'}).getByRole('button',{name:/올리브영 명동 플래그십/}).click();
  let release!:()=>void; const wait=new Promise<void>(resolve=>{release=resolve;});
  await page.route(`**/v1/web/trip-intakes/${INTAKE}/edits`,async route=>{ await wait; await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({error:{code:'schedule_conflict',message:'앞뒤 일정을 확인해 주세요.'}})}); });
  const form=page.getByRole('form',{name:'일정 추가',exact:true});
  await form.getByRole('button',{name:'일정에 추가',exact:true}).click();
  const back=page.getByRole('button',{name:'일정 추가 취소',exact:true});
  await expect(back).toHaveAttribute('aria-disabled','true'); await back.dispatchEvent('click');
  const box=(await page.getByRole('region',{name:'일정 추가 화면'}).boundingBox())!;
  await drag(page,box.x+4,box.y+100,160); await expect(form).toBeVisible();
  release(); await expect(form.getByRole('alert')).toContainText('앞뒤 일정');
  await expect(back).toHaveAttribute('aria-disabled','false');
});

test('새 목업은 이번 촬영만 사용하며 두 화면 크기로 전환된다',async({page})=>{
  test.skip(!shots,'촬영 모음을 만들 때 확인합니다');
  await page.goto(pathToFileURL(resolve(shots!,'index.html')).href);
  await expect(page.getByRole('heading',{name:'일정 추가 · 상단 검색과 지도 단추',exact:true})).toBeVisible();
  const patterns=await page.locator('[data-shot]').evaluateAll(nodes=>nodes.map(node=>(node as HTMLElement).dataset.shot!));
  for(const pattern of patterns)for(const width of [375,1280])await access(resolve(shots!,`${pattern}-${width}.png`));
  await page.getByLabel('촬영 화면').selectOption('1280');
  await expect(page.locator('img').first()).toHaveAttribute('src',/1280\.png$/);
  await page.setViewportSize({width:375,height:812}); await noHorizontalScroll(page);
});

test('오른쪽 거리 칩은 단추 아래의 빈 높이에서 화면 끝에 붙고 번호와 거리가 구분된다',async({page,request})=>{
  await page.setViewportSize({width:375,height:812}); await openFinished(page,request);
  await expect(toast(page,'계획 확인 화면이에요')).toHaveCount(0);
  const tools=page.getByRole('group',{name:'지도 단추'});
  await tools.getByRole('button',{name:'지도 단추 펼치기'}).click();
  for(let i=0;i<3;i++){await tools.getByRole('button',{name:'확대',exact:true}).click();await page.waitForTimeout(350);}
  await tools.getByRole('button',{name:'지도 단추 접기'}).click();
  const map=page.getByRole('region',{name:'여행 지도'}), box=(await map.boundingBox())!;
  await drag(page,box.x+80,box.y+200,210); await expect(map).not.toHaveAttribute('data-moving','true');
  await expect.poll(()=>map.locator('[data-edge-chip]').evaluateAll(nodes=>{
    return nodes.some(node=>{const r=node.getBoundingClientRect(), map=node.parentElement!.getBoundingClientRect();return Math.abs(r.right-map.right)<1;});
  })).toBe(true);
  const chip=map.locator('[data-edge-chip]').first();
  await expect(chip.locator('[class*=edgeNumbers]')).toHaveCSS('border-radius','999px');
  await expect(chip.locator('small')).toHaveCSS('border-left-style','solid');
});
