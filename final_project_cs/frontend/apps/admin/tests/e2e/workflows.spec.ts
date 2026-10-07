import { expect, test } from '@playwright/test';
import { main } from './support';

// 운영자 PC의 시간대와 관계없이 모든 운영 날짜 입력은 한국 시각이어야 한다.
test.use({ timezoneId: 'America/New_York' });

test('문의 상태에는 사유가 필요하고 템플릿 답변은 본문과 완료 상태를 남긴다', async ({ page }) => {
  await page.goto('/inquiries/inq-01');
  const detail = page.getByRole('region', { name: '문의 상세', exact: true });
  await detail.getByRole('combobox', { name: '문의 상태', exact: true }).selectOption('처리 중');
  await detail.getByRole('button', { name: '상태·담당 저장', exact: true }).click();
  await expect(detail.getByRole('alert')).toContainText('사유');
  await expect(detail.locator('span.badge').first()).toHaveText('접수');
  await detail.getByLabel('상태·담당 변경 사유 (필수)', { exact: true }).fill('문의 내용을 확인하여 담당자가 검토합니다.');
  await detail.getByRole('combobox', { name: '문의 담당자', exact: true }).selectOption('demo.operator');
  await detail.getByRole('button', { name: '상태·담당 저장', exact: true }).click();
  await expect(detail.locator('span.badge').first()).toHaveText('처리 중');

  await detail.getByRole('combobox', { name: '답변 템플릿', exact: true }).selectOption('tpl-limit');
  await expect(detail.getByRole('textbox', { name: '답변 본문', exact: true })).toHaveValue(/한국 시각 자정에 초기화/);
  const reply = '확인했습니다. 채팅 한도는 한국 시각 자정에 초기화됩니다. [독립 QA 답변]';
  await detail.getByRole('textbox', { name: '답변 본문', exact: true }).fill(reply);
  await detail.getByRole('button', { name: '답변 보내기', exact: true }).click();
  await expect(detail.locator('span.badge').first()).toHaveText('답변 완료');
  await expect(detail.getByText(reply, { exact: true })).toBeVisible();
  await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: '운영 기록', exact: true }).click();
  const record = main(page).getByRole('row').filter({ hasText: '문의 답변' }).filter({ hasText: 'inq-01' });
  await expect(record).toContainText('demo.operator');
  await expect(record).toContainText(reply);
});

test('답변 템플릿을 추가한 뒤 실제 답변 선택 목록에서 재사용한다', async ({ page }) => {
  await page.goto('/inquiries/inq-01');
  await page.getByRole('button', { name: '템플릿 관리', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '답변 템플릿 관리', exact: true });
  await dialog.getByLabel('템플릿 제목', { exact: true }).fill('QA 임시 안내');
  await dialog.getByLabel('템플릿 본문', { exact: true }).fill('현재 문의를 확인하고 있습니다. 확인 후 답변드리겠습니다.');
  await dialog.getByRole('button', { name: '템플릿 저장', exact: true }).click();
  await expect(dialog.getByRole('status')).toContainText('저장');
  await dialog.getByRole('button', { name: '템플릿 관리 닫기', exact: true }).click();
  await page.getByRole('combobox', { name: '답변 템플릿', exact: true }).selectOption({ label: 'QA 임시 안내' });
  await expect(page.getByRole('textbox', { name: '답변 본문', exact: true })).toHaveValue('현재 문의를 확인하고 있습니다. 확인 후 답변드리겠습니다.');
});

test('점검 전환은 사유 없이 거절하고 공지는 본문과 게시 기간을 저장한다', async ({ page }) => {
  await page.goto('/notices');
  await expect(page.getByLabel('예상 종료 (한국 시각)', { exact: true })).toHaveValue('2026-09-29T16:00');
  await expect(page.getByLabel('게시 시작 (한국 시각)', { exact: true })).toHaveValue('2026-09-29T14:00');
  await page.getByRole('button', { name: '점검 모드 켜기', exact: true }).click();
  await expect(main(page).getByRole('alert')).toContainText('사유');
  await expect(page.getByRole('button', { name: '점검 모드 켜기', exact: true })).toBeVisible();
  await page.getByLabel('점검 전환 사유 (필수)', { exact: true }).fill('점검 배너 전환 동작 확인');
  await page.getByLabel('예상 종료 (한국 시각)', { exact: true }).fill('2026-09-29T16:00');
  await page.getByRole('button', { name: '점검 모드 켜기', exact: true }).click();
  await expect(page.getByRole('button', { name: '점검 모드 끄기', exact: true })).toBeVisible();

  const noticeBody = '서울 여행 정보 확인 기능 점검 안내입니다. 실제로 게시되지 않는 QA 공지입니다.';
  await page.getByLabel('제목 · 한국어', { exact: true }).fill('QA 점검 안내');
  await page.getByLabel('내용 · 한국어', { exact: true }).fill(noticeBody);
  await page.getByLabel('제목 · English', { exact: true }).fill('QA maintenance notice');
  await page.getByLabel('내용 · English', { exact: true }).fill('This is a demo notice.');
  await page.getByLabel('게시 시작 (한국 시각)', { exact: true }).fill('2026-09-29T14:00');
  await page.getByLabel('게시 끝 (한국 시각)', { exact: true }).fill('2026-09-29T17:00');
  await page.getByRole('button', { name: '미리보기', exact: true }).click();
  await expect(page.getByRole('region', { name: '사용자 웹 미리보기', exact: true })).toContainText('This is a demo notice.');
  await page.getByRole('button', { name: '공지 게시', exact: true }).click();
  await expect(main(page).locator('summary').filter({ hasText: 'QA 점검 안내' })).toBeVisible();
  await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: '운영 기록', exact: true }).click();
  await expect(main(page).getByRole('row').filter({ hasText: '점검 모드 전환' })).toContainText('점검 배너 전환 동작 확인');
  await expect(main(page).getByRole('row').filter({ hasText: '공지 게시' })).toContainText(noticeBody);
});

