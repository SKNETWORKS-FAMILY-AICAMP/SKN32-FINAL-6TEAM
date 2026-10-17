import { NextRequest } from 'next/server';

const COOKIE_NAMES = new Set(['acop_ui', 'acop_admin_csrf']);
async function proxy(request: NextRequest, context: { params: Promise<{ segments: string[] }> }) {
  const { segments } = await context.params;
  const allowed = new Set(['session', 'login', 'logout', 'snapshot', 'commands', 'api-limits', 'source-policy']);
  const settingsPath = segments.length === 2 && segments[0] === 'settings' && ['limits', 'retention'].includes(segments[1]);
  const casesPath = segments[0] === 'cases' && (segments.length === 1 || (segments.length === 2 && /^[0-9a-f-]{36}$/i.test(segments[1])));
  const monitoringPath = ['simulations', 'watch-runs'].includes(segments[0]) && (segments.length === 1 || (segments.length === 2 && /^[0-9a-f-]{36}$/i.test(segments[1])));
  const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const tripPath = segments[0] === 'users' && uuid.test(segments[1] || '') && segments[2] === 'trips' && uuid.test(segments[3] || '') &&
    (segments.length === 4 || (segments.length === 5 && segments[4] === 'chat') ||
      (segments.length === 6 && segments[4] === 'plans' && ['initial', 'current'].includes(segments[5])));
  const receiptPath = segments[0] === 'simulations' && segments.length === 2 && segments[1] === 'receipts' && request.method === 'GET';
  const mockReceiptPath = segments[0] === 'simulations' && segments.length === 3 && /^[0-9a-f-]{36}$/i.test(segments[1]) && segments[2] === 'mock-receipts' && request.method === 'POST';
  // 결함 사후 분석 — 목록 · 한 결함의 영향 고객 · 발생 기록 · 해결 판 기록(지문은 sha256 16진 64자)
  const diagnosticsPath = segments[0] === 'diagnostics' && (segments.length === 1 || (segments.length === 3 && /^[a-f0-9]{64}$/.test(segments[1]) && ['customers', 'events', 'resolution'].includes(segments[2])));
  if (!settingsPath && !casesPath && !monitoringPath && !receiptPath && !mockReceiptPath && !diagnosticsPath && !tripPath && (segments.length !== 1 || !allowed.has(segments[0]))) return Response.json({ detail: '경로를 찾을 수 없습니다.' }, { status: 404 });
  if (tripPath && request.method !== 'GET') return Response.json({ detail: '여행 상세는 조회만 할 수 있습니다.' }, { status: 405 });
  const origin = new URL(process.env.ADMIN_OPS_API_URL || 'http://127.0.0.1:8070');
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(origin.hostname) || !['http:', 'https:'].includes(origin.protocol)) return Response.json({ detail: '운영 API 주소 설정을 확인해 주세요.' }, { status: 503 });
  const headers = new Headers();
  headers.set('Content-Type', 'application/json');
  headers.set('Cookie', request.cookies.getAll().filter(c => COOKIE_NAMES.has(c.name)).map(c => `${c.name}=${c.value}`).join('; '));
  const csrf = request.headers.get('x-csrf-token');
  if (csrf) headers.set('X-CSRF-Token', csrf);
  try {
    const target = new URL(`/admin/api/${segments.join('/')}`, origin);
    target.search = request.nextUrl.search;
    const upstream = await fetch(target, { method: request.method, headers, body: request.method === 'GET' ? undefined : await request.text(), cache: 'no-store', redirect: 'manual', signal: AbortSignal.timeout(15000) });
    const responseHeaders = new Headers({ 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    for (const cookie of upstream.headers.getSetCookie()) responseHeaders.append('Set-Cookie', cookie);
    return new Response(await upstream.text(), { status: upstream.status, headers: responseHeaders });
  } catch {
    return Response.json({ detail: '운영 API에 연결하지 못했습니다. 처리 여부는 목록에서 확인해 주세요.' }, { status: 503 });
  }
}
export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
