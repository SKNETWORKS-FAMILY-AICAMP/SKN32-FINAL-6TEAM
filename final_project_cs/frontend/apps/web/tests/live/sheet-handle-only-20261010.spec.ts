import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { openFinished } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots = process.env.SHEET_HANDLE_SHOTS;
const handle = (page: Page) => page.getByRole('button', { name: '목록 높이 바꾸기' });
const panel = (page: Page) => page.locator('section[aria-labelledby="plan-check-sheet-title"]');
const footer = (page: Page) => page.locator('footer[class*=footer]');
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

async function prepare(page: Page) {
  await expect(page.getByRole('status').filter({ hasText: '계획 확인 화면이에요' })).toHaveCount(0);
  await page.mouse.move(0, 0);
}
async function capture(page: Page, name: string) {
  if (!shots) return;
  await mkdir(shots, { recursive: true });
  await expect(page.getByRole('region', { name: '여행 지도' })).not.toHaveAttribute('data-moving');
  const dates = page.locator('[role=tablist]');
  if (await dates.isVisible()) await expect(dates).toHaveCSS('opacity', '1');
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}
async function onlyHandle(page: Page) {
  await expect(page.locator('[data-sheet]')).toHaveAttribute('data-collapsed', 'true');
  await expect.poll(() => panel(page).evaluate(e => e.getBoundingClientRect().height)).toBe(44);
  await expect(handle(page)).toBeVisible();
  await expect(handle(page)).toHaveCSS('height', '44px');
  await expect(panel(page).getByRole('button')).toHaveCount(1);
  await expect(footer(page)).toHaveCSS('opacity', '0');
  await expect(footer(page)).toHaveAttribute('inert', '');
  await expect(footer(page)).toHaveAttribute('aria-hidden', 'true');
  // An idle timer or keyboard traversal must not bring the send control back.
  await page.waitForTimeout(1100);
  await expect(footer(page)).toHaveCSS('opacity', '0');
  await handle(page).focus(); await page.keyboard.press('Tab');
  expect(await footer(page).evaluate(e => e.contains(document.activeElement))).toBe(false);
  await noHorizontalScroll(page);
}
for (const width of [375, 1280]) {
  test(`끝까지 드래그하면 손잡이만 남고 다시 올리면 복원 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    const server = await openFinished(page, request, undefined, { intakeEvents: 'off' });
    await tiles(); await prepare(page);
    const before = (await server.log()).filter(e => e.method !== 'GET').length;
    const box = (await handle(page).boundingBox())!;
    await page.mouse.move(box.x + box.width / 2, box.y + 10); await page.mouse.down();
    await page.mouse.move(box.x + box.width / 2, 811, { steps: 12 });
    await expect(page.locator('[data-sheet]')).toHaveAttribute('data-collapsed', 'true');
    await page.mouse.up(); await onlyHandle(page); await page.mouse.move(0, 0);
    await capture(page, `collapsed-${width}`);
    const folded = (await handle(page).boundingBox())!;
    await page.mouse.move(folded.x + folded.width / 2, folded.y + 10); await page.mouse.down();
    await page.mouse.move(folded.x + folded.width / 2, folded.y - 330, { steps: 12 }); await page.mouse.up();
    await expect(page.locator('[data-sheet]')).not.toHaveAttribute('data-collapsed');
    await expect(panel(page).getByRole('article', { name: '경복궁 관람', exact: true })).toBeVisible();
    await expect(footer(page)).toHaveCSS('opacity', '1'); await expect(footer(page)).not.toHaveAttribute('inert');
    await capture(page, `restored-${width}`);
    expect((await server.log()).filter(e => e.method !== 'GET').length).toBe(before);
  });
  test(`클릭 최소 단계·키보드 하한·복귀가 같은 상태 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 }); await page.emulateMedia({ reducedMotion: 'reduce' });
    await openFinished(page, request, undefined, { intakeEvents: 'off' }); await prepare(page);
    await handle(page).click(); await handle(page).click();
    await expect(page.locator('[data-sheet]')).toHaveAttribute('data-sheet', 'peek'); await onlyHandle(page);
    await handle(page).focus(); await page.keyboard.press('ArrowDown'); await onlyHandle(page);
    await handle(page).focus();
    for (let i = 0; i < 5; i++) await page.keyboard.press('ArrowUp');
    await expect(panel(page).getByRole('article', { name: '경복궁 관람', exact: true })).toBeVisible();
    await expect(footer(page)).toHaveCSS('opacity', '1');
    for (let i = 0; i < 10; i++) await page.keyboard.press('ArrowDown');
    await onlyHandle(page); await handle(page).click();
    await expect(page.locator('[data-sheet]')).toHaveAttribute('data-sheet', 'half');
    await expect(footer(page)).toHaveCSS('opacity', '1');
  });
}
