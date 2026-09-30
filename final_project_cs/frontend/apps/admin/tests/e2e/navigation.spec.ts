import { expect, test } from '@playwright/test';
import { collectBrowserFailures, demoLabel, expectNoHorizontalOverflow, loginLabel, main, routes, screenTitles } from './support';

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
