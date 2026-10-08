import { expect, test } from '@playwright/test';

test('모드가 없는 별도 빌드는 직접 경로에서도 데모로 전환하지 않는다', async ({ page }) => {
  const externalRequests: string[] = [];
  const errors: string[] = [];
  page.on('request', request => {
    const url = new URL(request.url());
    if (url.protocol.startsWith('http') && url.origin !== 'http://127.0.0.1:3302') {
      externalRequests.push(request.url());
    }
  });
  page.on('pageerror', error => errors.push(error.message));

  await page.route('**/admin/api/session', route => route.fulfill({ json: { authenticated: false, configured: false, csrf: 'csrf', operator: null, scopes: [] } }));
  for (const path of ['/login', '/', '/users/demo-user-01', '/limits']) {
    await page.goto(path);
    await expect(page.getByRole('heading', { name: '운영자 로그인', exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '데모로 들어가기 — 인증하지 않음', exact: true })).toHaveCount(0);
    await expect(page.getByRole('button', { name: '데모 초기화', exact: true })).toHaveCount(0);
    await expect(page.getByLabel('화면 상태', { exact: true })).toHaveCount(0);
  }

  expect(externalRequests).toEqual([]);
  expect(errors).toEqual([]);
});
