import { NextRequest } from 'next/server';

const COOKIE_NAMES = new Set(['acop_ui', 'acop_admin_csrf']);
async function proxy(request: NextRequest, context: { params: Promise<{ segments: string[] }> }) {
  const { segments } = await context.params;
  const allowed = new Set(['session', 'login', 'logout', 'snapshot', 'commands']);
  const settingsPath = segments.length === 2 && segments[0] === 'settings' && ['limits', 'retention'].includes(segments[1]);
  const casesPath = segments[0] === 'cases' && (segments.length === 1 || (segments.length === 2 && /^[0-9a-f-]{36}$/i.test(segments[1])));
  if (!settingsPath && !casesPath && (segments.length !== 1 || !allowed.has(segments[0]))) return Response.json({ detail: '경로를 찾을 수 없습니다.' }, { status: 404 });
  const origin = new URL(process.env.ADMIN_OPS_API_URL || 'http://127.0.0.1:8070');
  if (!['127.0.0.1', 'localhost', '[::1]'].includes(origin.hostname) || !['http:', 'https:'].includes(origin.protocol)) return Response.json({ detail: '운영 API 주소 설정을 확인해 주세요.' }, { status: 503 });
  const headers = new Headers();
  headers.set('Content-Type', 'application/json');
  headers.set('Cookie', request.cookies.getAll().filter(c => COOKIE_NAMES.has(c.name)).map(c => `${c.name}=${c.value}`).join('; '));
  const csrf = request.headers.get('x-csrf-token');
  if (csrf) headers.set('X-CSRF-Token', csrf);
  try {
    const upstream = await fetch(new URL(`/admin/api/${segments.join('/')}`, origin), { method: request.method, headers, body: request.method === 'GET' ? undefined : await request.text(), cache: 'no-store', redirect: 'manual', signal: AbortSignal.timeout(15000) });
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
