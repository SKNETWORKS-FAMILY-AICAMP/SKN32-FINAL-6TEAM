import { expect, test } from '@playwright/test';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { collectBrowserFailures, demoLabel, expectNoHorizontalOverflow, loginLabel, main, routes, screenTitles } from './support';

const standaloneUrl = pathToFileURL(resolve('mockups/admin-scenario.html')).href;

test('비인증 데모 로그인과 모든 화면의 직접 경로가 열리고 백엔드를 호출하지 않는다', async ({ page }) => {
  const failures = collectBrowserFailures(page, 'http://127.0.0.1:3301');
  await page.goto('/login');
  await expect(page.getByText(demoLabel, { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: loginLabel, exact: true })).toBeVisible();
  await page.getByRole('button', { name: loginLabel, exact: true }).click();
  await expect(page).toHaveURL('http://127.0.0.1:3301/');

  for (const path of routes) {
    await page.goto(path);
    await expect(page.getByText(demoLabel, { exact: true })).toBeVisible();
    await expect(main(page).getByRole('heading', { name: screenTitles[path], level: 1, exact: true })).toBeVisible();
    await expect(page.getByLabel('화면 상태', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '데모 초기화', exact: true })).toBeVisible();
    await expect(main(page)).not.toContainText('연결 미설정');
    await expectNoHorizontalOverflow(page);
  }
  expect(failures.errors).toEqual([]);
  expect(failures.forbiddenRequests).toEqual([]);
});

test('조회 화면마다 로딩·빈 목록·실패를 명시하고 정상 상태로 돌아온다', async ({ page }) => {
  for (const path of routes) {
    await page.goto(path);
    await expect(main(page).getByRole('heading', { name: screenTitles[path], level: 1, exact: true })).toBeVisible();
    await page.getByLabel('화면 상태', { exact: true }).selectOption('loading');
    await expect(main(page).getByRole('status')).toContainText('불러오는 중');
    await expect(main(page).getByRole('heading', { name: screenTitles[path], level: 1, exact: true })).toHaveCount(0);
    await page.getByLabel('화면 상태', { exact: true }).selectOption('empty');
    await expect(main(page).getByRole('heading', { name: '표시할 데이터가 없습니다.', exact: true })).toBeVisible();
    await expect(main(page).getByRole('table')).toHaveCount(0);
    await page.getByLabel('화면 상태', { exact: true }).selectOption('error');
    await expect(main(page).getByRole('alert')).toContainText('불러오기 실패');
    await expect(main(page).getByRole('table')).toHaveCount(0);
    await main(page).getByRole('button', { name: '다시 불러오기', exact: true }).click();
    await expect(main(page).getByRole('heading', { name: screenTitles[path], level: 1, exact: true })).toBeVisible();
    await expect(page.getByLabel('화면 상태', { exact: true })).toHaveValue('normal');
  }
});

test('없는 사용자·문의 ID는 다른 대상의 상세로 대체하지 않는다', async ({ page }) => {
  await page.goto('/users/not-a-user');
  await expect(main(page).getByRole('heading', { name: '사용자를 찾을 수 없습니다', exact: true })).toBeVisible();
  await expect(main(page).getByRole('button', { name: '사용자 차단', exact: true })).toHaveCount(0);
  await page.goto('/inquiries/not-an-inquiry');
  await expect(main(page).getByText('요청한 문의를 찾을 수 없습니다.', { exact: true })).toBeVisible();
  await expect(main(page).getByRole('region', { name: '문의 상세', exact: true })).toHaveCount(0);
});

test('390px 창에서도 모든 화면을 페이지 가로 넘침 없이 읽는다', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ['/login', ...routes]) {
    await page.goto(path);
    await expect(page.getByText(demoLabel, { exact: true })).toBeVisible();
    await expect(page.getByRole('heading', { level: 1 })).toBeVisible();
    await expectNoHorizontalOverflow(page);
  }
});

