import { expect, test, type Locator, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { openFinished } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots = process.env.EMPTY_MAP_SHOTS;
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
async function capture(page: Page, name: string) {
  if (!shots) return;
  await mkdir(shots, { recursive: true }); await page.mouse.move(0, 0);
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}
async function notCovered(page: Page, notice: Locator) {
  await expect(notice).toBeVisible();
  const box = (await notice.boundingBox())!;
  expect(await notice.evaluate(e => {
    const b = e.getBoundingClientRect();
    return [0.15, 0.5, 0.85].every(ratio => {
      const hit = document.elementFromPoint(b.x + b.width * ratio, b.y + b.height / 2);
      // Notices do not intercept map gestures; check which foreground layer is hit.
      return !hit?.closest('header:not([class*=sheetHead]), [data-map-controls], button[class*=handle]');
    });
  })).toBe(true);
  expect(box.y).toBeGreaterThanOrEqual(70);
  expect(box.x).toBeGreaterThanOrEqual(0);
  expect(box.x + box.width).toBeLessThanOrEqual(page.viewportSize()!.width);
}
for (const width of [375, 1280]) {
  test(`좌표0개 안내가 메뉴·도구·목록에 가리지 않고 좌표 복원 시 해제 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    let missing = true;
    const server = await openFinished(page, request, view => {
      for (let i = 3; i < 8; i++) view.review.items.push({ ...view.review.items[2], id: `0-${i}`, index: i, title: `서울 일정 ${i + 1}` });
      if (missing) for (const item of view.review.items) { item.place.latitude = null; item.place.longitude = null; }
    }, { intakeEvents: 'off' }, false);
    const writesBefore = (await server.log()).filter(e => e.method !== 'GET').length;
    await tiles();
    await expect(page.getByRole('status').filter({ hasText: '계획 확인 화면이에요' })).toHaveCount(0);
    const notice = page.locator('[data-empty-map-notice]:visible');
    await expect(notice).toHaveCount(1); await expect(notice).toHaveAttribute('role', 'status');
    await notCovered(page, notice);
    const controls = page.getByRole('group', { name: '지도 단추' });
    await controls.getByRole('button', { name: '지도 단추 펼치기', exact: true }).click();
    const n = (await notice.boundingBox())!, c = (await controls.boundingBox())!;
    expect(Math.min(n.x+n.width,c.x+c.width)-Math.max(n.x,c.x)).toBeLessThanOrEqual(0);
    await notCovered(page, notice); await capture(page, `empty-map-half-${width}`);
    const handle = page.getByRole('button', { name: '목록 높이 바꾸기' });
    await handle.click();
    await expect(page.locator('[data-sheet]')).toHaveAttribute('data-empty-map-in-head', 'true');
    await expect(notice).toHaveCount(1); await expect(notice).toContainText('일정에서 장소를 수정');
    await notCovered(page, notice);
    const dates = page.locator('[role=tablist]');
    await expect(dates).toHaveCSS('opacity', '1');
    expect((await dates.boundingBox())!.height).toBeGreaterThanOrEqual(32);
    expect((await dates.boundingBox())!.y).toBeGreaterThanOrEqual((await notice.boundingBox())!.y + (await notice.boundingBox())!.height);
    const y = (await notice.boundingBox())!.y;
    const body = page.locator('div[class*=sheetBody]'); await body.hover(); await page.mouse.wheel(0, 220);
    await expect.poll(() => body.evaluate(e => e.scrollTop)).toBeGreaterThan(100);
    expect((await notice.boundingBox())!.y).toBe(y);
    await expect(page.locator('[role=tablist]')).toHaveCSS('opacity', '1');
    await capture(page, `empty-map-full-${width}`);
    await handle.click(); await expect(page.locator('[data-sheet]')).toHaveAttribute('data-collapsed', 'true');
    await expect(notice).toHaveCount(1); await notCovered(page, notice);
    await capture(page, `empty-map-collapsed-${width}`);
    expect((await server.log()).filter(e => e.method !== 'GET').length).toBe(writesBefore);
    missing = false; await page.reload();
    await expect(page.locator('[data-pin-body]').first()).toBeVisible();
    await expect(page.locator('[data-empty-map-notice]')).toHaveCount(0);
    await noHorizontalScroll(page);
  });
}
