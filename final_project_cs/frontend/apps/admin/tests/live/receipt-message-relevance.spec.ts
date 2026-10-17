import { test, expect } from '@playwright/test';
import { createDemoSnapshot } from '../../src/lib/demo/fixtures';

for (const width of [1280, 375]) test(`문자 원문·지역 불일치·미확인과 빨강 초록 결과 (${width}px)`, async ({ page }, testInfo) => {
  await page.setViewportSize({ width, height: 900 });
  await page.clock.install({ time: new Date('2026-10-18T00:00:00Z') });
  const writes: string[] = [];
  const records = ['none', 'item', 'unassessed'].map((scope, index) => ({
    id: `area-${index}`, received_at: '2026-10-17T12:42:39+00:00', mode: 'actual', record_type: 'api_check',
    category: 'disaster_msg', status: 'ok', source: 'disaster_msg', trip_id: 'synthetic-trip',
    target_title: `지역 비교 일정 ${index}`, stage: 'schedule', payload: {}, regions: [],
    impact: { scope, label: scope === 'none' ? '영향없음' : scope === 'item' ? '해당일정정지' : '영향 미판정',
      summary: '지역과 저장된 점검 결과를 대조했습니다.', affects_itinerary: scope === 'item', target_mode: 'actual' },
    notice_review: {
      messages: [{ text: index === 0 ? '금천구 시험 행사장의 소음·연기 안전안내입니다.' : '서초구 시험 장소 진입도로 통제 안내입니다.',
        kind: '기타', step: '안전안내', created_at: '2026-10-17T18:00:00+09:00', published_at: null,
        regions: [index === 0 ? '서울특별시 금천구' : '서울특별시 서초구'],
        relation: index === 0 ? 'unrelated' : index === 1 ? 'matched' : 'unassessed' }],
      target: { name: '비교 활동장소', district: index === 2 ? null : '서초구', district_basis: index === 2 ? 'none' : 'box', basis_source: 'current_saved_place' },
      reason: index === 0 ? '발송 지역과 일정 지역이 달라 영향 사유에서 제외했습니다.' : index === 1 ? '발송 지역과 비교 지역이 겹칩니다.' : '지역을 확인할 수 없습니다.',
    },
  }));
  await page.route('**/admin/api/**', async route => {
    const url = new URL(route.request().url());
    if (route.request().method() !== 'GET') writes.push(url.pathname);
    if (url.pathname.endsWith('/session')) return route.fulfill({ json: { authenticated: true, configured: true, operator: '화면 시험', scopes: [], csrf: 'mock' } });
    if (url.pathname.endsWith('/snapshot')) return route.fulfill({ json: { ...createDemoSnapshot(), live: true } });
    if (url.pathname.endsWith('/simulations')) return route.fulfill({ json: { categories: [], trips: [], total: 0, page: 1, total_pages: 1 } });
    if (url.pathname.endsWith('/simulations/receipts')) return route.fulfill({ json: { statuses: [], targets: [], latest_run: null,
      history: { records, total: 3, page: 1, page_size: 50, total_pages: 1, mode: 'actual', date_from: '2026-10-12', date_to: '2026-10-18', as_of: '2026-10-18T00:00:00Z' } } });
    return route.fulfill({ status: 404, json: { detail: 'mock 서버 시험 경로 확인 필요' } });
  });
  await page.goto('/simulations');
  await page.getByRole('tab', { name: '수신·모니터링 기록', exact: true }).click();
  const panel = page.getByRole('region', { name: '재난문자·API 수신 및 점검 기록', exact: true });
  const card = panel.locator('ol > li').first();
  await expect(card.getByText('금천구 시험 행사장의 소음·연기 안전안내입니다.', { exact: false })).toBeVisible();
  await expect(card).toContainText('발송 지역 서울특별시 금천구');
  await expect(card).toContainText('비교 지역 서초구');
  await expect(card).toContainText('현재 저장된 장소 기준 재검토');
  await expect(card).toContainText('영향 사유에서 제외');
  await expect(card.locator('[data-review=clear]')).toHaveText('검토 결과: 영향 없음');
  await expect(panel.locator('ol > li').nth(1).locator('[data-review=affected]')).toHaveText('검토 결과: 영향 감지');
  await expect(panel.locator('ol > li').nth(2).locator('[data-review=unassessed]')).toHaveText('검토 결과: 미판정');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await card.scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath(`message-relevance-${width}.png`) });
  expect(writes).toEqual([]);
});