for (const standalone of [false, true]) {
  const surface = standalone ? '오프라인 HTML' : '실행 앱';

  test(`${surface}: 사용자 목록 조건은 상세 방문과 뒤로 가기에서 유지되고 초기화로 지워진다`, async ({ page, context }) => {
    const failures = collectBrowserFailures(page, standalone ? undefined : 'http://127.0.0.1:3301');
    await context.setOffline(standalone);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(standalone ? `${standaloneUrl}#/users` : '/users');
    await page.getByLabel('사용자 ID로 찾기', { exact: true }).fill('demo-user-0');
    await page.getByRole('combobox', { name: '상태', exact: true }).selectOption('정상');
    await page.getByRole('combobox', { name: '정렬', exact: true }).selectOption('오늘 사용량순');
    await page.getByRole('button', { name: '문의 있음', exact: true }).click();
    await expect(main(page).getByRole('row')).toHaveCount(4);
    await page.getByRole('button', { name: 'demo-user-02 상세 보기', exact: true }).click();
    await expect(main(page).getByRole('heading', { name: '사용자 상세', exact: true })).toBeVisible();
    await page.goBack();
    await expect(page.getByLabel('사용자 ID로 찾기', { exact: true })).toHaveValue('demo-user-0');
    await expect(page.getByRole('combobox', { name: '상태', exact: true })).toHaveValue('정상');
    await expect(page.getByRole('combobox', { name: '정렬', exact: true })).toHaveValue('오늘 사용량순');
    await expect(page.getByRole('button', { name: '문의 있음', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await page.goForward();
    await page.getByRole('button', { name: '← 사용자 목록', exact: true }).click();
    await expect(page.getByLabel('사용자 ID로 찾기', { exact: true })).toHaveValue('demo-user-0');
    await expect(page.getByRole('combobox', { name: '정렬', exact: true })).toHaveValue('오늘 사용량순');
    await expect(main(page).getByRole('row')).toHaveCount(4);
    if (!standalone) {
      await page.screenshot({ path: 'test-results/admin-users-filtered-desktop.png', fullPage: true });
      await page.setViewportSize({ width: 390, height: 844 });
      await expectNoHorizontalOverflow(page);
      await page.screenshot({ path: 'test-results/admin-users-filtered-mobile.png', fullPage: true });
    }
    await page.getByRole('button', { name: '데모 초기화', exact: true }).click();
    await expect(page.getByLabel('사용자 ID로 찾기', { exact: true })).toHaveValue('');
    await expect(page.getByRole('combobox', { name: '상태', exact: true })).toHaveValue('전체');
    await expect(page.getByRole('combobox', { name: '정렬', exact: true })).toHaveValue('마지막 사용순');
    await expect(page.getByRole('button', { name: '전체', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await expect(main(page).getByRole('row')).toHaveCount(7);
    await page.getByLabel('사용자 ID로 찾기', { exact: true }).fill('demo-user-02');
    await page.reload();
    await expect(page.getByLabel('사용자 ID로 찾기', { exact: true })).toHaveValue('');
    expect(failures.errors).toEqual([]);
    expect(failures.forbiddenRequests).toEqual([]);
  });

  test(`${surface}: 문의 선택과 사용자 확인 후에도 문의 필터를 유지한다`, async ({ page, context }) => {
    const failures = collectBrowserFailures(page, standalone ? undefined : 'http://127.0.0.1:3301');
    await context.setOffline(standalone);
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(standalone ? `${standaloneUrl}#/inquiries` : '/inquiries');
    const list = page.getByRole('region', { name: '문의 목록', exact: true });
    const detail = page.getByRole('region', { name: '문의 상세', exact: true });
    await list.getByRole('button', { name: /^처리 중 \d+$/ }).click();
    await page.getByRole('combobox', { name: '담당자 필터', exact: true }).selectOption('demo.operator');
    await page.getByLabel('문의 찾기', { exact: true }).fill('장소');
    await list.getByRole('button').filter({ hasText: '장소 정보가 갱신되지 않아요' }).click();
    await expect(page.getByLabel('문의 찾기', { exact: true })).toHaveValue('장소');
    await expect(page.getByRole('combobox', { name: '담당자 필터', exact: true })).toHaveValue('demo.operator');
    await expect(list.getByRole('button', { name: /^처리 중 \d+$/ })).toHaveAttribute('aria-pressed', 'true');
    if (!standalone) await page.screenshot({ path: 'test-results/admin-inquiries-filtered-desktop.png', fullPage: true });
    await detail.getByRole('button', { name: 'demo-user-02 ↗', exact: true }).click();
    await expect(main(page).getByRole('heading', { name: '사용자 상세', exact: true })).toBeVisible();
    await page.goBack();
    await expect(detail).toContainText('장소 정보가 갱신되지 않아요');
    await expect(page.getByLabel('문의 찾기', { exact: true })).toHaveValue('장소');
    await page.goBack();
    await expect(page.getByRole('combobox', { name: '담당자 필터', exact: true })).toHaveValue('demo.operator');
    await page.goForward();
    await list.getByRole('button', { name: /^접수 \d+$/ }).click();
    await expect(main(page).getByText('선택한 문의가 현재 필터에 포함되지 않습니다.', { exact: true })).toBeVisible();
    await expect(detail).toHaveCount(0);
    await page.getByRole('button', { name: '문의 필터 초기화', exact: true }).click();
    await expect(page.getByLabel('문의 찾기', { exact: true })).toHaveValue('');
    await expect(page.getByRole('combobox', { name: '담당자 필터', exact: true })).toHaveValue('all');
    await expect(list.getByRole('button', { name: /^전체/ })).toHaveAttribute('aria-pressed', 'true');
    await expect(detail).toContainText('장소 정보가 갱신되지 않아요');
    await page.getByLabel('문의 찾기', { exact: true }).fill('장소');
    await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: '운영 홈', exact: true }).click();
    await page.getByRole('button', { name: '데모 초기화', exact: true }).click();
    await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: /^문의함/ }).click();
    await expect(page.getByLabel('문의 찾기', { exact: true })).toHaveValue('');
    expect(failures.errors).toEqual([]);
    expect(failures.forbiddenRequests).toEqual([]);
  });
}
