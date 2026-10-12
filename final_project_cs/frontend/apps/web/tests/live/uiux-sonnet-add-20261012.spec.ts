import { expect, test, type Page, type APIRequestContext } from '@playwright/test';
import { mockServer } from './helpers';
import { openFinished, INTAKE } from './plan-check-kit';

async function openAdd(page: Page, request: APIRequestContext) {
  await mockServer(request).reset();
  await openFinished(page, request, undefined, { intakeEvents: 'off' });
  await page.locator('[data-insert-near] > button').click();
  await page.getByRole('searchbox', { name: '장소 검색' }).fill('올리브영');
  await page.getByRole('list', { name: '장소 검색 결과' }).getByRole('button', { name: /올리브영 명동 플래그십/ }).click();
  return page.getByRole('form', { name: '일정 추가', exact: true });
}

test('추가 거절 안내는 필드 초점 이동으로 없어지지 않고 입력 수정 때 지워진다', async ({ page, request }) => {
  const form = await openAdd(page, request);
  await page.route(`**/v1/web/trip-intakes/${INTAKE}/edits`, route => route.fulfill({
    status: 409, contentType: 'application/json', body: JSON.stringify({ error: { code: 'schedule_conflict', message: '앞뒤 일정을 확인해 주세요.' } }),
  }));
  await form.getByRole('button', { name: '일정에 추가', exact: true }).click();
  await expect(form.getByRole('alert')).toContainText('앞뒤 일정');
  await form.getByLabel('날짜', { exact: true }).focus();
  await page.keyboard.press('Tab');
  await expect(form.getByRole('alert')).toContainText('앞뒤 일정');
  await form.getByLabel('일정 이름', { exact: true }).fill('다른 일정 이름');
  await expect(form.getByRole('alert')).toHaveCount(0);
});

test('시작 시각을 앞당겨 끝 시각이 유효해지면 이전 순서 오류를 지운다', async ({ page, request }) => {
  const form = await openAdd(page, request);
  await form.getByLabel('시작', { exact: true }).fill('12:00');
  await form.getByLabel('끝', { exact: true }).fill('11:00');
  await form.getByLabel('일정 이름', { exact: true }).focus();
  await expect(form.getByText('끝 시각은 시작보다 뒤로 입력해 주세요.', { exact: true })).toBeVisible();
  await form.getByLabel('시작', { exact: true }).fill('10:00');
  await expect(form.getByLabel('끝', { exact: true })).toHaveAttribute('aria-invalid', 'false');
  await expect(form.getByText('끝 시각은 시작보다 뒤로 입력해 주세요.', { exact: true })).toHaveCount(0);
});
