import { test, expect, type Page } from '@playwright/test';
import { createDemoSnapshot } from '../../src/lib/demo/fixtures';

// 언리미티드 모드 — 「API 호출량」 탭에서 확인 창(유료 호출 안내 · 사유)을 거쳐 켜고 끈다. 서버는 mock 서버(page.route)로 흉내 낸다.
const field = (env: string | null, value: number | null, zero_meaning = 'unset', origin = 'configured') => ({ env, value, zero_meaning, origin });
const serpapi = { id: 'serpapi', name: 'SerpApi 구글 호텔 · 항공권', budget_timezone: 'Asia/Seoul', daily: field('ACOP_RATE_SERPAPI_PER_DAY', 8), monthly: field('ACOP_RATE_SERPAPI_PER_MONTH', 250), recorded: { day: { used: 8, cap: 8, updated_at: '2026-10-19T20:00:00+09:00' }, month: { used: 250, cap: 250, updated_at: '2026-10-19T20:00:00+09:00' } }, operator_cap: null, adjustable: true, over_cap: { day: 4, month: 6 } };
const limits = { as_of: '2026-10-19T20:01:00+09:00', timezone: 'Asia/Seoul', usage_error: null, limits: [serpapi] };
const cell = (value: boolean) => ({ name: 'api.unlimited_mode', label: '언리미티드 모드', type: 'bool', value, default: false, text_ko: '유료 호출이 늘 수 있습니다.', updated_at: value ? '2026-10-19T20:02:00+09:00' : null, updated_by: value ? 'op-kim' : null });

async function mockServer(page: Page, state: { on: boolean; revision: number; patches: unknown[] }) {
  await page.route('**/admin/api/**', async route => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith('/session')) return route.fulfill({ json: { authenticated: true, configured: true, operator: 'op-kim', scopes: ['ops:introspect', 'limits:read', 'limits:write'], csrf: 'mock' } });
    if (path.endsWith('/snapshot')) return route.fulfill({ json: { ...createDemoSnapshot(), live: true } });
    if (path.endsWith('/api-limits')) return route.fulfill({ json: limits });
    if (path.endsWith('/settings/limits')) {
      if (request.method() === 'PATCH') {
        const body = request.postDataJSON();
        state.patches.push(body);
        if (body.expected_revision !== state.revision) return route.fulfill({ status: 409, json: { detail: { error: { message: '그 사이 다른 운영자가 바꿨다 — 다시 읽고 바꾼다' } } } });
        state.on = body.changes['api.unlimited_mode'] === true; state.revision += 1;
      }
      return route.fulfill({ json: { revision: state.revision, limits: [cell(state.on)] } });
    }
    return route.abort();
  });
}

test('켤 때 유료 호출 안내와 사유를 거쳐야 저장되고, 끄기도 같은 길로 한다', async ({ page }) => {
  const state = { on: false, revision: 3, patches: [] as unknown[] };
  await mockServer(page, state);
  await page.goto('/usage');
  const panel = page.getByRole('region', { name: '언리미티드 모드' });
  await expect(panel.getByText('꺼짐 — 한도 지킴')).toBeVisible();
  await panel.getByRole('button', { name: '언리미티드 켜기' }).click();
  const dialog = panel.getByRole('alertdialog', { name: '언리미티드 모드를 켤까요?' });
  await expect(dialog).toContainText('유료 호출이 늘 수 있음');
  await expect(dialog).toContainText('숙소 시연 모드의 월 한도도 풀립니다');
  await dialog.getByRole('button', { name: /켜기/ }).click();
  await expect(panel.getByRole('alert')).toContainText('사유를 입력하세요');
  expect(state.patches).toHaveLength(0);
  await dialog.getByLabel('사유 (필수)').fill('최종 발표 시연');
  await dialog.getByRole('button', { name: /켜기/ }).click();
  await expect(panel.getByRole('status').filter({ hasText: '언리미티드 모드를 켰습니다' })).toBeVisible();
  await expect(panel.getByText('켜짐 — 한도 풀림')).toBeVisible();
  expect(state.patches).toEqual([{ expected_revision: 3, changes: { 'api.unlimited_mode': true }, reason: '최종 발표 시연' }]);
  // 「한도 밖」 수 — 상한 있는 줄과 따로 센 호출
  await expect(page.getByRole('region', { name: /API 한도 표/ })).toContainText('한도 밖(언리미티드 · 숙소 시연): 일 4회 · 월 6회');
  if (process.env.UNLIMITED_SCREENSHOT) await page.screenshot({ path: process.env.UNLIMITED_SCREENSHOT, fullPage: true });

  await panel.getByRole('button', { name: '언리미티드 끄기' }).click();
  const off = panel.getByRole('alertdialog', { name: '언리미티드 모드를 끌까요?' });
  await off.getByLabel('사유 (필수)').fill('시연 끝');
  await off.getByRole('button', { name: '언리미티드 끄기' }).click();
  await expect(panel.getByText('꺼짐 — 한도 지킴')).toBeVisible();
  expect(state.patches[1]).toEqual({ expected_revision: 4, changes: { 'api.unlimited_mode': false }, reason: '시연 끝' });
});

test('취소하면 아무것도 저장하지 않고, 375px 에서도 가로로 넘치지 않는다', async ({ page }) => {
  await page.setViewportSize({ width: 375, height: 844 });
  const state = { on: false, revision: 1, patches: [] as unknown[] };
  await mockServer(page, state);
  await page.goto('/usage');
  const panel = page.getByRole('region', { name: '언리미티드 모드' });
  await panel.getByRole('button', { name: '언리미티드 켜기' }).click();
  await panel.getByRole('button', { name: '취소' }).click();
  await expect(panel.getByRole('alertdialog')).toHaveCount(0);
  expect(state.patches).toHaveLength(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  if (process.env.UNLIMITED_NARROW_SCREENSHOT) await page.screenshot({ path: process.env.UNLIMITED_NARROW_SCREENSHOT, fullPage: true });
});