for (const conclusion of ['전달 확인', '미전달 확인']) {
  test(`발송 ${conclusion}은 근거를 요구하고 unknown 상태를 보존한다`, async ({ page }) => {
    await page.goto('/ops');
    await main(page).getByRole('button', { name: conclusion, exact: true }).click();
    const dialog = page.getByRole('dialog', { name: conclusion, exact: true });
    await dialog.getByRole('button', { name: '확인 결과 기록', exact: true }).click();
    await expect(dialog.getByRole('alert')).toContainText('근거');
    await expect(dialog).toBeVisible();
    await dialog.getByLabel('사유 · 확인 근거 (필수)', { exact: true }).fill('외부 채널의 수신 기록을 직접 대조했습니다.');
    await dialog.getByRole('button', { name: '확인 결과 기록', exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await expect(main(page).getByText('확인이 필요한 알림이 없습니다.', { exact: true })).toBeVisible();
    await page.getByLabel('확인 완료 포함', { exact: true }).check();
    const row = main(page).getByRole('row').filter({ hasText: '여행 일정 변경 안내' });
    await expect(row).toContainText('unknown');
    await expect(row).toContainText('1회');
    await expect(row).toContainText(conclusion);
    await expect(row).toContainText('demo.operator');
    await expect(row).toContainText('외부 채널의 수신 기록을 직접 대조했습니다.');
    await expect(row.getByRole('button')).toHaveCount(0);
  });
}

for (const decision of ['승인', '거절']) {
  test(`예약 ${decision}은 근거와 사유를 확인한 뒤 대기 목록과 운영 기록에 반영한다`, async ({ page }) => {
    await page.goto('/ops');
    const request = main(page).getByRole('row').filter({ hasText: '방문 시간 변경 요청' });
    await request.getByText('근거 보기', { exact: true }).click();
    await expect(request).toContainText('공급자 확인 내용은 데모 문서입니다.');
    await request.getByRole('button', { name: decision, exact: true }).click();
    const dialog = page.getByRole('dialog', { name: `예약 ${decision}`, exact: true });
    await expect(dialog).toContainText('demo-user-02');
    await dialog.getByRole('button', { name: `${decision} 확정`, exact: true }).click();
    await expect(dialog.getByRole('alert')).toContainText('근거');
    await expect(request).toHaveCount(1);
    const reason = `공급자 확인 문서를 검토한 데모 ${decision} 판단`;
    await dialog.getByLabel('사유 · 확인 근거 (필수)', { exact: true }).fill(reason);
    await dialog.getByRole('button', { name: `${decision} 확정`, exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await expect(request).toHaveCount(0);
    await expect(main(page).getByText('승인을 기다리는 예약 요청이 없습니다.', { exact: true })).toBeVisible();
    await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: '운영 기록', exact: true }).click();
    const record = main(page).getByRole('row').filter({ hasText: `예약 요청 ${decision}` });
    await expect(record).toContainText('approval-01');
    await expect(record).toContainText('demo.operator');
    await expect(record).toContainText(reason);
  });
}

test('위임 회수와 재부여는 사유를 요구하고 상태 및 운영 기록을 남긴다', async ({ page }) => {
  await page.goto('/ops');
  const delegation = main(page).getByRole('row').filter({ hasText: 'demo-user-02' }).filter({ hasText: '여행 일정 확인' });
  await delegation.getByRole('button', { name: '거두기', exact: true }).click();
  let dialog = page.getByRole('dialog', { name: '위임 거두기', exact: true });
  await dialog.getByRole('button', { name: '위임 회수 확정', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('근거');
  await expect(delegation).toContainText('위임 중');
  await dialog.getByLabel('사유 · 확인 근거 (필수)', { exact: true }).fill('사용자 요청을 확인하여 위임 회수');
  await dialog.getByRole('button', { name: '위임 회수 확정', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(delegation).toContainText('없음');
  await delegation.getByRole('button', { name: '주기', exact: true }).click();
  dialog = page.getByRole('dialog', { name: '위임 주기', exact: true });
  await dialog.getByRole('button', { name: '위임 부여 확정', exact: true }).click();
  await expect(dialog.getByRole('alert')).toContainText('근거');
  await expect(delegation).toContainText('없음');
  await dialog.getByLabel('사유 · 확인 근거 (필수)', { exact: true }).fill('사용자 재요청을 확인하여 위임 부여');
  await dialog.getByRole('button', { name: '위임 부여 확정', exact: true }).click();
  await expect(dialog).toHaveCount(0);
  await expect(delegation).toContainText('위임 중');
  await page.getByRole('navigation', { name: '운영 메뉴' }).getByRole('button', { name: '운영 기록', exact: true }).click();
  const records = main(page).getByRole('row').filter({ hasText: '위임 변경' }).filter({ hasText: 'demo-user-02' });
  await expect(records).toHaveCount(2);
  await expect(records.filter({ hasText: '사용자 요청을 확인하여 위임 회수' })).toContainText('demo.operator');
  await expect(records.filter({ hasText: '사용자 재요청을 확인하여 위임 부여' })).toContainText('demo.operator');
});
