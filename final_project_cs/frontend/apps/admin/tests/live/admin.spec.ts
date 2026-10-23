import { test, expect } from '@playwright/test';
import { createDemoSnapshot } from '../../src/lib/demo/fixtures';

test('운영 로그인은 고객 로그인과 분리되고 실제 명령 계약을 사용한다', async ({ page }) => {
  let authenticated = false;
  const commands: unknown[] = [];
  const snapshot = { ...createDemoSnapshot(), live: true };
  await page.route('**/admin/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/session')) await route.fulfill({ json: { authenticated, configured: true, operator: authenticated ? 'real-operator' : null, scopes: ['ops:introspect','limits:write'], csrf: 'mock-csrf' } });
    else if (path.endsWith('/login')) { expect(route.request().headers()['x-csrf-token']).toBe('mock-csrf'); expect(route.request().postDataJSON()).toEqual({ operatorId: 'real-operator', password: 'secret-password' }); authenticated = true; await route.fulfill({ json: { operator: 'real-operator' } }); }
    else if (path.endsWith('/snapshot')) await route.fulfill({ json: snapshot });
    else if (path.endsWith('/commands')) { commands.push(route.request().postDataJSON()); await route.fulfill({ json: { ok: true } }); }
    else if (path.endsWith('/logout')) { authenticated = false; await route.fulfill({ json: { ok: true } }); }
    else await route.fulfill({ status: 404, json: { detail: 'missing' } });
  });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '운영자 로그인' })).toBeVisible();
  await page.getByLabel('운영자 ID').fill('real-operator');
  await page.getByLabel('비밀번호', { exact: true }).fill('secret-password');
  await page.getByRole('button', { name: '로그인', exact: true }).click();
  await expect(page.getByText('실제 운영 자료', { exact: true })).toBeVisible();
  await expect(page.getByText('인증된 운영자')).toBeVisible();
  await expect(page.getByText('데모 데이터 — 서버에 저장되지 않음')).toHaveCount(0);
  await page.getByRole('button', { name: '한도 · 감시 조절', exact: true }).click();
  await expect(page.getByRole('heading', { name: '안전 감시 주기' })).toBeVisible();
  await expect(page.getByRole('button', { name: '+ 단계 추가' })).toHaveCount(0);
  await page.getByRole('button', { name: '로그아웃', exact: true }).click();
  await expect(page.getByRole('heading', { name: '운영자 로그인' })).toBeVisible();
  expect(commands).toEqual([]);
});

test('운영 계정 미설정이면 닫히고 데모 자료를 보여주지 않는다', async ({ page }) => {
  await page.route('**/admin/api/session', route => route.fulfill({ json: { authenticated: false, configured: false, operator: null, scopes: [], csrf: 'csrf' } }));
  await page.goto('/users');
  await expect(page.getByRole('alert').filter({ hasText: '운영자 계정이 설정되지 않아 접근이 닫혀 있습니다.' })).toBeVisible();
  await expect(page.getByLabel('운영자 ID')).toHaveCount(0);
  await expect(page.getByText('demo-user-01')).toHaveCount(0);
});

test('운영 설정과 보관 기간을 기존 API 계약으로 연결한다', async ({ page }) => {
  const changed: unknown[] = [];
  await page.route('**/admin/api/**', async route => {
    const path = new URL(route.request().url()).pathname;
    if (path.endsWith('/session')) await route.fulfill({ json: { authenticated: true, configured: true, operator: 'operator', scopes: [], csrf: 'csrf' } });
    else if (path.endsWith('/snapshot')) await route.fulfill({ json: { ...createDemoSnapshot(), live: true } });
    else if (path.endsWith('/settings/limits')) {
      if (route.request().method() === 'PATCH') { changed.push(route.request().postDataJSON()); await route.fulfill({ json: { revision: 2 } }); }
      else await route.fulfill({ json: { revision: 1, limits: [{ name: 'web.map_provider', label: '화면 지도 종류', value: 'osm', type: 'choice', choices: ['osm','google'] }] } });
    } else if (path.endsWith('/settings/retention')) await route.fulfill({ json: { revision: 3, cells: [{ key: 'audit_days', label_ko: '감사 보관 기간', value: 365, unit: '일', min: 30, max: 3650, editable: true }], history: [], purge: { mode: 'dry_run', runs: [] } } });
    else await route.fulfill({ status: 404, json: { detail: 'missing' } });
  });
  await page.goto('/settings');
  await expect(page.getByRole('heading', { name: '운영 설정 · 보관 기간' })).toBeVisible();
  await page.getByLabel('화면 지도 종류').selectOption('google');
  await page.getByLabel('변경 사유', { exact: true }).fill('지도 설정 변경');
  await page.getByRole('button', { name: '설정 저장', exact: true }).click();
  await expect(page.getByRole('status')).toContainText('설정을 저장했습니다.');
  expect(changed).toEqual([{ expected_revision: 1, changes: { 'web.map_provider': 'google' }, reason: '지도 설정 변경' }]);
  await page.getByRole('button', { name: '약관 보관 기간', exact: true }).click();
  await expect(page.getByLabel('감사 보관 기간 일')).toHaveValue('365');
});
