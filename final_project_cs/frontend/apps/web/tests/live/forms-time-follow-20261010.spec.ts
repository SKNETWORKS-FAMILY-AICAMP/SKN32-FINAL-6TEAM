import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { openFinished, head, INTAKE } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots = process.env.FORMS_FOLLOW_SHOTS;
const tileWaits = new WeakMap<Page, () => Promise<void>>();
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
async function ready(page: Page) {
  await expect(page.getByRole('status').filter({ hasText: '계획 확인 화면이에요' })).toHaveCount(0);
}
async function capture(page: Page, name: string) {
  if (!shots) return;
  await mkdir(shots, { recursive: true }); await page.mouse.move(0, 0); await ready(page);
  const close = page.getByRole('status').getByRole('button', { name: '닫기', exact: true });
  if (await close.count()) await close.click();
  await page.waitForTimeout(220);
  await expect(page.getByRole('region', { name: '여행 지도', exact: true })).not.toHaveAttribute('data-moving');
  await tileWaits.get(page)?.();
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}
for (const width of [375, 1280]) {
  test(`시각은 펼침·검토·되돌리기 상태에만 따라온다 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 }); await page.emulateMedia({ reducedMotion: 'reduce' });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    tileWaits.set(page, tiles);
    await openFinished(page, request, undefined, { intakeEvents: 'off' }); await tiles(); await ready(page);
    const row = (title: string) => page.locator('li[data-type=item]').filter({ has: page.getByRole('article', { name: title, exact: true }) });
    const time = (title: string) => row(title).locator(':scope > button').first();
    for (const title of ['경복궁 관람', '광장시장']) {
      await expect(time(title)).toHaveCSS('position', 'relative');
      await expect(row(title)).not.toHaveAttribute('data-time-follow');
    }
    await expect(time('올리브영')).toHaveCSS('position', 'sticky');
    await head(page, '경복궁 관람').click(); await expect(time('경복궁 관람')).toHaveCSS('position', 'sticky');
    const scroll = page.locator('div[class*=sheetBody]');
    const original = await time('경복궁 관람').boundingBox();
    await scroll.evaluate(e => { e.scrollTop += 140; });
    const followed = await time('경복궁 관람').boundingBox();
    expect(followed!.y).toBeGreaterThan(original!.y - 140 + 8);
    await capture(page, `expanded-time-${width}`);
    await head(page, '경복궁 관람').dispatchEvent('click');
    await expect(time('경복궁 관람')).toHaveCSS('position', 'relative');
    await scroll.evaluate(e => { e.scrollTop = 0; });
    await page.getByRole('button', { name: '경복궁 관람 삭제', exact: true }).click();
    await expect(page.getByRole('button', { name: '경복궁 관람 삭제 되돌리기', exact: true })).toBeVisible();
    await expect(time('경복궁 관람')).toHaveCSS('position', 'sticky');
    await page.getByRole('button', { name: '경복궁 관람 삭제 되돌리기', exact: true }).click();
    await expect(time('경복궁 관람')).toHaveCSS('position', 'relative');
    await capture(page, `collapsed-time-${width}`); await noHorizontalScroll(page);
  });

  test(`직접 수정은 장소 입력 중복 없이 원래 장소와 거절된 초안을 유지한다 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    tileWaits.set(page, tiles);
    const api = await openFinished(page, request, undefined, { intakeEvents: 'off' }); await tiles(); await ready(page);
    await page.getByRole('button', { name: '광장시장 수정', exact: true }).click();
    await page.getByText('직접 고치기 · 이름·날짜·시각·장소 없음').click();
    const form = page.getByRole('form', { name: '「광장시장」 고치기' });
    await expect(page.getByRole('searchbox')).toHaveCount(1); await expect(form.getByRole('searchbox')).toHaveCount(0);
    await expect(form).not.toContainText('저장하면 서버가');
    await form.getByLabel('일정 이름', { exact: true }).fill('광장시장 점심');
    if (shots) for (let i=0; i<5; i++) await page.getByRole('button', { name: '목록 높이 바꾸기' }).press('ArrowUp');
    await capture(page, `edit-${width}`);
    let payload: unknown;
    await page.route(`**/v1/web/trip-intakes/${INTAKE}/edits`, async route => {
      payload = route.request().postDataJSON();
      await route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ error: { code: 'schedule_conflict', message: '앞뒤 일정을 확인해 주세요.' } }) });
    });
    await form.getByRole('button', { name: '저장', exact: true }).click();
    await expect(form.getByRole('alert')).toContainText('앞뒤 일정');
    await expect(form.getByLabel('일정 이름', { exact: true })).toHaveValue('광장시장 점심');
    expect(JSON.stringify(payload)).toContain('광장시장 점심'); expect(JSON.stringify(payload)).not.toContain('"field":"items[2].place"');
    expect(await api.received('POST', '/edits')).toHaveLength(0); await noHorizontalScroll(page);
  });

  test(`일정 추가는 검색 초점으로 열고 검색·지우기·선택 후에도 초안을 보존한다 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 }); await page.emulateMedia({ reducedMotion: 'reduce' });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    tileWaits.set(page, tiles);
    const api = await openFinished(page, request, undefined, { intakeEvents: 'off' }); await tiles(); await ready(page);
    const add = page.locator('[data-insert-near] > button'), label = (await add.getAttribute('aria-label'))!;
    const before = (await api.log()).length;
    await add.click();
    const search = page.getByRole('searchbox', { name: '장소 검색', exact: true });
    const form = page.getByRole('form', { name: '일정 추가', exact: true });
    await expect(form).toBeVisible(); await expect(search).toBeFocused();
    await expect(page.locator('[data-hide-brand]')).toHaveAttribute('data-open');
    await expect(page.getByText('검색 결과에서 방문할 장소를 골라 주세요.')).toHaveCount(0);
    expect((await api.log()).slice(before).filter(e => e.path.includes('/places'))).toHaveLength(0);
    for (let i=0; i<4; i++) await page.getByRole('button', { name: '목록 높이 바꾸기' }).press('ArrowUp');
    const controls = page.getByRole('group', { name: '지도 단추' }), fold = controls.locator('button[aria-expanded]');
    await expect(controls).toHaveAttribute('data-direction', 'row');
    const geometry = () => fold.evaluate(e => {
      const r = e.getBoundingClientRect(), a = e.querySelector('[class*=foldArrow]')!.getBoundingClientRect();
      const m = e.querySelector<SVGSVGElement>('[class*=foldArrow] svg')!.getScreenCTM()!;
      const start = new DOMPoint(9,12).matrixTransform(m), tip = new DOMPoint(15,12).matrixTransform(m);
      return { x:a.x+a.width/2-r.x, y:a.y+a.height/2-r.y, dx:tip.x-start.x };
    });
    await expect(fold).toHaveAttribute('aria-expanded','false');
    const closed = await geometry(); expect(closed.dx).toBeLessThan(-3);
    await search.focus();
    await capture(page, `add-initial-${width}`);
    await fold.click(); await expect(fold).toHaveAttribute('aria-expanded','true');
    const opened = await geometry(); expect(opened.dx).toBeGreaterThan(3);
    expect(opened.x).toBe(closed.x); expect(opened.y).toBe(closed.y);
    await capture(page, `add-map-open-${width}`);
    await fold.click(); await search.focus();
    await form.getByLabel('일정 이름', { exact: true }).fill('종로에서 잠깐 쇼핑');
    await search.fill('올리브영'); await expect(form).toHaveCount(0);
    const result = page.getByRole('list', { name: '장소 검색 결과' }).getByRole('button', { name: /올리브영 명동 플래그십/ });
    await expect(result).toBeVisible(); await capture(page, `add-search-${width}`);
    await page.getByRole('button', { name: '검색어 지우기', exact: true }).click();
    await expect(form.getByLabel('일정 이름', { exact: true })).toHaveValue('종로에서 잠깐 쇼핑');
    await search.fill('올리브영'); await result.click();
    await expect(form.getByLabel('일정 이름', { exact: true })).toHaveValue('종로에서 잠깐 쇼핑');
    await expect(page.getByText('올리브영 명동 플래그십', { exact: true })).toBeVisible();
    await capture(page, `add-selected-${width}`);
    await page.getByRole('button', { name: '일정 추가 취소', exact: true }).click();
    await expect(page.getByRole('button', { name: label, exact: true })).toBeFocused();
    expect(await api.received('POST', '/edits')).toHaveLength(0); await noHorizontalScroll(page);
  });

  test(`추가 입력 검증과 검색 초점·실제 선택 장소 저장 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    const api = await openFinished(page, request, undefined, { intakeEvents: 'off' }); await ready(page);
    await page.locator('[data-insert-near] > button').click();
    const form = page.getByRole('form', { name: '일정 추가', exact: true });
    const title = form.getByLabel('일정 이름', { exact: true });
    const submit = form.getByRole('button', { name: '일정에 추가', exact: true });
    await expect(submit).toBeEnabled(); await submit.click(); await expect(title).toBeFocused();
    await title.fill('종로 쇼핑'); await submit.click();
    const search = page.getByRole('searchbox', { name: '장소 검색', exact: true });
    await expect(search).toBeFocused(); expect(await api.received('POST', '/edits')).toHaveLength(0);
    await search.fill('올리브영');
    await page.getByRole('list', { name: '장소 검색 결과' }).getByRole('button', { name: /올리브영 명동 플래그십/ }).click();
    await submit.click();
    await expect.poll(async () => (await api.received('POST', '/edits')).length).toBe(1);
    const payload = JSON.stringify((await api.received('POST', '/edits'))[0].body);
    expect(payload).toContain('종로 쇼핑'); expect(payload).toContain('올리브영 명동 플래그십');
    expect(payload).toContain('latitude'); expect(payload).toContain('longitude');
    await expect(form).toHaveCount(0);
  });
}
