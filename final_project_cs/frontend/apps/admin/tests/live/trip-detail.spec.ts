import { test, expect, type Page } from '@playwright/test';
import { createDemoSnapshot } from '../../src/lib/demo/fixtures';

const userId = '11111111-1111-4111-8111-111111111111';
const tripId = '22222222-2222-4222-8222-222222222222';
const path = `/users/${userId}/trips/${tripId}`;
const originalTitle = '경복궁 관람';
const currentTitle = '국립중앙박물관 관람';
const at = '2026-10-17T12:10:00Z';
const longText = '박물관으로 바꿔 주세요.\n<script>window.injected=true</script>\n' + '여행 계획 확인. '.repeat(120);

async function records(page: Page, options: { empty?: boolean; failed?: boolean; missingInitial?: boolean } = {}) {
  const calls: string[] = [];
  const snapshot = { ...createDemoSnapshot(), live: true };
  snapshot.users = [{ ...snapshot.users[0], id: userId, trips: [{ id: tripId, title: '서울 가족 여행', status: 'active', places: 2 }] }];
  const summary = { trip: { trip_id: tripId, customer_id: userId, title: '서울 가족 여행', status: 'active', locale: 'ko', party_size: 4, latest_version: 2, created_at: at }, as_of: at };
  const item = { item_id: 'item-1', seq: 1, kind: 'activity', starts_at: '2026-10-20T01:00:00Z', ends_at: '2026-10-20T03:00:00Z', locked: false, place_name: '서울', address: '서울특별시', detail: {} };
  await page.route('**/admin/api/**', async route => {
    const url = new URL(route.request().url()); calls.push(url.pathname + url.search);
    if (url.pathname.endsWith('/session')) return route.fulfill({ json: { authenticated: true, configured: true, operator: 'qa-operator', scopes: ['ops:introspect'], csrf: 'csrf' } });
    if (url.pathname.endsWith('/snapshot')) return route.fulfill({ json: snapshot });
    if (url.pathname === `/admin/api${path}`) return route.fulfill({ json: summary });
    if (url.pathname.endsWith('/chat')) {
      if (options.failed) return route.fulfill({ status: 503, json: { detail: '대화 기록 연결을 확인해 주세요.' } });
      const turns = options.empty ? [] : url.searchParams.get('after') === '0' ? [
        { turn_id: '21', role: 'customer', text: longText, at, case_id: null },
        { turn_id: '22', role: 'assistant', text: '현재 계획을 박물관으로 바꿨습니다.', at, case_id: null },
      ] : [{ turn_id: '23', role: 'customer', text: '변경된 계획 확인했습니다.', at, case_id: null }];
      return route.fulfill({ json: { turns, next_after: !options.empty && url.searchParams.get('after') === '0' ? '22' : null } });
    }
    if (url.pathname.endsWith('/plans/initial') || url.pathname.endsWith('/plans/current')) {
      const initial = url.pathname.endsWith('/initial');
      return route.fulfill({ json: { plan: initial && options.missingInitial ? null : { version: initial ? 1 : 2, reason: initial ? 'created' : 'customer_request', created_at: at, items: [{ ...item, title: initial ? originalTitle : currentTitle }] }, as_of: at } });
    }
    return route.fulfill({ status: 404, json: { detail: '이 사용자의 여행을 찾을 수 없습니다.' } });
  });
  return calls;
}

test('여행 선택·대화 이어 읽기·처음과 현재 계획·뒤로 가기·새로고침', async ({ page }) => {
  const calls = await records(page);
  await page.goto(`/users/${userId}`);
  await expect(page.getByRole('link', { name: '서울 가족 여행' })).toHaveAttribute('href', path);
  await page.getByRole('link', { name: '서울 가족 여행' }).click();
  await expect(page).toHaveURL(path);
  await expect(page.getByRole('heading', { name: '서울 가족 여행' })).toBeVisible();
  await expect(page.getByText(longText, { exact: true })).toBeVisible();
  await expect(page.getByRole('tabpanel').getByText(/21:10/).first()).toBeVisible();
  expect(await page.evaluate(() => 'injected' in window)).toBe(false);
  await page.getByRole('button', { name: '다음 대화 더 보기' }).click();
  await expect(page.getByText('변경된 계획 확인했습니다.', { exact: true })).toBeVisible();
  await expect(page.getByText(/대화 3개 표시/)).toBeVisible();
  await page.getByRole('tab', { name: '처음 여행계획' }).click();
  await expect(page.getByRole('heading', { name: originalTitle })).toBeVisible();
  await expect(page.getByText('1판 · 처음 등록')).toBeVisible();
  await page.getByRole('tab', { name: '현재 여행계획' }).click();
  await expect(page.getByRole('heading', { name: currentTitle })).toBeVisible();
  await expect(page.getByText('2판 · 고객 요청')).toBeVisible();
  await expect(page.getByText('10:00', { exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('heading', { name: '서울 가족 여행' })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: '사용자 상세', exact: true })).toBeVisible();
  expect(calls.some(call => call.endsWith('/commands'))).toBe(false);
});

