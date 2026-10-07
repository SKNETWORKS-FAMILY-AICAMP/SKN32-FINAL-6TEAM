import { expect, test } from '@playwright/test';
import { resolve } from 'node:path';
import { pathToFileURL } from 'node:url';
import { collectBrowserFailures, demoLabel, expectNoHorizontalOverflow, loginLabel, main } from './support';

const standaloneUrl = pathToFileURL(resolve('mockups/admin-scenario.html')).href;

test('오프라인 차단 확인은 성공 후 닫히고 반대 작업에 새 사유를 요구한다', async ({ page, context }) => {
  const failures = collectBrowserFailures(page);
  await context.setOffline(true);
  await page.goto(`${standaloneUrl}#/users/demo-user-01`);
  await page.getByRole('button', { name: '사용자 차단', exact: true }).click();
  await page.getByLabel('차단·해제 사유 (필수)', { exact: true }).fill('오프라인 차단 흐름 확인');
  await page.getByRole('button', { name: '차단 확정', exact: true }).click();
  await expect(page.getByLabel('차단·해제 사유 (필수)', { exact: true })).toHaveCount(0);
  await page.getByRole('button', { name: '차단 해제', exact: true }).click();
  await expect(page.getByLabel('차단·해제 사유 (필수)', { exact: true })).toHaveValue('');
  await page.getByRole('button', { name: '차단 해제 확정', exact: true }).click();
  await expect(main(page).getByRole('alert')).toContainText('사유');
  await expect(page.getByRole('button', { name: '차단 해제', exact: true })).toBeVisible();
  expect(failures.errors).toEqual([]);
  expect(failures.forbiddenRequests).toEqual([]);
});

test('단일 HTML은 오프라인에서 키보드 로그인·예외 한도·문의 답변·감사 기록을 연결한다', async ({ page, context }, testInfo) => {
  const failures = collectBrowserFailures(page);
  await context.setOffline(true);
  await page.goto(standaloneUrl);
  await expect(page.getByText(demoLabel, { exact: true })).toBeVisible();
  const login = page.getByRole('button', { name: loginLabel, exact: true });
  for (let i = 0; i < 8 && !(await login.evaluate(element => element === document.activeElement)); i++) {
    await page.keyboard.press('Tab');
  }
  await expect(login).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(main(page).getByRole('heading', { name: '오늘 처리할 일', exact: true })).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('standalone-home-desktop.png'), fullPage: true });

  await page.keyboard.press('Tab');
  const skip = page.getByRole('link', { name: '본문으로 건너뛰기', exact: true });
  await expect(skip).toBeFocused();
  await page.keyboard.press('Enter');
  await expect(main(page)).toBeFocused();
  await expect(main(page).getByRole('heading', { name: '오늘 처리할 일', exact: true })).toBeVisible();

  const navigation = page.getByRole('navigation', { name: '운영 메뉴' });
  await navigation.getByRole('button', { name: '사용자', exact: true }).click();
  await main(page).getByRole('button', { name: 'demo-user-01 상세 보기', exact: true }).click();
  await page.getByLabel('② 채팅 하루 한도', { exact: true }).fill('80');
  await page.getByLabel('예외 한도 사유 (필수)', { exact: true }).fill('오프라인 시나리오: 여행 중 추가 상담');
  await page.getByRole('button', { name: '예외 한도 저장', exact: true }).click();
  await expect(page.getByRole('meter', { name: '오늘 채팅 사용률', exact: true })).toHaveAttribute('aria-valuetext', '50 / 80');
  await navigation.getByRole('button', { name: /^문의함/ }).click();
  await page.getByRole('combobox', { name: '답변 템플릿', exact: true }).selectOption('tpl-limit');
  await page.getByRole('textbox', { name: '답변 본문', exact: true }).fill('오늘 예외 한도를 80회로 조정했습니다. [오프라인 시나리오]');
  await page.getByRole('button', { name: '답변 보내기', exact: true }).click();
  await expect(page.getByRole('region', { name: '문의 상세', exact: true }).locator('span.badge').first()).toHaveText('답변 완료');
  await navigation.getByRole('button', { name: '운영 기록', exact: true }).click();
  await expect(main(page).getByRole('row').filter({ hasText: '예외 한도 변경' })).toContainText('오프라인 시나리오: 여행 중 추가 상담');
  await expect(main(page).getByRole('row').filter({ hasText: '문의 답변' })).toContainText('오늘 예외 한도를 80회로 조정했습니다.');
  await page.screenshot({ path: testInfo.outputPath('standalone-audit-desktop.png'), fullPage: true });

  await page.getByRole('button', { name: '데모 초기화', exact: true }).click();
  await expect(main(page).getByRole('row').filter({ hasText: '예외 한도 변경' })).toHaveCount(0);
  await expect(main(page).getByRole('row').filter({ hasText: '문의 답변' })).toHaveCount(0);
  expect(failures.errors).toEqual([]);
  expect(failures.forbiddenRequests).toEqual([]);
});

test('오프라인 모바일 메뉴·발송 확인 대화상자를 키보드로 조작한다', async ({ page, context }, testInfo) => {
  const failures = collectBrowserFailures(page);
  await context.setOffline(true);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(standaloneUrl);
  await page.getByRole('button', { name: loginLabel, exact: true }).click();
  const navigation = page.getByRole('navigation', { name: '운영 메뉴', includeHidden: true });
  await expect(navigation).toHaveCount(1);
  await expect(navigation).toBeHidden();
  const menus = ['운영 홈', '문의함', '사용자', '사용량', '서버 상태', '한도 · 감시 조절', '공지 · 점검', '운영 기록', '승인 · 위임 · 발송'];
  for (const menu of menus) {
    await page.getByRole('button', { name: '메뉴 열기', exact: true }).click();
    await expect(navigation).toBeVisible();
    await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: new RegExp(`^${menu}`) }).click();
    await expect(main(page).getByRole('heading', { level: 1 })).toBeVisible();
    await expect(page.getByRole('button', { name: '메뉴 열기', exact: true })).toHaveAttribute('aria-expanded', 'false');
    await expect(navigation).toBeHidden();
    await expectNoHorizontalOverflow(page);
  }
  await page.screenshot({ path: testInfo.outputPath('standalone-ops-mobile.png'), fullPage: true });
  const trigger = main(page).getByRole('button', { name: '미전달 확인', exact: true });
  await trigger.focus();
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: '미전달 확인', exact: true });
  await expect(dialog).toBeVisible();
  expect(await dialog.evaluate(element => element.matches(':modal'))).toBe(true);
  await expect(dialog.getByRole('textbox')).toBeFocused();
  for (let i = 0; i < 8; i++) {
    await page.keyboard.press('Tab');
    // Native dialog may hand focus to browser chrome at the wrap boundary.
    // That reports BODY; no background page control may receive focus.
    expect(await dialog.evaluate(element => element.contains(document.activeElement) || document.activeElement === document.body)).toBe(true);
    expect(await dialog.evaluate(element => element.matches(':modal'))).toBe(true);
  }
  await expect(dialog.getByRole('textbox')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(trigger).toBeFocused();
  expect(failures.errors).toEqual([]);
  expect(failures.forbiddenRequests).toEqual([]);
});
