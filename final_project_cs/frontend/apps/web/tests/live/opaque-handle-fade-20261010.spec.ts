import { expect, test, type Page } from '@playwright/test';
import sharp from 'sharp';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { openFinished, head } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots = process.env.OPAQUE_HANDLE_SHOTS;
const handle = (page: Page) => page.getByRole('button', { name: '목록 높이 바꾸기' });
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

async function idle(page: Page) {
  await expect(page.getByRole('status').filter({ hasText: '계획 확인 화면이에요' })).toHaveCount(0);
  const tabs = page.locator('[role=tablist]');
  if (await tabs.count()) await expect(tabs).toHaveCSS('opacity', '1');
}
async function capture(page: Page, name: string) {
  if (!shots) return;
  await mkdir(shots, { recursive: true }); await page.mouse.move(0, 0); await idle(page);
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}
for (const width of [375, 1280]) {
  test(`손잡이는 완전히 가리고 그 아래 목록은 점진적으로 보임 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 }); await page.emulateMedia({ reducedMotion: 'reduce' });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    const api = await openFinished(page, request, undefined, { intakeEvents: 'off' });
    await tiles(); await idle(page);
    const scroll = page.locator('div[class*=sheetBody]'), button = scroll.locator('#plan-recommend-all');
    const h = (await handle(page).boundingBox())!;
    const align = async (offset: number) => {
      await scroll.evaluate((e, y) => {
        const b = e.querySelector('#plan-recommend-all')!;
        e.scrollTop += b.getBoundingClientRect().bottom - y;
      }, h.y + h.height + offset);
    };
    await align(32); await capture(page, `approach-${width}`);
    await align(12); await capture(page, `fading-${width}`);
    await align(-2); await capture(page, `hidden-${width}`);
    expect((await button.boundingBox())!.y + (await button.boundingBox())!.height).toBeLessThan(h.y + h.height);
    await expect(handle(page)).toHaveCSS('opacity', '1');
    await expect(handle(page)).toHaveCSS('mask-image', 'none');
    // A colour probe in the real scroll layer checks browser compositing, not just CSS text.
    await scroll.evaluate(e => { e.style.backgroundColor = 'rgb(255, 0, 255)'; });
    const x = Math.round(h.x + 10), start = Math.round(h.y + h.height - 3);
    const { data, info } = await sharp(await page.screenshot({ clip: { x, y: start, width: 1, height: 42 } })).removeAlpha().raw().toBuffer({ resolveWithObject: true });
    const green = (y: number) => data[y * info.channels + 1];
    expect(green(0)).toBeGreaterThan(245); // No list layer shows anywhere inside the handle.
    expect(green(5)).toBeGreaterThan(green(13));
    expect(green(13)).toBeGreaterThan(green(23));
    expect(green(23)).toBeGreaterThan(green(38));
    expect(green(38)).toBeLessThan(10);
    await scroll.evaluate(e => { e.style.backgroundColor = ''; });
    await head(page, '경복궁 관람').click();
    await scroll.evaluate(e => {
      const title = e.querySelector('article [class*=cardTitle]')!;
      e.scrollTop += title.getBoundingClientRect().top - e.getBoundingClientRect().top - 34;
    });
    await capture(page, `card-${width}`);
    await handle(page).focus(); await page.keyboard.press('ArrowUp');
    await expect(handle(page)).toBeFocused(); await noHorizontalScroll(page);
    expect(await api.received('POST', '/edits')).toHaveLength(0);
  });
}