test('오류는 다시 읽기로 회복하고 빈 기록·처음 계획 미보관을 구분한다', async ({ page }) => {
  const options = { empty: true, failed: true, missingInitial: true };
  await records(page, options);
  await page.goto(path);
  await expect(page.getByRole('alert').filter({ hasText: '대화 기록 연결을 확인해 주세요.' })).toBeVisible();
  await expect(page.getByText('이 여행에 저장된 대화 내역이 없습니다.')).toHaveCount(0);
  options.failed = false;
  await page.getByRole('button', { name: '다시 읽기', exact: true }).click();
  await expect(page.getByText('이 여행에 저장된 대화 내역이 없습니다.')).toBeVisible();
  await page.getByRole('tab', { name: '처음 여행계획' }).click();
  await expect(page.getByText('처음 여행계획(1판)이 보관되어 있지 않습니다.')).toBeVisible();
  await page.getByRole('tab', { name: '현재 여행계획' }).click();
  await expect(page.getByRole('heading', { name: currentTitle })).toBeVisible();
});

test('직접 주소·잘못된 소유는 오류를 보이고 목록으로 복귀한다', async ({ page }) => {
  await records(page);
  await page.goto(path.replace(userId, '33333333-3333-4333-8333-333333333333'));
  await expect(page.getByRole('alert').filter({ hasText: '이 사용자의 여행을 찾을 수 없습니다.' })).toBeVisible();
  await expect(page.getByRole('tab', { name: '대화 내역' })).toHaveCount(0);
  await page.getByRole('button', { name: '사용자 목록', exact: true }).click();
  await expect(page).toHaveURL('/users');
});

test('이어 읽기·새로 읽기 실패에도 읽은 대화를 보존하고 재시도한다', async ({ page }) => {
  const options = { failed: false };
  await records(page, options);
  await page.goto(path);
  await expect(page.getByText(longText, { exact: true })).toBeVisible();
  options.failed = true;
  await page.getByRole('button', { name: '다음 대화 더 보기' }).click();
  const error = page.getByRole('alert').filter({ hasText: '대화 기록 연결을 확인해 주세요.' });
  await expect(error).toBeVisible();
  await expect(page.getByText(longText, { exact: true })).toBeVisible();
  options.failed = false;
  await error.getByRole('button', { name: '다시 읽기' }).click();
  await expect(page.getByText('변경된 계획 확인했습니다.', { exact: true })).toBeVisible();
  options.failed = true;
  await page.getByRole('button', { name: '기록 새로 읽기' }).click();
  await expect(error).toBeVisible();
  await expect(page.getByText('변경된 계획 확인했습니다.', { exact: true })).toBeVisible();
  options.failed = false;
  await error.getByRole('button', { name: '다시 읽기' }).click();
  await expect(error).toHaveCount(0);
});

for (const width of [375, 1280]) test(`${width}px 화면·키보드 탭·기록 촬영`, async ({ page }, testInfo) => {
  await page.setViewportSize({ width, height: 900 });
  await records(page);
  await page.goto(path);
  await expect(page.getByText(longText, { exact: true })).toBeVisible();
  const tab = page.getByRole('tab', { name: '대화 내역' });
  await tab.focus(); await tab.press('ArrowRight');
  await expect(page.getByRole('tab', { name: '처음 여행계획' })).toBeFocused();
  await expect(page.getByRole('heading', { name: originalTitle })).toBeVisible();
  await page.getByRole('tab', { name: '처음 여행계획' }).press('End');
  await expect(page.getByRole('tab', { name: '현재 여행계획' })).toBeFocused();
  await expect(page.getByRole('heading', { name: currentTitle })).toBeVisible();
  expect(await page.getByRole('heading', { name: currentTitle }).evaluate(element => parseFloat(getComputedStyle(element).fontSize))).toBeGreaterThanOrEqual(14);
  expect(await page.getByRole('heading', { name: currentTitle }).evaluate(element => Number(getComputedStyle(element).fontWeight))).toBeLessThanOrEqual(600);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await page.screenshot({ path: testInfo.outputPath(`trip-detail-${width}-plan.png`), fullPage: true });
  await page.getByRole('tab', { name: '현재 여행계획' }).press('Home');
  await expect(page.getByRole('tab', { name: '대화 내역' })).toBeFocused();
  await expect(page.getByText(longText, { exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  expect(await page.getByRole('tab', { name: '대화 내역' }).evaluate(element => element.getBoundingClientRect().height)).toBeGreaterThanOrEqual(44);
  await page.screenshot({ path: testInfo.outputPath(`trip-detail-${width}-chat.png`), fullPage: true });
});
