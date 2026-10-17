import { test, expect } from '@playwright/test';
import { createDemoSnapshot } from '../../src/lib/demo/fixtures';

for (const width of [1280, 375]) test(`일정 옆 검토 결과·실제와 모의·미판정 구별 (${width}px)`, async ({ page }, testInfo) => {
  await page.setViewportSize({ width, height: 900 });
  await page.clock.install({ time: new Date('2026-10-17T06:00:00Z') });
  const writes: string[] = [];
  const scopes = ['trip', 'day', 'item', 'none', 'unassessed', 'item', 'none', 'unassessed'];
  const records = scopes.map((scope, index) => ({
    id: `review-${index}`, received_at: '2026-10-17T05:00:00Z', mode: 'actual', record_type: 'api_check',
    category: 'disaster_msg', status: index === 4 ? 'failed' : 'ok', source: 'disaster_msg',
    trip_id: index === 6 ? null : 'review-trip', target_title: `검토 일정 ${index}`, stage: 'schedule',
    payload: {}, regions: [],
    impact: index === 7 ? undefined : { scope, label: scope, summary: '[mock 서버 시험] 저장된 영향 판정',
      affects_itinerary: index < 3, target_mode: index === 5 ? 'simulation' : index === 6 ? null : 'actual' },
  }));
  await page.route('**/admin/api/**', async route => {
    const url = new URL(route.request().url());
    if (route.request().method() !== 'GET') writes.push(url.pathname);
    if (url.pathname.endsWith('/session')) return route.fulfill({ json: { authenticated: true, configured: true, operator: '화면 시험', scopes: [], csrf: 'mock' } });
    if (url.pathname.endsWith('/snapshot')) return route.fulfill({ json: { ...createDemoSnapshot(), live: true } });
    if (url.pathname.endsWith('/simulations')) return route.fulfill({ json: { categories: [], trips: [], total: 0, page: 1, total_pages: 1 } });
    if (url.pathname.endsWith('/simulations/receipts')) return route.fulfill({ json: {
      statuses: [], targets: [], simulation_targets: [], latest_run: null,
      history: { records, total: records.length, page: 1, page_size: 50, total_pages: 1,
        mode: 'actual', date_from: '2026-10-11', date_to: '2026-10-17', as_of: '2026-10-17T06:00:00+00:00' },
    } });
    return route.fulfill({ status: 404, json: { detail: 'mock 서버 시험 경로 확인 필요' } });
  });
  await page.goto('/simulations');
  await page.getByRole('tab', { name: '수신·모니터링 기록', exact: true }).click();
  const panel = page.getByRole('region', { name: '재난문자·API 수신 및 점검 기록', exact: true });
  await expect(panel.locator('[data-review=affected]')).toHaveCount(3);
  await expect(panel.locator('[data-review=clear]')).toHaveCount(1);
  await expect(panel.locator('[data-review=unassessed]')).toHaveCount(3);
  await expect(panel.locator('[data-review=simulation]')).toHaveText('검토 결과: 모의 · 영향 감지');
  for (const [index, label] of ['영향 감지', '영향 감지', '영향 감지', '영향 없음', '미판정', '모의 · 영향 감지', '미판정', '미판정'].entries()) {
    const line = panel.locator('ol > li').nth(index).locator('p').filter({ hasText: `점검 일정 검토 일정 ${index}` });
    await expect(line).toContainText(`검토 결과: ${label}`);
  }
  const colors = await panel.locator('[data-review]').evaluateAll(elements => elements.map(element => ({
    state: element.getAttribute('data-review'), color: getComputedStyle(element).color,
    background: getComputedStyle(element).backgroundColor, fontSize: getComputedStyle(element).fontSize,
    lineHeight: getComputedStyle(element).lineHeight,
  })));
  expect(colors[0].color).toBe('rgb(159, 28, 32)');
  expect(colors[3].color).toBe('rgb(22, 101, 52)');
  for (const style of colors) {
    expect(parseFloat(style.fontSize)).toBeGreaterThanOrEqual(14);
    expect(parseFloat(style.lineHeight) / parseFloat(style.fontSize)).toBeGreaterThanOrEqual(1.5);
    const luminance = (rgb: string) => {
      const linear = rgb.match(/\d+/g)!.slice(0, 3).map(Number).map(value => {
        const srgb = value / 255;
        return srgb <= 0.04045 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4;
      });
      return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
    };
    const values = [luminance(style.color), luminance(style.background)].sort((a, b) => a - b);
    expect((values[1] + 0.05) / (values[0] + 0.05)).toBeGreaterThanOrEqual(4.5);
  }
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await panel.locator('ol > li').first().scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath(`receipt-review-${width}.png`) });
  expect(writes).toEqual([]);
});
