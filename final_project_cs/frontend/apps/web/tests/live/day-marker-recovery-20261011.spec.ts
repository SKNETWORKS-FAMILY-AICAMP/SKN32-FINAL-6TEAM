import { expect, test, type Page } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
import { mockServer, noHorizontalScroll } from './helpers';
import { card, head, openFinished, type Json } from './plan-check-kit';
import { useMapTiles } from './capture-map-tiles';

const shots = process.env.DAY_MARKER_SHOTS;
const withDays = (v: Json) => v.review.items.push({ ...v.review.items[0], id: '0-3', index: 3, title: 'N서울타워', day: 2, date: '2026-10-02' });
const strip = (page: Page) => page.getByRole('tablist', { name: '일차 고르기', includeHidden: true });
async function aligned(page: Page) {
  await expect.poll(() => strip(page).evaluate(e => {
    const tab = e.querySelector('[aria-selected=true]'), marker = e.querySelector('[class*=dayMarker]');
    if (!tab || !marker) return Infinity;
    const t = tab.getBoundingClientRect(), m = marker.getBoundingClientRect();
    return Math.max(Math.abs(t.left-m.left), Math.abs(t.right-m.right), Math.abs(t.top-m.top), Math.abs(t.bottom-m.bottom));
  }), { timeout: 4000 }).toBeLessThan(1);
  await expect(strip(page).locator('[data-lit]')).toHaveCount(1);
  await expect(strip(page).locator('[aria-selected=true]')).toHaveAttribute('data-lit', '');
}
async function finger(page: Page, type: string, x: number, id = 9) {
  await page.locator('div[class*=sheetBody]').evaluate((e, p) => e.dispatchEvent(new PointerEvent(p.type, {
    bubbles: true, pointerId: p.id, pointerType: 'touch', isPrimary: true, clientX: p.x, clientY: 550, button: 0, buttons: p.type === 'pointermove' || p.type === 'pointerdown' ? 1 : 0,
  })), { type, x, id });
}
test.beforeEach(async ({ request }) => { await mockServer(request).reset(); });
for (const width of [375, 1280]) {
  test(`수정안 왕복·직접 수정 복귀 시 선택 배경 전체 정렬 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    const tiles = shots ? await useMapTiles(page) : async () => {};
    await page.route('**/autofix', async route => {
      const response = await route.fetch(), result = await response.json();
      if (result.view?.review && !result.view.review.items.some((i: Json) => i.id === '0-3')) withDays(result.view);
      await route.fulfill({ response, json: result });
    });
    await openFinished(page, request, withDays, { intakeEvents: 'off' }); await tiles();
    await expect(page.getByRole('status').filter({ hasText: '계획 확인 화면이에요' })).toHaveCount(0);
    await page.getByRole('tab', { name: /^2일차/ }).click(); await aligned(page);
    await page.getByRole('button', { name: /^전체 자동 추천/ }).click();
    await expect(page.getByRole('group', { name: '보는 일정' })).toBeVisible(); await aligned(page);
    await page.getByRole('button', { name: '1. 변경 전 일정', exact: true }).click(); await aligned(page);
    await page.getByRole('button', { name: '2. 수정안', exact: true }).click(); await aligned(page);
    await page.getByRole('button', { name: '1. 변경 전 일정', exact: true }).click();
    await head(page, 'N서울타워').click();
    await page.getByRole('button', { name: 'N서울타워 수정', exact: true }).click();
    await expect(strip(page)).toHaveCount(0);
    await page.getByRole('button', { name: '바꾸기 그만두기', exact: true }).click(); await aligned(page);
    if (shots) {
      await expect(page.getByRole('status').filter({ hasText: '확인이 필요한 일정' })).toHaveCount(0);
      await mkdir(shots, { recursive: true }); await page.screenshot({ path: `${shots}/date-return-${width}.png`, fullPage: true });
    }
    await noHorizontalScroll(page);
  });
  test(`수정안에서 보던 날짜가 없어지면 첫 유효 날짜로 복귀 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await openFinished(page, request, withDays, { intakeEvents: 'off' });
    await page.getByRole('tab', { name: /^2일차/ }).click();
    await page.getByRole('button', { name: /^전체 자동 추천/ }).click();
    await expect(page.getByRole('group', { name: '보는 일정' })).toBeVisible(); await aligned(page);
    await expect(strip(page).locator('[aria-selected=true]')).toContainText('1일차');
    await page.getByRole('button', { name: '1. 변경 전 일정', exact: true }).click(); await aligned(page);
    await expect(strip(page).locator('[aria-selected=true]')).toContainText('2일차');
  });
  test(`탭 너비 변경·숨김 복원·화면 크기 변경 시 재측정 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await openFinished(page, request, withDays, { intakeEvents: 'off' });
    await page.getByRole('tab', { name: /^2일차/ }).click(); await aligned(page);
    // Review badge/font changes alter preceding tab widths without changing the selected day.
    await strip(page).getByRole('tab').nth(1).evaluate(e => { e.style.paddingInline = '25px'; }); await aligned(page);
    await strip(page).evaluate(e => { (e as HTMLElement).style.display = 'none'; });
    await page.setViewportSize({ width: width === 375 ? 514 : 900, height: 812 });
    await strip(page).evaluate(e => { (e as HTMLElement).style.removeProperty('display'); }); await aligned(page);
    await page.setViewportSize({ width, height: 812 }); await aligned(page);
  });
  test(`중간 스와이프 취소·확정·빠른 연속 전환·움직임 줄이기 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 });
    await openFinished(page, request, withDays, { intakeEvents: 'off' });
    const bodyWidth = await page.locator('div[class*=sheetBody]').evaluate(e => e.clientWidth);
    await finger(page, 'pointerdown', bodyWidth * .8);
    await finger(page, 'pointermove', bodyWidth * .65); await page.waitForTimeout(100);
    await finger(page, 'pointercancel', bodyWidth * .65); await aligned(page);
    await expect(page.getByRole('tab', { name: /^1일차/ })).toHaveAttribute('aria-selected', 'true');
    for (const direction of [-1, 1, -1]) {
      const x = direction === -1 ? bodyWidth * .8 : bodyWidth * .2;
      await finger(page, 'pointerdown', x); await finger(page, 'pointermove', x + direction * bodyWidth * .35);
      await finger(page, 'pointerup', x + direction * bodyWidth * .35); await page.waitForTimeout(300); await aligned(page);
    }
    await page.emulateMedia({ reducedMotion: 'reduce' });
    for (const name of [/^1일차/, /^2일차/, /^1일차/]) {
      await page.getByRole('tab', { name }).click(); await aligned(page);
    }
    const duration = await strip(page).locator('[class*=dayMarker]').evaluate(e => parseFloat(getComputedStyle(e).transitionDuration));
    expect(duration).toBeLessThanOrEqual(.00001);
  });
  test(`문제 항목 배치 비교 촬영·좁은 카드 줄바꿈 ${width}px`, async ({ page, request }) => {
    await page.setViewportSize({ width, height: 812 }); await page.emulateMedia({ reducedMotion: 'reduce' });
    await openFinished(page, request, undefined, { intakeEvents: 'off' });
    const target = card(page, '올리브영');
    await target.evaluate(e => e.scrollIntoView({ block: 'center', inline: 'nearest' }));
    await expect(target.locator('[class*=need] > b')).toHaveCount(2);
    if (shots) { await mkdir(shots, { recursive: true }); await target.screenshot({ path: `${shots}/status-current-${width}.png` }); }
    // Proposal only: scoped browser style; production card styles are unchanged.
    await target.evaluate(e => {
      const note = e.querySelector<HTMLElement>('[class*=cardFootNote]')!, tools = e.querySelector<HTMLElement>('[class*=cardFootTools]')!;
      const foot = note.parentElement!;
      note.style.setProperty('flex', '0 1 auto', 'important'); note.style.width = 'max-content'; note.style.marginLeft = 'auto';
      tools.style.marginLeft = '0'; foot.style.alignItems = 'center'; foot.style.columnGap = '12px';
    });
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    const geometry = await target.evaluate(e => {
      const items = Array.from(e.querySelectorAll('[class*=need] > b')).map(n => n.parentElement!.getBoundingClientRect());
      const pill = e.querySelector('[data-card-footer-status]')!.getBoundingClientRect(), r = e.getBoundingClientRect();
      return { gap: pill.left - items.at(-1)!.right, right: r.right - pill.right, fits: items.every(i => i.left >= r.left && i.right <= r.right) };
    }); expect(geometry.gap).toBeGreaterThanOrEqual(12); expect(geometry.gap).toBeLessThan(13); expect(geometry.right).toBeGreaterThan(10); expect(geometry.fits).toBe(true);
    if (shots) await target.screenshot({ path: `${shots}/status-grouped-${width}.png` });
    await target.evaluate(e => { e.style.width = '220px'; });
    const fits = await target.evaluate(e => e.scrollWidth <= e.clientWidth); expect(fits).toBe(true);
    await noHorizontalScroll(page);
  });
}
