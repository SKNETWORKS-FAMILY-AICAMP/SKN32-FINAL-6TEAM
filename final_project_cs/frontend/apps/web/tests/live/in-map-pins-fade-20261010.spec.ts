import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { openFinished, head } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots = process.env.IN_MAP_FADE_SHOTS;
const map = (page: Page) => page.getByRole('region', { name: '여행 지도', exact: true });
const marker = (page: Page, n: string) => page.locator('.leaflet-marker-icon').filter({ has: page.locator(`[data-pin-label="${n}"]`) });
const body = (page: Page, n: string) => marker(page, n).locator('[data-pin-body]');
const handle = (page: Page) => page.getByRole('button', { name: '목록 높이 바꾸기' });
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });

async function idle(page: Page) {
  await expect(map(page)).not.toHaveAttribute('data-moving');
  await expect(page.getByRole('status').filter({ hasText: '계획 확인 화면이에요' })).toHaveCount(0);
}
async function capture(page: Page, name: string) {
  if (!shots) return;
  await mkdir(shots, { recursive: true }); await page.mouse.move(0, 0); await idle(page);
  await expect(page.locator('[role=tablist]')).toHaveCSS('opacity', '1');
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}
async function anchor(page: Page, n: string) {
  return marker(page, n).evaluate(e => { const r = e.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; });
}
async function panAnchor(page: Page, n: string, x: number, y: number) {
  const box = (await map(page).boundingBox())!, at = await anchor(page, n);
  const dx = box.x + x - at.x, dy = box.y + y - at.y;
  const start = await map(page).evaluate((element, delta) => {
    const r = element.getBoundingClientRect();
    for (let y = r.bottom - 86; y > r.top + 75; y -= 16) for (let x = r.left + 12; x < r.right - 12; x += 16) {
      if (x + delta.dx < 1 || x + delta.dx > innerWidth - 1 || y + delta.dy < 1 || y + delta.dy > innerHeight - 1) continue;
      const hit = document.elementFromPoint(x, y);
      if (hit && element.contains(hit) && !hit.closest('button,[data-pin-body]')) return { x, y };
    }
    throw new Error('지도 드래그를 시작할 빈 공간이 없습니다');
  }, { dx, dy });
  await page.mouse.move(start.x, start.y); await page.mouse.down();
  await page.mouse.move(start.x + dx, start.y + dy, { steps: 12 });
  await page.waitForTimeout(220); await page.mouse.up(); await idle(page);
}

for (const width of [375, 1280]) {
  test(`지도 안 밀집 마커는 개별 표시·점선 연결·밖으로 나갈 때만 칩 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 }); await page.emulateMedia({ reducedMotion: 'reduce' });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    const server = await openFinished(page, request, v => {
      const first = v.review.items[0];
      v.review.items[1].place = { ...first.place, latitude: first.place.latitude + .00001, longitude: first.place.longitude + .00001 };
      for (let i = 3; i <= 4; i++) v.review.items.push({ ...first, id: `0-${i}`, index: i, title: `종로 일정 ${i}`, place: { ...first.place, latitude: first.place.latitude + i / 100000 } });
    }, { intakeEvents: 'off' });
    await tiles(); await idle(page);
    const writes = (await server.log()).filter(e => e.method !== 'GET').length;
    const r = (await map(page).boundingBox())!;
    await panAnchor(page, '1', r.width / 2, 12);
    const a = await anchor(page, '1'); expect(a.y - r.y).toBeGreaterThanOrEqual(0); expect(a.y - r.y).toBeLessThan(64);
    for (const n of ['1', '2', '4', '5']) {
      await expect(body(page, n)).toBeVisible(); await expect(marker(page, n)).not.toHaveAttribute('aria-hidden', 'true');
      await expect(marker(page, n).locator('[data-pin-body]')).toHaveText(n);
    }
    const chips = page.locator('[data-edge-chip]');
    for (const n of ['1', '2', '4', '5']) expect(await chips.evaluateAll((es, label) => es.some(e => new RegExp(`(?:^|\\D)${label}번`).test(e.getAttribute('aria-label') ?? '')), n)).toBe(false);
    const bodies = await page.locator('[data-pin-body]').evaluateAll(es => es.filter(e => getComputedStyle(e).visibility !== 'hidden' && !e.closest('[aria-hidden=true]')).map(e => { const r = e.getBoundingClientRect(); return { x:r.x,y:r.y,right:r.right,bottom:r.bottom }; }));
    bodies.forEach((b, i) => bodies.slice(i+1).forEach(c => expect(Math.min(b.right,c.right) <= Math.max(b.x,c.x) || Math.min(b.bottom,c.bottom) <= Math.max(b.y,c.y)).toBe(true)));
    const leaders = page.locator('[data-pin-leader]').filter({ visible: true });
    await expect(leaders.first()).toBeVisible();
    for (const line of await leaders.locator('line').all()) await expect(line).toHaveAttribute('stroke-dasharray', '2 4');
    await capture(page, `inside-top-${width}`);
    await panAnchor(page, '1', r.width / 2, -60);
    await expect(chips.filter({ has: page.locator('svg.lucide-layers') })).toHaveCount(1);
    await expect(marker(page, '1')).toHaveAttribute('aria-hidden', 'true');
    await expect(chips.first().locator(':scope > span')).toHaveCSS('background-color', 'rgb(32, 32, 32)');
    await capture(page, `outside-${width}`);
    await panAnchor(page, '1', 8, 110);
    for (const n of ['1', '2', '4', '5']) await expect(body(page, n)).toBeVisible();
    await expect(marker(page, '1')).not.toHaveAttribute('aria-hidden', 'true');
    await capture(page, `inside-edge-${width}`); await noHorizontalScroll(page);
    expect((await server.log()).filter(e => e.method !== 'GET').length).toBe(writes);
  });

  test(`상단 내용 페이드와 날짜·손잡이·최소 접힘 유지 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    await openFinished(page, request, undefined, { intakeEvents: 'off' }); await tiles(); await idle(page);
    await head(page, '경복궁 관람').click(); await idle(page);
    const scroll = page.locator('div[class*=sheetBody]');
    await expect(scroll).toHaveCSS('mask-image', /linear-gradient.*22px.*54px/);
    await expect(handle(page)).toHaveCSS('mask-image', 'none');
    await expect(page.locator('[role=tablist]')).toHaveCSS('mask-image', 'none');
    // Place the actual title across the fading boundary; it must scroll under the handle.
    await scroll.evaluate(e => { const title = e.querySelector('article h3') ?? e.querySelector('article [class*=cardHead]'); if (!title) throw Error('카드 제목 없음'); const delta = title.getBoundingClientRect().top - e.getBoundingClientRect().top + 12; e.scrollTop += delta; });
    await expect.poll(() => scroll.evaluate(e => e.scrollTop)).toBeGreaterThan(50);
    await idle(page); await capture(page, `fade-${width}`);
    await expect(page.locator('[role=tablist]')).toHaveCSS('opacity', '1');
    await handle(page).focus();
    for (let i = 0; i < 10; i++) await page.keyboard.press('ArrowDown');
    await expect(page.locator('[data-sheet]')).toHaveAttribute('data-collapsed', 'true');
    await expect(handle(page)).toBeVisible(); await expect(page.locator('footer[class*=footer]')).toHaveAttribute('inert', '');
    await handle(page).click(); await expect(page.locator('[data-sheet]')).not.toHaveAttribute('data-collapsed');
    await expect(scroll).toHaveCSS('mask-image', /linear-gradient.*22px.*54px/); await noHorizontalScroll(page);
  });
}
