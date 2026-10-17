import { test, expect } from '@playwright/test';
import { createDemoSnapshot } from '../../src/lib/demo/fixtures';

for (const width of [1280, 375]) test(`일정 영향 카드·다중 필터·페이지·읽기 전용 (${width}px)`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 });
  await page.clock.install({ time: new Date('2026-10-17T06:00:00Z') });
  const requests: URL[] = [];
  const writes: string[] = [];
  const options = [{ scope: 'trip', label: '전체일정정지' }, { scope: 'day', label: '일일일정정지' }, { scope: 'item', label: '해당일정정지' }, { scope: 'none', label: '영향없음' }, { scope: 'unassessed', label: '영향 미판정' }];
  const records = Array.from({ length: 153 }, (_, index) => {
    const value = options[index % options.length];
    const mode = index % 7 === 0 ? 'simulation' : 'actual';
    return { id: `impact-${index}`, received_at: '2026-10-17T05:00:00Z', mode,
      record_type: 'api_check', category: 'earthquake', status: 'ok', source: 'kma_earthquake', trip_id: 'test-trip',
      target_title: `영향 검증 일정 ${index}`, stage: 'safety', payload: {}, regions: [],
      impact: { ...value, summary: '[mock 서버 시험] 저장된 판정에 따른 영향 범위',
        affects_itinerary: mode === 'actual' && ['trip', 'day', 'item'].includes(value.scope), target_mode: mode } };
  });
  await page.route('**/admin/api/**', async route => {
    const url = new URL(route.request().url());
    if (route.request().method() !== 'GET') writes.push(url.pathname);
    if (url.pathname.endsWith('/session')) return route.fulfill({ json: { authenticated: true, configured: true, operator: '화면 시험', scopes: [], csrf: 'mock' } });
    if (url.pathname.endsWith('/snapshot')) return route.fulfill({ json: { ...createDemoSnapshot(), live: true } });
    if (url.pathname.endsWith('/simulations')) return route.fulfill({ json: { categories: [], trips: [], total: 0, page: 1, total_pages: 1 } });
    if (url.pathname.endsWith('/simulations/receipts')) {
      requests.push(url);
      const selected = url.searchParams.getAll('impact');
      const mode = url.searchParams.get('mode') || 'actual';
      const filtered = records.filter(record => (mode === 'all' || record.mode === mode) && (!selected.length || selected.includes(record.impact.scope)));
      const current = Number(url.searchParams.get('page') || 1);
      return route.fulfill({ json: { statuses: [], targets: [], simulation_targets: [], latest_run: null,
        history: { records: filtered.slice((current - 1) * 50, current * 50), total: filtered.length, page: current, page_size: 50,
          total_pages: Math.max(1, Math.ceil(filtered.length / 50)), mode, impacts: selected,
          date_from: '2026-10-11', date_to: '2026-10-17', as_of: '2026-10-17T06:00:00+00:00' } } });
    }
    return route.fulfill({ status: 404, json: { detail: 'mock 서버 시험 경로 확인 필요' } });
  });
  await page.goto('/simulations');
  await page.getByRole('tab', { name: '수신·모니터링 기록', exact: true }).click();
  const panel = page.getByRole('region', { name: '재난문자·API 수신 및 점검 기록', exact: true });
  await expect(panel.getByRole('checkbox')).toHaveCount(4);
  await expect(panel.getByLabel('전체일정정지', { exact: true })).not.toBeChecked();
  await expect(panel.locator('li[data-affects=true][data-impact=trip]').first()).toContainText('실제 일정 영향 가능');
  await expect(panel.locator('li[data-impact=unassessed]').first()).toContainText('여행 영향 확인 전');
  await expect(panel.locator('li').first()).toContainText('기상청 지진정보');
  const colors = await panel.locator('li[data-affects=true]').evaluateAll(elements =>
    Object.fromEntries(elements.map(element => [element.getAttribute('data-impact'), getComputedStyle(element).backgroundColor])));
  expect(new Set(Object.values(colors)).size).toBe(3);
  await panel.getByRole('button', { name: '수신 기록 2페이지', exact: true }).click();
  await expect(panel.getByRole('button', { name: '수신 기록 2페이지', exact: true })).toHaveAttribute('aria-current', 'page');
  await panel.getByLabel('전체일정정지', { exact: true }).check();
  await expect(panel.getByRole('button', { name: '수신 기록 1페이지', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(panel.locator('ol > li')).toHaveCount(records.filter(r => r.mode === 'actual' && r.impact.scope === 'trip').length);
  expect(requests.at(-1)?.searchParams.getAll('impact')).toEqual(['trip']);
  expect(requests.at(-1)?.searchParams.has('as_of')).toBe(false);
  await panel.getByLabel('일일일정정지', { exact: true }).check();
  await expect(panel.locator('ol > li')).toHaveCount(50);
  expect(requests.at(-1)?.searchParams.getAll('impact')).toEqual(['trip', 'day']);
  expect(await panel.locator('ol > li').evaluateAll(elements => elements.every(element => ['trip', 'day'].includes(element.getAttribute('data-impact') || '')))).toBe(true);
  await panel.getByLabel('입력 구분').selectOption('all');
  await expect(panel.getByRole('button', { name: '수신 기록 2페이지', exact: true })).toBeVisible();
  await panel.getByRole('button', { name: '수신 기록 2페이지', exact: true }).click();
  await expect(panel.locator('ol > li')).toHaveCount(12);
  expect(requests.at(-1)?.searchParams.get('as_of')).toBe('2026-10-17T06:00:00+00:00');
  await panel.getByLabel('전체일정정지', { exact: true }).uncheck();
  await panel.getByLabel('일일일정정지', { exact: true }).uncheck();
  await panel.getByLabel('영향없음', { exact: true }).check();
  await expect(panel.locator('ol > li')).toHaveCount(30);
  await expect(panel.locator('li[data-impact=unassessed]')).toHaveCount(0);
  await panel.getByLabel('영향없음', { exact: true }).uncheck();
  await expect(panel.locator('li[data-impact=unassessed]').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `../receipt-impact-${width}-v1.png`, fullPage: false });
  expect(writes).toEqual([]);
});
