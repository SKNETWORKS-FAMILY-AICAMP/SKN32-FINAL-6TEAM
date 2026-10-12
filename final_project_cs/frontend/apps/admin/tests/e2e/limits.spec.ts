import { expect, test } from '@playwright/test';
import { main } from './support';

test('차단·해제와 예외 한도는 사유를 요구하고 사용자와 운영 기록에 함께 반영한다', async ({ page }) => {
  await page.goto('/users/demo-user-01');
  await page.getByRole('button', { name: '사용자 차단', exact: true }).click();
  await page.getByRole('button', { name: '차단 확정', exact: true }).click();
  await expect(main(page).getByRole('alert')).toContainText('사유');
  await expect(page.getByRole('button', { name: '사용자 차단', exact: true })).toBeVisible();
  await page.getByLabel('차단·해제 사유 (필수)', { exact: true }).fill('반복 요청 확인 후 임시 차단');
  await page.getByRole('button', { name: '차단 확정', exact: true }).click();
  await expect(page.getByRole('button', { name: '차단 해제', exact: true })).toBeVisible();
  await page.getByLabel('차단·해제 사유 (필수)', { exact: true }).fill('사용자 요청 확인 후 차단 해제');
  await page.getByRole('button', { name: '차단 해제 확정', exact: true }).click();
  await expect(page.getByRole('button', { name: '사용자 차단', exact: true })).toBeVisible();

  await page.getByLabel('② 채팅 하루 한도', { exact: true }).fill('75');
  await page.getByRole('button', { name: '예외 한도 저장', exact: true }).click();
  await expect(main(page).getByRole('alert')).toContainText('사유');
  await expect(page.getByRole('meter', { name: '오늘 채팅 사용률', exact: true })).toHaveAttribute('aria-valuetext', '50 / 50');
  await page.getByLabel('예외 한도 사유 (필수)', { exact: true }).fill('오늘 여행 상담을 위한 한도 조정');
  await page.getByRole('button', { name: '예외 한도 저장', exact: true }).click();
  await expect(page.getByRole('meter', { name: '오늘 채팅 사용률', exact: true })).toHaveAttribute('aria-valuetext', '50 / 75');
  await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: '운영 기록', exact: true }).click();
  await expect(main(page).getByRole('row').filter({ hasText: '사용자 차단 해제' })).toContainText('사용자 요청 확인 후 차단 해제');
  await expect(main(page).getByRole('row').filter({ hasText: '예외 한도 변경' })).toContainText('오늘 여행 상담을 위한 한도 조정');
});

test('기본 한도 저장은 사유가 있어야 적용되고 기존 사용자 예외를 유지한다', async ({ page }) => {
  await page.goto('/limits');
  await page.getByLabel('② 채팅 하루 한도 (모든 사용자)', { exact: true }).fill('60');
  await page.getByRole('button', { name: '한도 · 감시 설정 저장', exact: true }).click();
  await expect(main(page).getByRole('alert')).toContainText('사유');
  await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: '사용자', exact: true }).click();
  await expect(main(page).getByRole('row').filter({ hasText: 'demo-user-01' })).toContainText('50 / 50');
  await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: '한도 · 감시 조절', exact: true }).click();
  await page.getByLabel('② 채팅 하루 한도 (모든 사용자)', { exact: true }).fill('60');
  await page.getByLabel('한도·감시 설정 변경 사유 (필수)', { exact: true }).fill('기본 채팅 한도 검토 결과 반영');
  await page.getByRole('button', { name: '한도 · 감시 설정 저장', exact: true }).click();
  await expect(main(page).getByRole('status')).toContainText('반영');
  await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: '사용자', exact: true }).click();
  await expect(main(page).getByRole('row').filter({ hasText: 'demo-user-01' })).toContainText('50 / 60');
  await expect(main(page).getByRole('row').filter({ hasText: 'demo-user-02' })).toContainText('32 / 80');
});

test('운영 상한은 사유를 요구하고 월 상한 도달도 호출 멈춤으로 보인다', async ({ page }) => {
  await page.goto('/usage');
  const google = main(page).getByRole('row').filter({ has: page.getByRole('button', { name: 'Google Places 운영 상한 조정', exact: true }) });
  await page.getByRole('button', { name: 'Google Places 운영 상한 조정', exact: true }).click();
  await page.getByLabel('하루 운영 상한', { exact: true }).fill('2000');
  await page.getByLabel('월 운영 상한', { exact: true }).fill('17000');
  await page.getByRole('button', { name: '운영 상한 저장', exact: true }).click();
  await expect(main(page).getByRole('alert')).toContainText('사유');
  await expect(google).toContainText('31,000');
  await page.getByLabel('운영 상한 변경 사유 (필수)', { exact: true }).fill('월 호출량 기준 차단 동작 확인');
  await page.getByRole('button', { name: '운영 상한 저장', exact: true }).click();
  await expect(google).toContainText('17,000');
  await expect(google).toContainText('멈춤');
  await expect(page.getByRole('button', { name: 'Google Routes 운영 상한 조정', exact: true })).toBeDisabled();
  await expect(page.getByRole('button', { name: 'Google 지도 표시 운영 상한 조정', exact: true })).toBeDisabled();
  await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: '운영 기록', exact: true }).click();
  await expect(main(page).getByRole('row').filter({ hasText: '외부 API 운영 상한 변경' })).toContainText('월 호출량 기준 차단 동작 확인');
});
