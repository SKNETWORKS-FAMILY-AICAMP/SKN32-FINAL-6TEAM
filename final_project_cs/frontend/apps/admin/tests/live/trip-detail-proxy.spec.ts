import { test, expect } from '@playwright/test';
import { createServer, type Server } from 'node:http';

let upstream: Server;
const calls: { url: string; cookie: string; method: string }[] = [];
const user = '11111111-1111-4111-8111-111111111111';
const trip = '22222222-2222-4222-8222-222222222222';
const path = `/admin/api/users/${user}/trips/${trip}`;

test.beforeAll(async () => {
  upstream = createServer((request, response) => {
    calls.push({ url: request.url || '', cookie: request.headers.cookie || '', method: request.method || '' });
    response.setHeader('Content-Type', 'application/json');
    response.end(JSON.stringify({ ok: true }));
  });
  await new Promise<void>((resolve, reject) => { upstream.once('error', reject); upstream.listen(3385, '127.0.0.1', resolve); });
});
test.afterAll(async () => { await new Promise<void>((resolve, reject) => upstream.close(error => error ? reject(error) : resolve())); });

test('여행 조회 네 경로·대화 커서를 실제 중계하고 고객 쿠키와 쓰기·임의 경로를 차단한다', async ({ request }) => {
  const headers = { Cookie: 'acop_ui=operator-cookie; acop_admin_csrf=csrf; tripilot_sid_dev=customer-cookie' };
  for (const suffix of ['', '/chat?after=22&limit=100', '/draft', '/plans/initial', '/plans/current']) {
    const response = await request.get(path + suffix, { headers });
    expect(response.status()).toBe(200);
    expect(response.headers()['cache-control']).toBe('no-store');
    expect(calls.at(-1)).toEqual({ url: path + suffix, method: 'GET', cookie: 'acop_ui=operator-cookie; acop_admin_csrf=csrf' });
  }
  const before = calls.length;
  expect((await request.post(path + '/draft', { headers, data: {} })).status()).toBe(405);
  expect((await request.post(path, { headers, data: {} })).status()).toBe(405);
  expect((await request.patch(path + '/plans/current', { headers, data: {} })).status()).toBe(405);
  expect((await request.get(path + '/plans/private')).status()).toBe(404);
  expect((await request.get(path.replace(user, 'invalid-user'))).status()).toBe(404);
  expect((await request.get(path + '/chat/private')).status()).toBe(404);
  expect(calls).toHaveLength(before);
});
