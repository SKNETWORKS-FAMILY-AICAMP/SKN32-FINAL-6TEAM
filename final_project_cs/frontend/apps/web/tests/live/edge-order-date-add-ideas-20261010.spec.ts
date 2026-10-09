import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { head, openFinished, card } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots = process.env.EDGE_IDEAS_SHOTS;
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
async function prepare(page: Page) {
  await expect(page.getByRole('status').filter({ hasText: '계획 확인 화면이에요' })).toHaveCount(0);
  await page.mouse.move(0, 0);
}
async function capture(page: Page, name: string, pointer = true) {
  if (!shots) return;
  await mkdir(shots, { recursive: true });
  if (pointer) await page.mouse.move(0, 0);
  await page.screenshot({ path: `${shots}/${name}.png`, fullPage: true });
}
for (const width of [375, 1280]) {
  test(`좌우 순서·검정 번호·조작 중 거리 숨김 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    await openFinished(page, request, v => {
      v.review.items[1].place.latitude = 37.5796;
      v.review.items[1].place.longitude = 126.94;
      v.review.items[2].place.latitude = 37.5796;
      v.review.items[2].place.longitude = 127.02;
      for (let i = 3; i <= 4; i++) v.review.items.push({ ...v.review.items[2], id: `0-${i}`, index: i, title: `종로 일정 ${i}`, place: { ...v.review.items[2].place, longitude: 127.02 + i / 100000 } });
    }, { intakeEvents: 'off' });
    await tiles(); await prepare(page); await head(page, '경복궁 관람').click(); await prepare(page);
    const map = page.getByRole('region', { name: '여행 지도' });
    await page.getByRole('button', { name: '지도 단추 펼치기', exact: true }).click();
    for (let i = 0; i < 3; i++) {
      await page.getByRole('button', { name: '확대', exact: true }).click();
      await expect.poll(() => map.getAttribute('data-moving')).toBe(null);
    }
    await page.getByRole('button', { name: '지도 단추 접기', exact: true }).click();
    const chips = page.locator('[data-edge-chip]');
    await expect(chips.first()).toBeVisible();
    const sides = await chips.evaluateAll(es => es.map(e => ({ side: e.getAttribute('data-side'), x: e.getBoundingClientRect().x + e.getBoundingClientRect().width / 2, direction: getComputedStyle(e).flexDirection, children: Array.from(e.children).map(c => ({ tag: c.tagName, x: c.getBoundingClientRect().x })) })));
    expect(sides.some(s => s.side === 'left')).toBe(true);
    expect(sides.some(s => s.side === 'right')).toBe(true);
    await expect(chips.filter({ has: page.locator('svg.lucide-layers') })).toHaveCount(1);
    for (const side of sides) {
      const xs = side.children.map(c => c.x);
      expect(side.direction).toBe(side.side === 'left' ? 'row-reverse' : 'row');
      expect(xs[0] < xs[1] && xs[1] < xs[2]).toBe(side.side === 'right');
    }
    const fill = await chips.first().locator('span').evaluate(e => getComputedStyle(e).backgroundColor);
    expect(fill).toBe('rgb(32, 32, 32)');
    await expect(page.locator('[role=tablist]')).toHaveCSS('opacity', '1');
    await capture(page, `01-both-sides-${width}`);
    const box = (await map.boundingBox())!;
    await page.mouse.move(box.x + 110, box.y + 140); await page.mouse.down();
    await page.mouse.move(box.x + 140, box.y + 155, { steps: 5 });
    await expect(map).toHaveAttribute('data-moving', 'true'); await expect(chips.locator('small')).toHaveCount(0);
    await capture(page, `02-moving-${width}`, false); await page.mouse.up();
    await expect.poll(() => map.getAttribute('data-moving')).toBe(null);
    await expect(chips.first().locator('small')).toBeVisible(); await noHorizontalScroll(page);
  });
  test(`하루 일정도 날짜 표시·스크롤 중 숨김·정지 후 복귀·미선택 안내 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    await openFinished(page, request, undefined, { intakeEvents: 'off' }); await tiles(); await prepare(page);
    const strip = page.locator('[role="tablist"][aria-label="일차 고르기"]'), summary = page.locator('[data-map-summary]');
    await expect(strip).toHaveCSS('opacity', '1'); await expect(strip).toContainText('1일차');
    await expect(summary).toContainText('확인 필요 · 올리브영'); await capture(page, `03-date-summary-${width}`);
    await head(page, '경복궁 관람').click(); await prepare(page);
    await expect(summary).toHaveCount(0); await expect(page.locator('[class*=statusTools]')).toContainText('경복궁 관람');
    await head(page, '경복궁 관람').click(); await prepare(page); await expect(summary).toContainText('확인 필요');
    const body = page.locator('div[class*=sheetBody]'); await body.hover(); await page.mouse.wheel(0, 160);
    await expect(strip).toHaveCSS('opacity', '0'); await expect(strip).toHaveAttribute('inert', '');
    await expect(strip).toHaveCSS('opacity', '1'); await capture(page, `04-scrolled-date-${width}`); await noHorizontalScroll(page);
  });
  test(`일정 추가 네 배치안 비교 촬영 ${width}px`, async ({ page, request }) => {
    test.skip(!shots, '비교안은 촬영을 요청했을 때만 생성합니다');
    await page.setViewportSize({ width, height: 812 }); await page.emulateMedia({ reducedMotion: 'reduce' });
    const tiles = await useMapTiles(page);
    await openFinished(page, request, undefined, { intakeEvents: 'off' }); await tiles(); await prepare(page);
    for (let i = 0; i < 5; i++) await page.getByRole('button', { name: '목록 높이 바꾸기' }).press('ArrowUp');
    await head(page, '올리브영').click(); await prepare(page);
    const seam = page.locator('[data-insert-near]'), add = seam.getByRole('button'); await expect(add).toBeVisible();
    await expect.poll(() => page.locator('[role=tablist]').getAttribute('data-quiet')).toBe(null);
    await capture(page, `05-add-a-original-${width}`);
    const rail = await page.addStyleTag({ content: '[data-insert-point] > button {left:-39px!important}' });
    await capture(page, `06-add-b-rail-${width}`); await rail.evaluate(e => e.parentNode?.removeChild(e));
    const divider = await page.addStyleTag({ content: '[data-insert-near]::after {content:"";position:absolute;left:0;right:0;top:0;border-top:1px solid var(--color-border-strong);z-index:-2} [data-insert-near] > button::before {inset:7px!important;box-shadow:none!important}' });
    await capture(page, `07-add-c-divider-${width}`); await divider.evaluate(e => e.parentNode?.removeChild(e));
    const label = await add.getAttribute('aria-label');
    const footerAdd = page.getByRole('button', { name: '올리브영 다음 이동 전에 일정 추가', exact: true });
    const below = await page.addStyleTag({ content: '[data-insert-near] > button {opacity:0!important} [data-proposal-footer] {left:auto!important;right:0!important;width:118px!important;display:flex!important;justify-content:center;gap:4px;font:inherit;font-size:12px;opacity:1!important;pointer-events:auto!important} [data-proposal-footer]::before {inset:7px 0!important;border-radius:8px!important;box-shadow:none!important}' });
    await footerAdd.evaluate(e => { e.setAttribute('data-proposal-footer', 'true'); const text = document.createElement('span'); text.dataset.proposalLabel='true'; text.textContent='다음 일정 추가'; e.append(text); });
    await capture(page, `08-add-d-card-footer-${width}`);
    await footerAdd.locator('[data-proposal-label]').evaluate(e => e.remove()); await footerAdd.evaluate(e => e.removeAttribute('data-proposal-footer')); await below.evaluate(e => e.parentNode?.removeChild(e));
    await expect(add).toHaveAttribute('aria-label', label!); expect((await add.boundingBox())!.width).toBe(44);
    await noHorizontalScroll(page); await expect(card(page, '올리브영')).toBeVisible();
  });
  test(`확인할 내용이 없으면 되돌릴 수 있는 변경 내용을 안내 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    let clearNeeds = false;
    await openFinished(page, request, v => {
      if (clearNeeds) {
        for (const item of v.review.items) { item.status = 'keep'; item.rows = item.rows.map((row: Record<string, unknown>) => ({ ...row, result: 'ok' })); }
        for (const move of v.review.moves) { move.status = 'keep'; move.rows = move.rows.map((row: Record<string, unknown>) => ({ ...row, result: 'ok' })); }
      }
    }, { intakeEvents: 'off' }); await tiles(); await prepare(page);
    await page.route('**/v1/web/trip-intakes/*/edits', async route => {
      const response = await route.fetch(); const v = await response.json();
      for (const item of v.review.items) { item.status = 'keep'; item.rows = item.rows.map((row: Record<string, unknown>) => ({ ...row, result: 'ok' })); }
      for (const move of v.review.moves) { move.status = 'keep'; move.rows = move.rows.map((row: Record<string, unknown>) => ({ ...row, result: 'ok' })); }
      await route.fulfill({ response, json: v });
    });
    await page.getByRole('button', { name: '광장시장 수정', exact: true }).click();
    await page.getByText('직접 고치기 · 이름·날짜·시각·장소 없음').click();
    const editor = page.getByRole('form', { name: '「광장시장」 고치기' });
    await editor.getByLabel('일정 이름', { exact: true }).fill('광장시장 점심');
    clearNeeds = true;
    await editor.getByRole('button', { name: '저장', exact: true }).click();
    await expect(editor).toHaveCount(0); await prepare(page);
    // The change screen leaves this stop selected; closing it restores the unselected summary.
    const heading = head(page, '광장시장 점심');
    if (await heading.getAttribute('aria-expanded') === 'true') await heading.click();
    await expect(page.locator('[data-map-summary]')).toContainText(/변경됨|되돌리기 가능/);
    await expect(page.getByRole('button', { name: /^확인 필요 \d+곳$/ })).toHaveCount(0);
    await expect.poll(() => page.getByRole('region', { name: '여행 지도' }).getAttribute('data-moving')).toBe(null);
    await expect(page.locator('[role=tablist]')).toHaveCSS('opacity', '1');
    await expect(page.locator('[class*=mapChips]')).not.toHaveAttribute('data-muted', 'true');
    // Give the completed opacity transition a paint before capturing the restored labels.
    await page.waitForTimeout(250);
    await capture(page, `09-undo-summary-${width}`); await noHorizontalScroll(page);
  });
}
