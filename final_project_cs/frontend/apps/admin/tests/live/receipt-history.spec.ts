import { test, expect } from '@playwright/test';
import { createDemoSnapshot } from '../../src/lib/demo/fixtures';

for (const width of [1280, 375]) test(`수신 기록 기간·모의 실제·50건 페이지·대상 구분 (${width}px)`, async ({ page }) => {
  await page.setViewportSize({ width, height: 900 });
  await page.clock.install({ time: new Date('2026-10-17T06:00:00Z') });
  const requests: URL[] = [];
  const writes: string[] = [];
  const categories = ['forecast', 'weather_warning', 'disaster_msg', 'traffic_control', 'air_quality', 'earthquake'];
  const records = Array.from({ length: 123 }, (_, index) => ({
    id: `record-${index}`, received_at: index < 80 ? '2026-10-17T05:00:00Z' : '2026-10-16T05:00:00Z',
    mode: index % 3 === 2 ? 'simulation' : 'actual', record_type: index === 0 ? 'disaster_message' : 'api_check',
    category: index === 0 ? 'disaster_msg' : categories[index % 6], status: 'ok', source: '[화면 시험] API 자료',
    trip_id: 'trip-test', target_title: `점검 기록 ${index + 1}`, stage: 'schedule',
    text: index === 0 ? '[화면 시험] 실제 수신 문자 내용' : null, published_at: null, regions: ['서울'],
    payload: { category: categories[index % 6], value: { temperature: 23, wind_speed_kmh: 12 } },
  }));
  await page.route('**/admin/api/**', async route => {
    const url = new URL(route.request().url());
    const path = url.pathname;
    if (route.request().method() !== 'GET') writes.push(path);
    if (path.endsWith('/session')) return route.fulfill({ json: { authenticated: true, configured: true, operator: '화면 시험', scopes: [], csrf: 'mock' } });
    if (path.endsWith('/snapshot')) return route.fulfill({ json: { ...createDemoSnapshot(), live: true } });
    if (path.endsWith('/simulations')) return route.fulfill({ json: { categories: [{ key: 'forecast', label: '날씨 예보' }], total: 1, page: 1, total_pages: 1, trips: [{ trip_id: 'trip-test', title: '화면 시험 여행', can_simulate: true }] } });
    if (path.endsWith('/simulations/trip-test')) return route.fulfill({ json: { trip_id: 'trip-test', title: '화면 시험', version: 1, can_simulate: true, configuration: { revision: 0, active: false, categories: [] }, items: [{ item_id: 'item-test', title: '화면 시험 공원', starts_at: '2031-01-01T10:00:00+09:00', ongoing: false, weather_sensitive: true }], notices: [] } });
    if (path.endsWith('/simulations/receipts')) {
      requests.push(url);
      const mode = url.searchParams.get('mode') || 'actual';
      const from = url.searchParams.get('date_from') || '2026-10-11';
      const to = url.searchParams.get('date_to') || '2026-10-17';
      const filtered = records.filter(record => (mode === 'all' || record.mode === mode) && record.received_at.slice(0, 10) >= from && record.received_at.slice(0, 10) <= to);
      const current = Number(url.searchParams.get('page') || 1);
      return route.fulfill({ json: {
        statuses: [], targets: [], targets_as_of: '2026-10-17T06:00:00Z', latest_run: null,
        simulation_targets: [{ trip_id: 'trial-trip', item_id: 'trial-item', title: '창덕궁 · 모의 대상 시험', starts_at: '2026-10-24T10:00:00+09:00', ends_at: '2026-10-24T11:30:00+09:00', reason: 'simulation' }],
        history: { records: filtered.slice((current - 1) * 50, current * 50), total: filtered.length, page: current, page_size: 50, total_pages: Math.max(1, Math.ceil(filtered.length / 50)), mode, date_from: from, date_to: to, as_of: '2026-10-17T06:00:00+00:00' },
      } });
    }
    return route.fulfill({ status: 404, json: { detail: '화면 시험 경로 확인 필요' } });
  });
  await page.goto('/simulations');
  const setupTab = page.getByRole('tab', { name: '재난 시뮬레이션', exact: true });
  const historyTab = page.getByRole('tab', { name: '수신·모니터링 기록', exact: true });
  await expect(setupTab).toHaveAttribute('aria-selected', 'true');
  await page.getByRole('combobox', { name: '대상 여행', exact: true }).selectOption('trip-test');
  await page.getByRole('switch', { name: /날씨 예보/ }).check();
  await page.getByLabel('적용·중지 사유').fill('기록 탭을 오가도 유지');
  await historyTab.click();
  const panel = page.getByRole('region', { name: '재난문자·API 수신 및 점검 기록', exact: true });
  await expect(panel.getByLabel('입력 구분')).toHaveValue('actual');
  await expect(panel.getByLabel('수신·점검 시작일')).toHaveValue('2026-10-11');
  await expect(panel.getByLabel('수신·점검 종료일')).toHaveValue('2026-10-17');
  await expect(panel.locator('ol > li')).toHaveCount(50);
  await expect(panel.getByText('[화면 시험] 실제 수신 문자 내용', { exact: true })).toBeVisible();
  await expect(panel.getByText('총 82건', { exact: false })).toBeVisible();
  await panel.locator('ol > li').first().getByText('API 데이터·점검 결과 펼치기', { exact: true }).click();
  await expect(panel.locator('ol > li').first().locator('pre')).toContainText('temperature');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({ path: `../receipt-history-${width}-v2.png`, fullPage: false });
  await panel.getByLabel('입력 구분').selectOption('all');
  await expect(panel.getByText('총 123건', { exact: false })).toBeVisible();
  await panel.getByRole('button', { name: '수신 기록 2페이지', exact: true }).click();
  await expect(panel.getByRole('button', { name: '수신 기록 2페이지', exact: true })).toHaveAttribute('aria-current', 'page');
  await expect(panel.locator('ol > li')).toHaveCount(50);
  expect(requests.at(-1)?.searchParams.get('as_of')).toBe('2026-10-17T06:00:00+00:00');
  await panel.getByRole('button', { name: '수신 기록 3페이지', exact: true }).click();
  await expect(panel.locator('ol > li')).toHaveCount(23);
  await expect(panel.getByRole('button', { name: '다음 페이지', exact: true })).toBeDisabled();
  await panel.getByLabel('입력 구분').selectOption('simulation');
  await expect(panel.getByText('총 41건', { exact: false })).toBeVisible();
  await expect(panel.getByRole('button', { name: '수신 기록 1페이지', exact: true })).toHaveAttribute('aria-current', 'page');
  await panel.getByText('현재 수신 상태·검사 대상 펼치기', { exact: true }).click();
  await expect(panel.getByText('창덕궁 · 모의 대상 시험', { exact: false })).toBeVisible();
  await expect(panel.getByRole('heading', { name: '현재 모의 시험 대상 1건', exact: true })).toBeVisible();
  await panel.getByLabel('입력 구분').selectOption('actual');
  await expect(panel.getByRole('heading', { name: '현재 실제 검사 대상 0건', exact: true })).toBeVisible();
  await expect(panel.getByText('창덕궁 · 모의 대상 시험', { exact: false })).toBeHidden();
  await panel.getByLabel('수신·점검 시작일').fill('2026-10-16');
  await panel.getByLabel('수신·점검 종료일').fill('2026-10-16');
  await panel.getByRole('button', { name: '기간 조회', exact: true }).click();
  await expect(panel.locator('ol > li')).toHaveCount(28);
  expect(requests.at(-1)?.searchParams.get('date_from')).toBe('2026-10-16');
  await panel.getByLabel('수신·점검 시작일').fill('2026-10-18');
  const beforeInvalid = requests.length;
  await panel.getByRole('button', { name: '기간 조회', exact: true }).click();
  await expect(panel.getByRole('alert')).toContainText('시작일과 종료일');
  expect(requests.length).toBe(beforeInvalid);
  await panel.getByRole('button', { name: '최근 7일 보기', exact: true }).click();
  await expect(panel.locator('ol > li')).toHaveCount(50);
  await historyTab.press('ArrowLeft');
  await expect(setupTab).toBeFocused();
  await expect(page.getByLabel('적용·중지 사유')).toHaveValue('기록 탭을 오가도 유지');
  await expect(page.getByRole('switch', { name: /날씨 예보/ })).toBeChecked();
  await setupTab.press('End');
  await expect(historyTab).toBeFocused();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  expect(writes).toEqual([]);
});
