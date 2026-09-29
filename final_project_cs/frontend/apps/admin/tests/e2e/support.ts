import { expect, type Page } from '@playwright/test';

export const demoLabel = '데모 데이터 — 서버에 저장되지 않음';
export const loginLabel = '데모로 들어가기 — 인증하지 않음';
export const routes = [
  '/', '/users', '/users/demo-user-01', '/limits', '/usage', '/server',
  '/inquiries', '/inquiries/inq-01', '/notices', '/audit', '/ops',
] as const;
export const screenTitles: Record<typeof routes[number], string> = {
  '/': '오늘 처리할 일', '/users': '사용자', '/users/demo-user-01': '사용자 상세',
  '/limits': '한도 · 감시 조절', '/usage': '사용량', '/server': '서버 상태',
  '/inquiries': '문의함', '/inquiries/inq-01': '문의함', '/notices': '공지 · 점검',
  '/audit': '운영 기록', '/ops': '예약 승인 · 위임 · 발송 확인',
};

export const main = (page: Page) => page.getByRole('main');

export async function expectNoHorizontalOverflow(page: Page) {
  const size = await page.evaluate(() => ({
    viewport: window.innerWidth,
    content: document.documentElement.scrollWidth,
  }));
  expect(size.content, `페이지 가로 너비 ${size.content}px / 창 ${size.viewport}px`).toBeLessThanOrEqual(size.viewport);
}

export function collectBrowserFailures(page: Page, origin?: string) {
  const errors: string[] = [];
  const forbiddenRequests: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => {
    const url = new URL(request.url());
    if (!url.protocol.startsWith('http')) return;
    if (url.origin !== origin || /^\/(v1|api|health|introspection)(\/|$)/.test(url.pathname)) {
      forbiddenRequests.push(`${request.method()} ${url.href}`);
    }
  });
  return { errors, forbiddenRequests };
}
